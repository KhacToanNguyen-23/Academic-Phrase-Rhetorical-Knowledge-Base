from __future__ import annotations

from io import BytesIO

import pytest
from openpyxl import Workbook

from aprkb.modules.vocabulary.parsers import VocabularyParseError, parse_workbook
from aprkb.policies.loader import load_policy_bundle


def _xlsx(sheet: str, headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet
    worksheet.append(headers)
    for row in rows:
        worksheet.append(row)
    workbook.create_sheet("introduction")
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def test_detects_all_words_and_keeps_first_duplicate() -> None:
    headers = [
        "ID",
        "band",
        "status",
        "word",
        "Pos",
        "COCA-All",
        "COCA-Acad",
        "ratio",
        "disp",
        "range",
    ]
    content = _xlsx(
        "list",
        headers,
        [
            [1, 1, "y", "Alpha", "n", 10, 5, 1.2, 0.5, 4],
            [2, 1, "y", "alpha", "n", 20, 10, 2, 0.6, 5],
            [3, 1, "y", "Beta", "zz", 4, 2, 1, 0.2, 1],
        ],
    )
    parsed = parse_workbook(content, load_policy_bundle().vocabulary_import)
    assert parsed.source_kind == "all_words"
    assert parsed.rows_read == 3
    assert [row.word for row in parsed.lemmas] == ["alpha", "beta"]
    assert parsed.lemmas[0].coca_all == 10
    assert any("duplicate word/pos" in warning for warning in parsed.warnings)
    assert any("unknown pos code" in warning for warning in parsed.warnings)


def test_detects_acad_core_and_reads_duplicate_domain_headers_by_group() -> None:
    domains = ["HIS", "EDU", "SOC", "LAW", "HUM", "PHIL", "SCI", "MED", "BUS"]
    headers = [
        "ID",
        "word",
        "PoS",
        "COCA-All",
        "COCA-Acad",
        "ratio",
        "disp",
        "range",
        *domains,
        *domains,
    ]
    row = [
        7,
        "Gamma",
        "v",
        20,
        11,
        1.5,
        0.7,
        8,
        *range(10, 19),
        *[float(value) / 10 for value in range(1, 10)],
    ]
    parsed = parse_workbook(_xlsx("list", headers, [row]), load_policy_bundle().vocabulary_import)
    assert parsed.source_kind == "acad_core"
    assert parsed.lemmas[0].rank == 7
    assert [stat.freq for stat in parsed.domain_stats] == list(range(10, 19))
    assert [stat.relative_ratio for stat in parsed.domain_stats] == [
        value / 10 for value in range(1, 10)
    ]


def test_detects_families_and_maps_domain_aliases() -> None:
    headers = ["famRank", "family", "famFreq", "word", "PoS", "freq", "ratio", "categ", "domain"]
    content = _xlsx(
        "data",
        headers,
        [
            [1, "study", 100, "study", "n", 50, 1.1, "y", "Hum+Rel"],
            [1, "study", 100, "studies", "n", 30, 0.9, "x", "Fin"],
        ],
    )
    parsed = parse_workbook(content, load_policy_bundle().vocabulary_import)
    assert parsed.source_kind == "families"
    assert len(parsed.families) == 1
    assert parsed.members[0].domains == ("HUM", "PHIL")
    assert parsed.members[1].domains == ("BUS",)


def test_invalid_numeric_rows_are_skipped_and_missing_headers_are_reported() -> None:
    headers = [
        "ID",
        "band",
        "status",
        "word",
        "Pos",
        "COCA-All",
        "COCA-Acad",
        "ratio",
        "disp",
        "range",
    ]
    parsed = parse_workbook(
        _xlsx(
            "list",
            headers,
            [[1, 1, "y", "bad", "n", -2, 1, 1, 1, 1], [2, 1, "y", "text", "n", "nope", 1, 1, 1, 1]],
        ),
        load_policy_bundle().vocabulary_import,
    )
    assert parsed.skipped == 2
    assert parsed.lemmas == []
    with pytest.raises(VocabularyParseError, match="band"):
        parse_workbook(
            _xlsx("list", ["ID", "word"], [[1, "x"]]), load_policy_bundle().vocabulary_import
        )


def test_invalid_bytes_raise_vocabulary_parse_error() -> None:
    with pytest.raises(VocabularyParseError):
        parse_workbook(b"not an xlsx", load_policy_bundle().vocabulary_import)
