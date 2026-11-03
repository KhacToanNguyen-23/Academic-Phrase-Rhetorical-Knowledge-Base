"""Parser tests use invented text only."""

import json
from pathlib import Path

import pytest
import yaml

from aprkb.modules.reference_library.importer import parse_document
from aprkb.seeds.load import SEED_DIR


def sample_document():
    return {
        "source": "Example University Phrase Library",
        "status": "quarantined",
        "license_status": "unknown",
        "page_count": 2,
        "block_count": 3,
        "table_count": 1,
        "pages": [
            {
                "title": "Introducing work",
                "source_url": "https://example.test/introducing-work/",
                "resolved_url": "https://example.test/introducing-work/",
                "captured_at": "2026-01-01",
                "html_sha256": "a" * 64,
                "source_category": "external_reference",
                "license_status": "unknown",
                "rights_status": "unverified",
                "status": "quarantined",
                "note": "Internal test fixture",
                "blocks": [
                    {
                        "block_id": "p1",
                        "heading": "Introducing work",
                        "kind": "paragraph",
                        "lines": ["Alpha beta gamma"],
                    },
                    {
                        "block_id": "t1",
                        "heading": "A heading",
                        "kind": "table",
                        "rows": [["Alpha\nBeta", "gamma", "delta"]],
                    },
                ],
            },
            {
                "title": "Giving examples",
                "source_url": "https://example.test/giving-examples/",
                "resolved_url": "https://example.test/giving-examples/",
                "captured_at": "2026-01-01",
                "html_sha256": "b" * 64,
                "source_category": "external_reference",
                "license_status": "unknown",
                "rights_status": "unverified",
                "status": "quarantined",
                "note": "Internal test fixture",
                "blocks": [
                    {
                        "block_id": "p2",
                        "heading": "Giving examples",
                        "kind": "paragraph",
                        "lines": ["Delta epsilon"],
                    },
                ],
            },
        ],
    }


def test_parser_maps_sections_and_functions_and_alternatives() -> None:
    raw = json.dumps(sample_document()).encode()
    library = parse_document(json.loads(raw), raw)

    assert [category.kind for category in library.categories] == ["section", "function"]
    assert library.categories[0].entries[0].text == "Alpha beta gamma"
    assert library.categories[0].entries[1].cells == [["Alpha", "Beta"], ["gamma"], ["delta"]]
    assert library.categories[0].entries[1].search_text == "Alpha Beta gamma delta"
    assert [entry.block_index for entry in library.categories[0].entries] == [0, 1]
    assert [entry.block_id for entry in library.categories[0].entries] == ["p1", "t1"]
    assert library.categories[0].resolved_url == "https://example.test/introducing-work/"
    assert library.categories[0].captured_at == "2026-01-01"
    assert library.categories[0].html_sha256 == "a" * 64
    assert library.categories[0].source_category == "external_reference"
    assert library.categories[0].license_status == "unknown"
    assert library.categories[0].rights_status == "unverified"
    assert library.categories[0].status == "quarantined"
    assert library.categories[0].note == "Internal test fixture"
    assert library.categories[0].extraction_method is None
    assert library.table_count == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data.update(page_count=9),
        lambda data: data["pages"][0]["blocks"][0].update(heading="Wrong heading"),
        lambda data: data["pages"][0]["blocks"][1]["rows"].__setitem__(0, ["one"]),
    ],
)
def test_parser_rejects_invalid_structure(mutate) -> None:
    data = sample_document()
    mutate(data)
    raw = json.dumps(data).encode()

    with pytest.raises(ValueError):
        parse_document(data, raw)


def test_parser_accepts_optional_extraction_method_and_integer_block_ids() -> None:
    data = sample_document()
    for number, page in enumerate(data["pages"], start=1):
        page["extraction_method"] = "fixture"
        for block in page["blocks"]:
            block["block_id"] = number
    raw = json.dumps(data).encode()

    library = parse_document(json.loads(raw), raw)

    assert [len(category.entries) for category in library.categories] == [2, 1]
    assert library.categories[0].entries[0].block_id == 1


@pytest.mark.parametrize(
    "field,value",
    [("captured_at", "not-a-date"), ("html_sha256", "bad-hash")],
)
def test_parser_rejects_invalid_page_provenance(field: str, value: str) -> None:
    data = sample_document()
    data["pages"][0][field] = value
    raw = json.dumps(data).encode()
    with pytest.raises(ValueError):
        parse_document(data, raw)


def test_seed_mapping_uses_only_existing_section_codes() -> None:
    module_path = Path(__file__).resolve().parents[3]
    configured = yaml.safe_load(
        (module_path / "src/aprkb/modules/reference_library/taxonomy-mapping.yaml").read_text(
            encoding="utf-8"
        )
    )
    taxonomy = json.loads((SEED_DIR / "taxonomy.json").read_text(encoding="utf-8"))
    valid_sections = {item["code"] for item in taxonomy["sections"]}
    assert all(
        item["target_kind"] == "section" and item["target_code"] in valid_sections
        for item in configured["mappings"]
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: data["pages"][0].update(unexpected="x"),
        lambda data: data["pages"][0].update(extraction_method=""),
        lambda data: data["pages"][0]["blocks"][0].update(block_id=True),
        lambda data: data["pages"][0]["blocks"][0].update(block_id=-1),
        lambda data: data["pages"][0]["blocks"][0].update(block_id=1.5),
    ],
)
def test_parser_still_rejects_unknown_page_keys_and_bad_block_ids(mutate) -> None:
    data = sample_document()
    mutate(data)
    raw = json.dumps(data).encode()

    with pytest.raises(ValueError):
        parse_document(data, raw)
