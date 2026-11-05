"""Transactional handlers for import, ingestion, and mining jobs."""

from collections.abc import Callable
from dataclasses import asdict, dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.core.config import settings
from aprkb.core.logging import get_logger
from aprkb.modules.corpus.blobstore import BlobStore, LocalBlobStore
from aprkb.modules.corpus.importer import IMPORT_JOB_TYPE, MAX_IMPORT_BATCH_LIMIT, import_page
from aprkb.modules.corpus.ingest import parse_and_analyze
from aprkb.modules.corpus.models import Article, ArticleSection, License, Sentence
from aprkb.modules.corpus.parsers import parser_for_key
from aprkb.modules.corpus.schemas import DEFAULT_ARTIFACT_KINDS, SlrWorkFilters
from aprkb.modules.corpus.sentence_splitter import split_sentences
from aprkb.modules.corpus.sources import ArticleSource, build_article_source
from aprkb.modules.corpus.sources.base import ImportOptions
from aprkb.modules.mining.candidate_writer import CandidateDraft, CandidateWriter
from aprkb.modules.mining.models import Candidate, Job
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.nlp import NlpEngineInfo, SentenceAnalysis, SpacyEngine
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import PolicyBundle, load_policy_bundle

ArticleSourceFactory = Callable[[str], ArticleSource]
logger = get_logger(__name__)
_SPACY_ENGINES: dict[str, SpacyEngine] = {}


class _SessionCandidateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create_candidate(self, draft: CandidateDraft) -> Candidate:
        candidate = Candidate(
            canonical_frame=draft.canonical_frame,
            source_sentence_ids=draft.source_sentence_ids,
            slots={name: slot.model_dump(mode="json") for name, slot in draft.slots.items()},
            confidence=draft.confidence,
            epistemic_strength=draft.epistemic_strength,
            cluster_key=draft.cluster_key,
            occurrences=draft.occurrences,
            status="pending",
        )
        self._session.add(candidate)
        return candidate


async def handle_job(
    session: AsyncSession,
    job: Job,
    blob_store: BlobStore,
    *,
    article_source_factory: ArticleSourceFactory = build_article_source,
) -> str | None:
    if job.type == IMPORT_JOB_TYPE:
        return await _import(session, job, blob_store, article_source_factory)
    if job.type == "label_gold":
        sample_batch = job.payload.get("sample_batch")
        if not isinstance(sample_batch, str):
            return "Job payload is missing sample_batch"
        from aprkb.modules.gold.service import label_sample_batch

        job.result = await label_sample_batch(
            session, sample_batch=sample_batch, request_id=str(job.id)
        )
        return None
    article_value = job.payload.get("article_id")
    if not isinstance(article_value, str):
        return "Job payload is missing article_id"
    try:
        article_id = UUID(article_value)
    except ValueError:
        return "Job payload contains an invalid article_id"

    article = await session.get(Article, article_id)
    if article is None:
        return "Article not found"
    if job.type == "ingest_article":
        return await _ingest(session, article, blob_store)
    if job.type == "mine_article":
        return await _mine(session, article)
    return "Unknown job type"


async def _import(
    session: AsyncSession,
    job: Job,
    blob_store: BlobStore,
    article_source_factory: ArticleSourceFactory,
) -> str | None:
    source_name = job.payload.get("source")
    cursor = job.payload.get("cursor")
    limit = job.payload.get("limit")
    if not isinstance(source_name, str):
        return "Job payload is missing source"
    if cursor is not None and not isinstance(cursor, str):
        return "Job payload contains an invalid cursor"
    if not isinstance(limit, int) or not 1 <= limit <= MAX_IMPORT_BATCH_LIMIT:
        return "Job payload contains an invalid limit"
    try:
        raw_filters = job.payload.get("filters", {})
        raw_kinds = job.payload.get("artifact_kinds", list(DEFAULT_ARTIFACT_KINDS))
        profile_value = job.payload.get("profile_id")
        if not isinstance(raw_filters, dict) or not isinstance(raw_kinds, list):
            return "Job payload contains invalid import options"
        filters = SlrWorkFilters.model_validate(raw_filters).model_dump(
            by_alias=True, exclude_none=True
        )
        if (
            any(kind not in DEFAULT_ARTIFACT_KINDS for kind in raw_kinds)
            or not raw_kinds
            or len(set(raw_kinds)) != len(raw_kinds)
        ):
            return "Job payload contains invalid artifact kinds"
        profile_id = UUID(profile_value) if isinstance(profile_value, str) else None
        batch_value = job.payload.get("batch_id")
        batch_id = UUID(batch_value) if isinstance(batch_value, str) else None
    except (ValueError, TypeError):
        return "Job payload contains invalid import options"
    try:
        source = article_source_factory(source_name)
    except ValueError as error:
        if str(error) == "SLR_API_KEY is required when ARTICLE_SOURCE=slr":
            return str(error)
        return "Unknown article source"
    # Keep a failed page atomic while leaving the outer transaction available to
    # mark the import job failed. import_page compensates any blobs it wrote.
    try:
        async with session.begin_nested():
            summary = await import_page(
                session,
                source=source,
                blob_store=blob_store,
                cursor=cursor,
                limit=limit,
                job_id=job.id,
                options=ImportOptions(filters, tuple(raw_kinds)),
                profile_id=profile_id,
                batch_id=batch_id,
            )
            job.result = {
                **asdict(summary),
                "profile_id": str(profile_id) if profile_id else None,
                "batch_id": str(batch_id or job.id),
            }
        logger.info(
            "Import page done job_id=%s source=%s profile_id=%s filters=%s listed=%s imported=%s "
            "skipped_license=%s skipped_format=%s skipped_duplicate=%s "
            "skipped_invalid_content=%s continuation_job_id=%s",
            job.id,
            source_name,
            profile_id,
            filters,
            summary.listed,
            summary.imported,
            summary.skipped_license,
            summary.skipped_format,
            summary.skipped_duplicate,
            summary.skipped_invalid_content,
            summary.continuation_job_id,
        )
    finally:
        close = getattr(source, "aclose", None)
        if close is not None:
            await close()
    return None


async def _ingest(session: AsyncSession, article: Article, blob_store: BlobStore) -> str | None:
    license_row = await session.scalar(
        select(License).where(License.id == article.license_id).with_for_update()
    )
    if license_row is None or not license_row.allows_mining:
        article.ingest_status = "rejected"
        return "Article license does not allow mining"

    content = blob_store.get(article.blob_key)
    parser = parser_for_key(article.blob_key)
    if parser is None:
        article.ingest_status = "failed"
        return "Unsupported article format"
    policies = load_policy_bundle()
    try:
        nlp_info, section_analyser = _build_section_analyser(policies)
    except RuntimeError as error:
        article.ingest_status = "failed"
        return str(error)
    article.nlp_engine = nlp_info.to_json()
    prepared = parse_and_analyze(
        parser,
        content,
        section_headings=policies.section_headings,
        analyse_section=section_analyser,
    )
    section_rows: dict[int, ArticleSection] = {}
    for section in prepared.sections:
        section_row = ArticleSection(
            article_id=article.id,
            section_code=section.section_code,
            heading=section.parsed.heading,
            order=section.parsed.order,
        )
        session.add(section_row)
        section_rows[section.parsed.order] = section_row
    await session.flush()
    for sentence in prepared.sentences:
        section_row = section_rows[sentence.section_order]
        session.add(
            Sentence(
                article_id=article.id,
                article_section_id=section_row.id,
                text=sentence.text,
                char_start=sentence.char_start,
                char_end=sentence.char_end,
                nlp_features=sentence.nlp_features,
                boundary_source=sentence.boundary_source,
            )
        )
    article.ingest_status = "ready"
    return None


def _build_section_analyser(
    policies: PolicyBundle,
) -> tuple[
    NlpEngineInfo,
    Callable[[str], list[tuple[str, int, int, dict[str, object] | None, str]]],
]:
    if settings.nlp_engine == "regex":
        info = NlpEngineInfo(
            engine="regex",
            spacy_version="",
            model_name="regex",
            model_version="",
            components=("sentence_splitter",),
            schema_version=1,
            abbreviation_guard=False,
            boundary_policy_version=policies.sentence_rules.version,
        )

        def regex_analyse(text: str) -> list[tuple[str, int, int, dict[str, object] | None, str]]:
            return [
                (span.text, span.char_start, span.char_end, None, span.boundary_source)
                for span in split_sentences(text, rules=policies.sentence_rules)
            ]

        return info, regex_analyse

    if settings.nlp_engine != "spacy":
        raise RuntimeError(f"Unsupported NLP_ENGINE={settings.nlp_engine!r}")
    engine = _get_spacy_engine(settings.nlp_model)

    def spacy_analyse(text: str) -> list[tuple[str, int, int, dict[str, object] | None, str]]:
        return [
            (
                text[analysis.char_start : analysis.char_end],
                analysis.char_start,
                analysis.char_end,
                analysis.to_json(),
                analysis.boundary_source,
            )
            for analysis in engine.analyze(text)
        ]

    return engine.info, spacy_analyse


def _get_spacy_engine(model_name: str) -> SpacyEngine:
    engine = _SPACY_ENGINES.get(model_name)
    if engine is not None:
        return engine
    try:
        engine = SpacyEngine(model_name)
    except Exception as error:
        raise RuntimeError(
            f"NLP_ENGINE=spacy requires spaCy and model {model_name!r}; "
            f"installation/load failed: {type(error).__name__}"
        ) from error
    _SPACY_ENGINES[model_name] = engine
    return engine


@dataclass(frozen=True)
class ReingestResult:
    status: str
    sentences_before: int = 0
    sentences_after: int = 0
    pending_candidates_removed: int = 0
    error: str | None = None


async def reingest_article(
    session: AsyncSession, article: Article, blob_store: BlobStore
) -> ReingestResult:
    """Replace an article's sections and sentences after splitter or detector changes.

    Pending candidates that point at the old sentences are removed with them. Articles
    with reviewed candidates are left untouched so review history keeps valid sources.
    The caller owns the transaction.
    """
    old_ids = list(
        await session.scalars(select(Sentence.id).where(Sentence.article_id == article.id))
    )
    linked = (
        list(
            await session.scalars(
                select(Candidate).where(Candidate.source_sentence_ids.op("&&")(old_ids))
            )
        )
        if old_ids
        else []
    )
    if any(candidate.status != "pending" for candidate in linked):
        return ReingestResult(status="skipped_reviewed_candidates", sentences_before=len(old_ids))
    for candidate in linked:
        await session.delete(candidate)
    await session.execute(delete(Sentence).where(Sentence.article_id == article.id))
    await session.execute(delete(ArticleSection).where(ArticleSection.article_id == article.id))
    await session.flush()
    error = await _ingest(session, article, blob_store)
    await session.flush()
    after = len(
        list(await session.scalars(select(Sentence.id).where(Sentence.article_id == article.id)))
    )
    return ReingestResult(
        status="failed" if error else "ready",
        sentences_before=len(old_ids),
        sentences_after=after,
        pending_candidates_removed=len(linked),
        error=error,
    )


async def _mine(session: AsyncSession, article: Article) -> str | None:
    if article.ingest_status != "ready":
        return "Article ingestion is not ready"
    # Rights must be rechecked before querying any source sentence text.
    license_row = await session.scalar(
        select(License).where(License.id == article.license_id).with_for_update()
    )
    if license_row is None or not license_row.allows_mining:
        return "Article license does not allow mining"
    rows = list(
        await session.execute(
            select(Sentence, ArticleSection.section_code)
            .outerjoin(ArticleSection, Sentence.article_section_id == ArticleSection.id)
            .where(Sentence.article_id == article.id)
            .order_by(Sentence.char_start, Sentence.id)
        )
    )
    if not rows:
        return "Article has no parsed sentences"
    policies = load_policy_bundle()
    pipeline = MiningPipeline(stages=build_stages(policy_bundle=policies))
    mining_rows: list[MiningItem] = []
    locator = _syntax_locator(article)
    previous_text: str | None = None
    previous_section: str | None = None
    for sentence, code in rows:
        context = previous_text if code is not None and code == previous_section else None
        tokens = None
        if sentence.nlp_features is not None:
            try:
                tokens = usable_tokens(SentenceAnalysis.from_json(sentence.nlp_features))
            except ValueError:
                tokens = None
        mining_rows.append(
            MiningItem(
                text=sentence.text,
                source_sentence_ids=[sentence.id],
                section_code=code,
                char_start=sentence.char_start,
                previous_text=context,
                tokens=tokens,
                locator=locator if tokens is not None else None,
            )
        )
        previous_text = sentence.text
        previous_section = code
    items = pipeline.process(mining_rows)
    writer = CandidateWriter(
        _SessionCandidateRepository(session),
        reporting_policy=policies.reporting_verbs,
        constructions_policy=policies.constructions,
        lead_ins_policy=policies.lead_ins,
    )
    for item in items:
        writer.write(
            CandidateDraft(
                canonical_frame=item.text,
                source_sentence_ids=item.source_sentence_ids,
                slots=item.slots,
                confidence=None,
                epistemic_strength=item.epistemic_strength,
                cluster_key=item.cluster_key,
                occurrences=[
                    {
                        "sentence_id": str(occurrence.sentence_id),
                        "sentence_start": occurrence.sentence_start,
                        "sentence_end": occurrence.sentence_end,
                        "slot_spans": occurrence.slot_spans,
                    }
                    for occurrence in item.occurrences
                ],
                construction_id=item.construction_id,
            )
        )
    return None


def _syntax_locator(article: Article) -> str | None:
    metadata = article.nlp_engine
    if not isinstance(metadata, dict) or metadata.get("engine") != "spacy":
        return None
    model = metadata.get("model_name")
    version = metadata.get("model_version")
    if not isinstance(model, str) or not isinstance(version, str):
        return None
    return f"syntax:{model}:{version}"


def local_blob_store() -> LocalBlobStore:
    return LocalBlobStore(settings.blob_dir)
