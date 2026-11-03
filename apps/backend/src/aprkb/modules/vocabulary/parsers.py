"""Pure Excel parsing for the Academic Vocabulary List sources."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from io import BytesIO
from typing import Literal, cast
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from aprkb.policies.schemas import VocabularyImportPolicy, VocabularySourceProfile

SourceKind = Literal["all_words", "acad_core", "families"]


@dataclass(frozen=True)
class LemmaRow:
    word: str
    pos: str
    rank: int | None
    band: int | None
    status: str | None
    coca_all: int | None
    coca_acad: int | None
    ratio: float | None
    disp: float | None
    range: int | None


@dataclass(frozen=True)
class DomainStatRow:
    word: str
    pos: str
    domain: str
    freq: int
    relative_ratio: float


@dataclass(frozen=True)
class FamilyRow:
    headword: str
    rank: int
    family_freq: int


@dataclass(frozen=True)
class MemberRow:
    headword: str
    word: str
    pos: str
    freq: int
    category: str
    domains: tuple[str, ...]


@dataclass(frozen=True)
class ParsedWorkbook:
    source_kind: SourceKind
    rows_read: int
    lemmas: list[LemmaRow]
    domain_stats: list[DomainStatRow]
    families: list[FamilyRow]
    members: list[MemberRow]
    warnings: list[str]
    skipped: int


class VocabularyParseError(ValueError):
    """Raised when an uploaded workbook cannot be identified or parsed."""

    def __init__(self, message: str, missing_columns: list[str] | None = None) -> None:
        super().__init__(message)
        self.missing_columns = missing_columns or []


def _headers(workbook: object, sheet: str) -> list[str] | None:
    worksheet = getattr(workbook, "worksheets", [])
    sheet_by_name = next((item for item in worksheet if item.title == sheet), None)
    if sheet_by_name is None:
        return None
    row = next(sheet_by_name.iter_rows(values_only=True), ())
    return [str(value).strip() for value in row]


def detect_source(workbook: object, policy: VocabularyImportPolicy) -> SourceKind:
    """Identify a workbook by sheet name and its required first-row headers."""
    candidates: list[tuple[int, str, list[str]]] = []
    for name, profile in policy.sources.items():
        headers = _headers(workbook, profile.sheet)
        missing = (
            list(profile.required_headers)
            if headers is None
            else [header for header in profile.required_headers if header not in headers]
        )
        if not missing:
            return cast(SourceKind, name)
        candidates.append((len(missing), name, missing))
    closest = min(candidates, default=(0, "none", []))
    missing_text = ", ".join(closest[2]) or "sheet/header row"
    raise VocabularyParseError(
        f"Workbook did not match a vocabulary source; closest profile "
        f"{closest[1]} is missing: {missing_text}",
        closest[2],
    )


def _column_indices(headers: list[str], name: str) -> list[int]:
    return [index for index, header in enumerate(headers) if header == name]


def _index_map(headers: list[str], profile: VocabularySourceProfile) -> dict[str, int]:
    positions: dict[str, int] = {}
    for field, header in profile.columns.items():
        matches = _column_indices(headers, header)
        if not matches:
            raise VocabularyParseError(f"Missing required column: {header}", [header])
        positions[field] = matches[0]
    return positions


def _cell(row: tuple[object, ...], positions: dict[str, int], field: str) -> object:
    index = positions[field]
    return row[index] if index < len(row) else None


def _text(value: object) -> str:
    return "" if value is None else str(value).strip()


def _number(value: object, *, integer: bool, field: str) -> int | float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        number = float(str(value))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be numeric") from error
    if number < 0:
        raise ValueError(f"{field} must not be negative")
    if integer:
        if not number.is_integer():
            raise ValueError(f"{field} must be an integer")
        return int(number)
    return number


def _required_number(
    row: tuple[object, ...], positions: dict[str, int], field: str, *, integer: bool
) -> int | float:
    value = _number(_cell(row, positions, field), integer=integer, field=field)
    if value is None:
        raise ValueError(f"{field} is required")
    return value


def _header_and_rows(
    rows: Iterable[tuple[object, ...]],
) -> tuple[list[str], Iterator[tuple[object, ...]]]:
    iterator = iter(rows)
    try:
        header_row = next(iterator)
    except StopIteration as error:
        raise VocabularyParseError("Workbook sheet is empty") from error
    return [str(value).strip() for value in header_row], iterator


class _WarningCollector:
    def __init__(self) -> None:
        self.values: list[str] = []
        self.seen_codes: set[tuple[str, str]] = set()

    def add(self, message: str) -> None:
        self.values.append(message)

    def add_code_once(self, kind: str, code: str, message: str) -> None:
        marker = (kind, code)
        if marker not in self.seen_codes:
            self.seen_codes.add(marker)
            self.add(message)

    def result(self) -> list[str]:
        if len(self.values) <= 50:
            return self.values
        return [*self.values[:49], f"... and {len(self.values) - 49} more"]


def _normalize_domains(
    raw: str, policy: VocabularyImportPolicy, warnings: _WarningCollector
) -> tuple[str, ...]:
    domains: list[str] = []
    for value in (part.strip() for part in raw.split("+") if part.strip()):
        mapped = policy.family_domain_aliases.get(value, value.upper())
        if mapped not in policy.domain_codes:
            warnings.add_code_once(
                "domain", value, f"unknown family domain code {value!r}; kept as {mapped!r}"
            )
        if mapped not in domains:
            domains.append(mapped)
    return tuple(domains)


def _warn_unknown(
    value: str, kind: str, policy: VocabularyImportPolicy, warnings: _WarningCollector
) -> None:
    if value and value not in getattr(policy.labels, kind):
        warnings.add_code_once(kind, value, f"unknown {kind} code {value!r}; kept unchanged")


def _parse_all_words(
    rows: Iterable[tuple[object, ...]],
    profile: VocabularySourceProfile,
    policy: VocabularyImportPolicy,
) -> ParsedWorkbook:
    headers, data_rows = _header_and_rows(rows)
    positions = _index_map(headers, profile)
    warnings = _WarningCollector()
    lemmas: list[LemmaRow] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    rows_read = 0
    numeric_fields = {
        "rank": True,
        "band": True,
        "coca_all": True,
        "coca_acad": True,
        "ratio": False,
        "disp": False,
        "range": True,
    }
    for row_number, row in enumerate(data_rows, start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        rows_read += 1
        word = _text(_cell(row, positions, "word")).lower()
        if not word:
            continue
        pos = _text(_cell(row, positions, "pos")).lower()
        key = (word, pos)
        if key in seen:
            warnings.add(f"duplicate word/pos at row {row_number} kept first")
            continue
        try:
            numbers = {
                field: _number(_cell(row, positions, field), integer=integer, field=field)
                for field, integer in numeric_fields.items()
            }
        except ValueError as error:
            skipped += 1
            warnings.add(f"row {row_number}: {error}")
            continue
        seen.add(key)
        status = _text(_cell(row, positions, "status")).lower() or None
        _warn_unknown(pos, "pos", policy, warnings)
        _warn_unknown(status or "", "status", policy, warnings)
        lemmas.append(
            LemmaRow(
                word,
                pos,
                cast(int | None, numbers["rank"]),
                cast(int | None, numbers["band"]),
                status,
                cast(int | None, numbers["coca_all"]),
                cast(int | None, numbers["coca_acad"]),
                cast(float | None, numbers["ratio"]),
                cast(float | None, numbers["disp"]),
                cast(int | None, numbers["range"]),
            )
        )
    return ParsedWorkbook("all_words", rows_read, lemmas, [], [], [], warnings.result(), skipped)


def _parse_acad_core(
    rows: Iterable[tuple[object, ...]],
    profile: VocabularySourceProfile,
    policy: VocabularyImportPolicy,
) -> ParsedWorkbook:
    headers, data_rows = _header_and_rows(rows)
    positions = _index_map(headers, profile)
    warnings = _WarningCollector()
    lemmas: list[LemmaRow] = []
    stats: list[DomainStatRow] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    rows_read = 0
    domains = policy.domain_codes
    for row_number, row in enumerate(data_rows, start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        rows_read += 1
        word = _text(_cell(row, positions, "word")).lower()
        if not word:
            continue
        pos = _text(_cell(row, positions, "pos")).lower()
        key = (word, pos)
        if key in seen:
            warnings.add(f"duplicate word/pos at row {row_number} kept first")
            continue
        try:
            rank = _required_number(row, positions, "rank", integer=True)
            coca_all = _required_number(row, positions, "coca_all", integer=True)
            coca_acad = _required_number(row, positions, "coca_acad", integer=True)
            ratio = _required_number(row, positions, "ratio", integer=False)
            disp = _required_number(row, positions, "disp", integer=False)
            domain_range = _required_number(row, positions, "range", integer=True)
            domain_values: list[tuple[int, float]] = []
            for domain in domains:
                index_list = _column_indices(headers, profile.columns[f"domain_{domain}"])
                if len(index_list) < 2:
                    raise VocabularyParseError(
                        f"Column {domain} must occur twice for acad_core freq/ratio", [domain]
                    )
                freq = _number(
                    row[index_list[0]] if index_list[0] < len(row) else None,
                    integer=True,
                    field=f"{domain} freq",
                )
                relative_ratio = _number(
                    row[index_list[1]] if index_list[1] < len(row) else None,
                    integer=False,
                    field=f"{domain} ratio",
                )
                if freq is None or relative_ratio is None:
                    raise ValueError(f"{domain} freq and ratio are required")
                domain_values.append((int(freq), float(relative_ratio)))
        except ValueError as error:
            skipped += 1
            warnings.add(f"row {row_number}: {error}")
            continue
        seen.add(key)
        _warn_unknown(pos, "pos", policy, warnings)
        lemmas.append(
            LemmaRow(
                word,
                pos,
                int(rank),
                None,
                None,
                int(coca_all),
                int(coca_acad),
                float(ratio),
                float(disp),
                int(domain_range),
            )
        )
        stats.extend(
            DomainStatRow(word, pos, domain, freq, relative_ratio)
            for domain, (freq, relative_ratio) in zip(domains, domain_values, strict=True)
        )
    return ParsedWorkbook("acad_core", rows_read, lemmas, stats, [], [], warnings.result(), skipped)


def _parse_families(
    rows: Iterable[tuple[object, ...]],
    profile: VocabularySourceProfile,
    policy: VocabularyImportPolicy,
) -> ParsedWorkbook:
    headers, data_rows = _header_and_rows(rows)
    positions = _index_map(headers, profile)
    warnings = _WarningCollector()
    families: list[FamilyRow] = []
    members: list[MemberRow] = []
    seen_families: set[str] = set()
    seen_members: set[tuple[str, str, str]] = set()
    skipped = 0
    rows_read = 0
    for row_number, row in enumerate(data_rows, start=2):
        if not any(value is not None and str(value).strip() for value in row):
            continue
        rows_read += 1
        headword = _text(_cell(row, positions, "headword")).lower()
        word = _text(_cell(row, positions, "word")).lower()
        if not headword or not word:
            continue
        pos = _text(_cell(row, positions, "pos")).lower()
        key = (headword, word, pos)
        if key in seen_members:
            warnings.add(f"duplicate word/pos at row {row_number} kept first")
            continue
        try:
            rank = _required_number(row, positions, "rank", integer=True)
            family_freq = _required_number(row, positions, "family_freq", integer=True)
            freq = _required_number(row, positions, "freq", integer=True)
            ratio = _number(_cell(row, positions, "ratio"), integer=False, field="ratio")
            if ratio is None:
                raise ValueError("ratio is required")
        except ValueError as error:
            skipped += 1
            warnings.add(f"row {row_number}: {error}")
            continue
        category = _text(_cell(row, positions, "category")).lower()
        _warn_unknown(pos, "pos", policy, warnings)
        _warn_unknown(category, "category", policy, warnings)
        if headword not in seen_families:
            seen_families.add(headword)
            families.append(FamilyRow(headword, int(rank), int(family_freq)))
        seen_members.add(key)
        domains = _normalize_domains(_text(_cell(row, positions, "domains")), policy, warnings)
        members.append(MemberRow(headword, word, pos, int(freq), category, domains))
    return ParsedWorkbook(
        "families", rows_read, [], [], families, members, warnings.result(), skipped
    )


def parse_workbook(content: bytes, policy: VocabularyImportPolicy) -> ParsedWorkbook:
    """Parse one workbook according to the versioned vocabulary policy."""
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (BadZipFile, InvalidFileException, OSError, ValueError) as error:
        raise VocabularyParseError("Uploaded content is not a valid .xlsx workbook") from error
    try:
        source_kind = detect_source(workbook, policy)
        profile = policy.sources[source_kind]
        worksheet = workbook[profile.sheet]
        rows = worksheet.iter_rows(values_only=True)
        if source_kind == "all_words":
            return _parse_all_words(rows, profile, policy)
        if source_kind == "acad_core":
            return _parse_acad_core(rows, profile, policy)
        return _parse_families(rows, profile, policy)
    finally:
        workbook.close()
