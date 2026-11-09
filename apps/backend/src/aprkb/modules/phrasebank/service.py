"""One manifest coordinates existing Phrasebank import contracts."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from aprkb.modules.pack.service import import_pack
from aprkb.modules.reference_library.importer import import_library, load_document
from aprkb.modules.reference_library.mapping import import_mapping_file


class PhrasebankInit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1"]
    pattern_pack: str = Field(min_length=1)
    reference_library: str = Field(min_length=1)
    reference_mappings: str = Field(min_length=1)


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
    pack_path = _input_path(root, manifest.pattern_pack)
    library_path = _input_path(root, manifest.reference_library)
    mappings_path = _input_path(root, manifest.reference_mappings)
    library = load_document(library_path)
    if not mappings_path.is_file():
        raise ValueError("Reference mappings file does not exist")
    try:
        report, patterns = await import_pack(session, pack_path)
        if report.has_errors:
            findings = "; ".join(
                f"{finding.code} {finding.path}: {finding.message}"
                for finding in report.findings
                if finding.severity == "error"
            )
            raise ValueError(f"Pattern pack rejected: {findings}")
        references = await import_library(
            session, library, request_id="cli-phrasebank-init", commit=False, seed_mappings=False
        )
        mappings = await import_mapping_file(
            session, mappings_path, commit=False, source_name=library.source_name
        )
        result: dict[str, object] = {
            "patterns": patterns,
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
