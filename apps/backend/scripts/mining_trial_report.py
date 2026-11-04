"""Run an aggregate-only phase-4 trial over owner-provided plain-text or Markdown files."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import TextIO
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aprkb.core.config import settings
from aprkb.modules.corpus.ingest import parse_and_analyze
from aprkb.modules.corpus.models import Article, License
from aprkb.modules.corpus.parsers import parser_for_key
from aprkb.modules.mining.pipeline import MiningPipeline
from aprkb.modules.mining.stages import build_stages
from aprkb.modules.mining.stages.base import MiningItem
from aprkb.modules.mining.stages.construction_matcher import ReportingWithConstruction
from aprkb.modules.mining.stages.sentence_filter import SentenceFilter
from aprkb.nlp import SentenceAnalysis, SpacyEngine
from aprkb.nlp.syntax import usable_tokens
from aprkb.policies.loader import PolicyBundle, load_policy_bundle


async def _verify_rights(files: list[Path], blob_root: Path) -> tuple[str, ...]:
    """Check every file's blob key against mining-allowed article metadata before reading it."""
    root = blob_root.resolve()
    file_keys: set[str] = set()
    for path in files:
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("trial files must be inside the configured blob root")
        file_keys.add(resolved.relative_to(root).as_posix())

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            rows = await session.execute(
                select(Article.blob_key, License.code)
                .join(License, License.id == Article.license_id)
                .where(License.allows_mining.is_(True))
                .where(Article.blob_key.in_(file_keys))
            )
            authorized = {key: code for key, code in rows}
    finally:
        await engine.dispose()

    missing = file_keys - authorized.keys()
    if missing:
        raise ValueError(f"{len(missing)} trial files lack a mining-allowed article record")
    return tuple(sorted(set(authorized.values())))


def _validate_dump_path(path: Path) -> Path:
    """Require an unused ignored file under the worktree's local tmp directory."""
    repository = Path(__file__).resolve().parents[3]
    local_tmp = repository / "tmp"
    is_junction = getattr(os.path, "isjunction", lambda _: False)
    if local_tmp.is_symlink() or is_junction(local_tmp):
        raise ValueError("--dump requires tmp/ to be a real directory, not a link")
    if not local_tmp.exists():
        local_tmp.mkdir()
    if not local_tmp.is_dir() or not local_tmp.resolve().is_relative_to(repository):
        raise ValueError("--dump requires a real tmp/ directory inside the worktree")
    target = path.resolve() if path.is_absolute() else (Path.cwd() / path).resolve()
    if not target.is_relative_to(local_tmp.resolve()) or target == local_tmp.resolve():
        raise ValueError("--dump must name a new file under the worktree tmp/ directory")
    if target.parent != local_tmp.resolve():
        raise ValueError("--dump file must be directly inside the worktree tmp/ directory")
    if target.exists():
        raise ValueError("--dump target already exists; choose a new filename")
    relative = target.relative_to(repository).as_posix()
    ignored = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", relative],
        cwd=repository,
        check=False,
    )
    if ignored.returncode != 0:
        raise ValueError("--dump target must be ignored by Git")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "--", relative],
        cwd=repository,
        capture_output=True,
        check=False,
    )
    if tracked.returncode == 0:
        raise ValueError("--dump target is tracked by Git")
    return target


def _open_dump_file(path: Path | None) -> tuple[TextIO | None, object | None]:
    """Open an exclusive Windows-local dump while locking its parent directory."""
    if path is None:
        return None, None
    if os.name != "nt":
        raise ValueError("--dump is supported on Windows only to keep the local output path fixed")
    target = _validate_dump_path(path)
    try:
        directory_guard = _open_windows_tmp_guard(target.parent)
        try:
            stream = target.open("x", encoding="utf-8", newline="\n")
        except Exception:
            _close_dump_guard(directory_guard)
            raise
        return stream, directory_guard
    except FileExistsError as error:
        raise ValueError("--dump target already exists; choose a new filename") from error


def _open_windows_tmp_guard(directory: Path) -> object:
    """Lock tmp/ against rename/replacement, then verify the opened directory's real path."""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    # Share read/write access but withhold FILE_SHARE_DELETE to block directory swaps.
    handle = create_file(str(directory), 0x80, 0x1 | 0x2, None, 3, 0x02000000, None)
    if handle == wintypes.HANDLE(-1).value:
        raise OSError(ctypes.get_last_error(), "could not lock worktree tmp directory")

    final_path = kernel32.GetFinalPathNameByHandleW
    final_path.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    final_path.restype = wintypes.DWORD
    buffer = ctypes.create_unicode_buffer(32768)
    length = final_path(handle, buffer, len(buffer), 0)
    if length == 0 or length >= len(buffer):
        _close_dump_guard(handle)
        raise OSError(ctypes.get_last_error(), "could not resolve locked tmp directory")
    name = buffer.value
    if name.startswith("\\\\?\\UNC\\"):
        actual = Path("\\\\" + name[8:])
    else:
        actual = Path(name.removeprefix("\\\\?\\"))
    expected = Path(__file__).resolve().parents[3] / "tmp"
    if actual != expected:
        _close_dump_guard(handle)
        raise ValueError("--dump tmp directory does not resolve to the worktree tmp/")
    return handle


def _close_dump_guard(guard: object) -> None:
    import ctypes
    from ctypes import wintypes

    close_handle = ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    close_handle(wintypes.HANDLE(guard))


def _spacy_section_analyser(
    engine: SpacyEngine, text: str
) -> list[tuple[str, int, int, dict[str, object] | None, str]]:
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


def trial_report(
    directory: Path, *, blob_root: Path | None, model: str, dump: Path | None = None
) -> dict[str, object]:
    """Return only aggregate counts and version metadata; never return source strings."""
    files = sorted(
        path
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.casefold() in {".txt", ".md"}
    )
    if not files:
        raise ValueError("no .txt or .md files found in the trial directory")
    if blob_root is None:
        if directory.name != "articles":
            raise ValueError("provide --blob-root so mining rights can be checked before reading")
        blob_root = directory.parent
    licenses = asyncio.run(_verify_rights(files, blob_root))
    policy = load_policy_bundle()
    engine = SpacyEngine(model)
    dump_file, dump_guard = _open_dump_file(dump)
    try:
        return _run_trial(
            files,
            licenses,
            policy=policy,
            engine=engine,
            dump_file=dump_file,
            dump_guard=dump_guard,
        )
    finally:
        if dump_file is not None:
            dump_file.close()
        if dump_guard is not None:
            _close_dump_guard(dump_guard)


def _run_trial(
    files: list[Path],
    licenses: tuple[str, ...],
    *,
    policy: PolicyBundle,
    engine: SpacyEngine,
    dump_file: TextIO | None,
    dump_guard: object | None,
) -> dict[str, object]:
    stages = build_stages(policy_bundle=policy)
    sentence_filter = next(stage for stage in stages if isinstance(stage, SentenceFilter))
    extractor = next(stage for stage in stages if isinstance(stage, ReportingWithConstruction))
    pipeline = MiningPipeline(stages=stages)
    rejected: Counter[str] = Counter()
    extraction: Counter[str] = Counter()
    coordinated_reporting = 0
    sentences = filtered = imperative_accepted = 0
    dump_records: list[tuple[str, str | None, str]] = []

    for path in files:
        parser = parser_for_key(path.name)
        if parser is None:
            raise ValueError(f"no parser for trial file extension: {path.suffix}")
        source = path.read_bytes()
        prepared = parse_and_analyze(
            parser,
            source,
            section_headings=policy.section_headings,
            analyse_section=lambda text: _spacy_section_analyser(engine, text),
        )
        previous_text: str | None = None
        previous_section: str | None = None
        locator = f"syntax:{engine.info.model_name}:{engine.info.model_version}"
        for sentence in prepared.sentences:
            sentences += 1
            text = sentence.text
            analysis = (
                SentenceAnalysis.from_json(sentence.nlp_features)
                if sentence.nlp_features is not None
                else None
            )
            tokens = usable_tokens(analysis) if analysis is not None else None
            context = (
                previous_text
                if sentence.section_code is not None and sentence.section_code == previous_section
                else None
            )
            item = MiningItem(
                text=text,
                source_sentence_ids=[uuid4()],
                section_code=sentence.section_code,
                char_start=sentence.char_start,
                previous_text=context,
                tokens=tokens,
                locator=locator if tokens is not None else None,
            )
            reason = sentence_filter.reject_reason(item)
            if reason is not None:
                rejected[reason] += 1
                previous_text, previous_section = text, sentence.section_code
                continue
            filtered += 1
            labels: list[str] = []
            if sentence_filter.accepted_as_imperative(item):
                imperative_accepted += 1
                labels.append("imperative_accepted")
            report_reason = extractor.reporting.extractability_reason(text, tokens)
            if report_reason == "coordinated_reporting_verbs":
                coordinated_reporting += 1
                labels.append("coordinated_reporting")
            if labels:
                dump_records.append((",".join(labels), sentence.section_code, text))
            if pipeline.process([item]):
                extraction["EXTRACTED"] += 1
            else:
                extraction[report_reason or "other"] += 1
            previous_text, previous_section = text, sentence.section_code

    if dump_file is not None:
        if dump_guard is None:
            raise RuntimeError("manual-review dump is missing its directory guard")
        dump_file.write(
            "".join(
                f"[{label}; section={section_code or 'unclassified'}] {text}\n"
                for label, section_code, text in dump_records
            )
        )

    return {
        "files": len(files),
        "licenses_allowed_for_mining": licenses,
        "sentences": sentences,
        "filter_kept": filtered,
        "filter_rejections": dict(sorted(rejected.items())),
        "imperative_accepted": imperative_accepted,
        "extraction_reasons": dict(sorted(extraction.items())),
        "matches_per_construction": extractor.constructions.match_counts,
        "construction_rejections": extractor.constructions.rejection_counts,
        "coordinated_reporting_verbs": coordinated_reporting,
        "syntax_invalid_token_fallbacks": extractor.syntax_fallback_reasons.get(
            "syntax_invalid_tokens", 0
        ),
        "engine": engine.info.engine,
        "model_name": engine.info.model_name,
        "model_version": engine.info.model_version,
        "spacy_version": engine.info.spacy_version,
        "registry_version": policy.constructions.version,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--blob-root", type=Path)
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument(
        "--dump", type=Path, help="write manual-review sentences under worktree tmp/"
    )
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error("directory does not exist")
    try:
        print(
            json.dumps(
                trial_report(
                    args.directory,
                    blob_root=args.blob_root,
                    model=args.model,
                    dump=args.dump,
                ),
                ensure_ascii=False,
                indent=2,
            )
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
