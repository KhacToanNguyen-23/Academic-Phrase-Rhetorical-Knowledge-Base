import pytest
from pydantic import ValidationError

from aprkb.modules.corpus.schemas import (
    DEFAULT_ARTIFACT_KINDS,
    ImportProfileCreate,
    SlrWorkFilters,
)


def test_work_filters_reject_unknown_keys_and_invalid_years() -> None:
    with pytest.raises(ValidationError):
        SlrWorkFilters.model_validate({"limit": 1})
    with pytest.raises(ValidationError):
        SlrWorkFilters.model_validate({"year_from": 2020})
    with pytest.raises(ValidationError):
        SlrWorkFilters.model_validate({"yearFrom": 2025, "yearTo": 2020})


def test_issn_is_normalized_and_validated() -> None:
    assert SlrWorkFilters.model_validate({"journalIssn": "1234-567X"}).journal_issn == "1234567X"
    with pytest.raises(ValidationError):
        SlrWorkFilters.model_validate({"journalIssn": "123456"})


def test_profile_rejects_empty_duplicate_artifacts_and_out_of_range_limit() -> None:
    for payload in (
        {"name": "empty", "artifact_kinds": []},
        {"name": "duplicate", "artifact_kinds": ["SOURCE_PDF", "SOURCE_PDF"]},
        {"name": "limit", "batch_limit": 101},
    ):
        with pytest.raises(ValidationError):
            ImportProfileCreate.model_validate(payload)
    assert ImportProfileCreate(name="default").artifact_kinds == list(DEFAULT_ARTIFACT_KINDS)
