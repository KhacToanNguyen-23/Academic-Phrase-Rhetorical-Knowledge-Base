"""Build a local vocabulary evidence snapshot from classified, ingested papers."""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.corpus.models import Article, License, Sentence
from aprkb.modules.vocabulary.models import VocabLemma, VocabLemmaResearchStat, VocabResearchGroup

OpenAlexID = Annotated[str, StringConstraints(pattern=r"^[1-9][0-9]{0,11}$")]
TaxonomyLabel = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
TOKEN = re.compile(r"[^\W_]+(?:['’\-][^\W_]+)*")
SNAPSHOT_LOCK_ID = 4715538080323821


class ClassifiedPaper(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    article_id: UUID
    field_id: OpenAlexID
    field_name: TaxonomyLabel
    subfield_id: OpenAlexID | None = None
    subfield_name: TaxonomyLabel | None = None

    @model_validator(mode="after")
    def check_subfield(self) -> "ClassifiedPaper":
        if (self.subfield_id is None) != (self.subfield_name is None):
            raise ValueError("provide both subfield_id and subfield_name or neither")
        return self


class ResearchManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    papers: list[ClassifiedPaper] = Field(min_length=2, max_length=1000)

    @model_validator(mode="after")
    def check_taxonomy(self) -> "ResearchManifest":
        if len({paper.article_id for paper in self.papers}) != len(self.papers):
            raise ValueError("each local article must occur once")

        fields: dict[str, str] = {}
        subfields: dict[str, tuple[str, str]] = {}
        for paper in self.papers:
            if fields.setdefault(paper.field_id, paper.field_name) != paper.field_name:
                raise ValueError(f"conflicting names for field {paper.field_id}")
            if paper.subfield_id is not None and paper.subfield_name is not None:
                identity = (paper.field_id, paper.subfield_name)
                if subfields.setdefault(paper.subfield_id, identity) != identity:
                    raise ValueError(f"conflicting assignments for subfield {paper.subfield_id}")
        if len(fields) < 2:
            raise ValueError("sample papers from at least two fields to make a comparison")
        return self


@dataclass
class Cohort:
    group: VocabResearchGroup
    matches: Counter[UUID]


def _cohorts(manifest: ResearchManifest) -> dict[str, Cohort]:
    cohorts: dict[str, Cohort] = {}
    for paper in manifest.papers:
        for key, subfield_id, subfield_name in _groups(paper):
            if key not in cohorts:
                group = VocabResearchGroup(
                    key=key,
                    field_id=paper.field_id,
                    field_name=paper.field_name,
                    subfield_id=subfield_id,
                    subfield_name=subfield_name,
                    paper_count=0,
                )
                cohorts[key] = Cohort(group, Counter())
            cohorts[key].group.paper_count += 1
    return cohorts


def _groups(paper: ClassifiedPaper) -> list[tuple[str, str | None, str | None]]:
    groups: list[tuple[str, str | None, str | None]] = [(f"field:{paper.field_id}", None, None)]
    if paper.subfield_id is not None:
        groups.append((f"subfield:{paper.subfield_id}", paper.subfield_id, paper.subfield_name))
    return groups


def _enriched_matches(
    matches: Counter[UUID], total: Counter[UUID], group_size: int, sample_size: int
) -> dict[UUID, int]:
    return {
        lemma: count
        for lemma, count in matches.items()
        if count >= 2 and count * sample_size > total[lemma] * group_size
    }


async def build_research_snapshot(
    session: AsyncSession, manifest: ResearchManifest
) -> tuple[int, int]:
    """Replace the snapshot inside the caller's transaction."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": SNAPSHOT_LOCK_ID}
    )
    lemmas_by_spelling: dict[str, list[UUID]] = defaultdict(list)
    for lemma_id, word in await session.execute(select(VocabLemma.id, VocabLemma.word)):
        lemmas_by_spelling[word.casefold()].append(lemma_id)
    if not lemmas_by_spelling:
        raise ValueError("import vocabulary before building research evidence")
    unambiguous = {word: ids[0] for word, ids in lemmas_by_spelling.items() if len(ids) == 1}

    cohorts = _cohorts(manifest)
    total: Counter[UUID] = Counter()
    for paper in manifest.papers:
        sentences = await session.scalars(
            select(Sentence.text)
            .join(Article, Article.id == Sentence.article_id)
            .join(License, License.id == Article.license_id)
            .where(
                Sentence.article_id == paper.article_id,
                Article.ingest_status == "ready",
                License.allows_mining.is_(True),
                License.code != "DEV-UNVERIFIED",
            )
        )
        words = {
            match.group().casefold() for sentence in sentences for match in TOKEN.finditer(sentence)
        }
        if not words:
            raise ValueError(
                f"article {paper.article_id} has no ready, rights-cleared text for this pilot"
            )
        hits = {unambiguous[word] for word in words if word in unambiguous}
        total.update(hits)
        for key, _, _ in _groups(paper):
            cohorts[key].matches.update(hits)

    await session.execute(delete(VocabResearchGroup))
    session.add_all([cohort.group for cohort in cohorts.values()])
    await session.flush()
    stats_count = 0
    for key, cohort in cohorts.items():
        matches = _enriched_matches(
            cohort.matches, total, cohort.group.paper_count, len(manifest.papers)
        )
        if matches:
            await session.execute(
                insert(VocabLemmaResearchStat),
                [
                    {"group_key": key, "lemma_id": lemma_id, "paper_count": paper_count}
                    for lemma_id, paper_count in matches.items()
                ],
            )
        stats_count += len(matches)
    return len(cohorts), stats_count
