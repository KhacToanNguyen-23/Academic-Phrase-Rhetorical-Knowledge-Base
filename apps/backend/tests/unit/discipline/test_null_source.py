"""Unit tests for the discipline domain."""

from aprkb.modules.discipline.null_source import NullDisciplineSource
from aprkb.modules.journals.fingerprint import JournalFingerprintService


def test_null_discipline_source_and_fingerprint_remain_stubs():
    journal = object()

    assert NullDisciplineSource().classify_journal(journal) is None
    assert JournalFingerprintService().compute(journal) is None
