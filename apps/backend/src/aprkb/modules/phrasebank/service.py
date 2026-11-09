"""One manifest coordinates existing Phrasebank import contracts."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.pack.service import import_pack
from aprkb.modules.reference_library.importer import import_library, load_document
from aprkb.modules.reference_library.mapping import import_mapping_file


class PhrasebankInit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1"]
    pattern_pack: str | None = Field(default=None, min_length=1)
    pattern_seed: str | None = Field(default=None, min_length=1)
    academic_phrases: str | None = Field(default=None, min_length=1)
    reference_library: str | None = Field(default=None, min_length=1)
    reference_mappings: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def sources_are_well_formed(self) -> "PhrasebankInit":
        if bool(self.pattern_pack) == bool(self.pattern_seed):
            raise ValueError("Supply exactly one of pattern_pack or pattern_seed")
        if bool(self.reference_library) != bool(self.reference_mappings):
            raise ValueError("reference_library and reference_mappings must be supplied together")
        return self


def _input_path(root: Path, value: str) -> Path:
    relative = Path(value)
    resolved = (root / relative).resolve()
    if relative.is_absolute() or not resolved.is_relative_to(root):
        raise ValueError("Phrasebank input paths must stay inside the manifest directory")
    return resolved


async def initialize_phrasebank(
    session: AsyncSession, path: Path, *, dry_run: bool = False
) -> dict[str, object]:
    """Import both sources and mappings atomically, or roll back the entire preview.

    Call with a fresh session; this function owns its transaction. Reference
    taxonomy must already be initialized. Existing standalone importers retain
    their commit behavior when called without the new transaction option.
    """
    path = path.resolve()
    manifest = PhrasebankInit.model_validate_json(path.read_text(encoding="utf-8"))
    root = path.parent
    pack_path = _input_path(root, manifest.pattern_pack) if manifest.pattern_pack else None
    pattern_seed_path = _input_path(root, manifest.pattern_seed) if manifest.pattern_seed else None
    academic_path = (
        _input_path(root, manifest.academic_phrases) if manifest.academic_phrases else None
    )
    library_path = (
        _input_path(root, manifest.reference_library) if manifest.reference_library else None
    )
    mappings_path = (
        _input_path(root, manifest.reference_mappings) if manifest.reference_mappings else None
    )
    library = load_document(library_path) if library_path else None
    if mappings_path is not None and not mappings_path.is_file():
        raise ValueError("Reference mappings file does not exist")
    if academic_path is not None and not academic_path.is_file():
        raise ValueError("Academic Phrase Bank source file does not exist")
    if pattern_seed_path is not None and not pattern_seed_path.is_file():
        raise ValueError("AP-RKB pattern seed file does not exist")
    try:
        if pack_path is not None:
            report, patterns = await import_pack(session, pack_path)
            if report.has_errors:
                findings = "; ".join(
                    f"{finding.code} {finding.path}: {finding.message}"
                    for finding in report.findings
                    if finding.severity == "error"
                )
                raise ValueError(f"Pattern pack rejected: {findings}")
        else:
            from aprkb.seeds.load import import_pattern_seed

            assert pattern_seed_path is not None
            patterns = await import_pattern_seed(session, pattern_seed_path)
        academic_phrase_count = 0
        if academic_path is not None:
            from aprkb.seeds.load import import_academic_phrases

            academic_phrase_count = await import_academic_phrases(session, academic_path)
        references: dict[str, int] = {"categories": 0, "entries": 0}
        mappings = 0
        if library is not None and mappings_path is not None:
            references = await import_library(
                session,
                library,
                request_id="cli-phrasebank-init",
                commit=False,
                seed_mappings=False,
            )
            mappings = await import_mapping_file(
                session, mappings_path, commit=False, source_name=library.source_name
            )
        result: dict[str, object] = {
            "patterns": patterns,
            "academic_phrases": {"records": academic_phrase_count},
            "reference_library": references,
            "reference_mappings": mappings,
            "dry_run": dry_run,
        }
        if dry_run:
            await session.rollback()
        else:
            await session.commit()
        return result
    except BaseException:
        await session.rollback()
        raise
