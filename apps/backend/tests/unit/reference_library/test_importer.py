"""Parser tests use invented text only."""

import json

import pytest

from aprkb.modules.reference_library.importer import parse_document


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
