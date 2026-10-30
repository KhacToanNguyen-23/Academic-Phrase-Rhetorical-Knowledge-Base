"""AT-12: writer role cannot publish and unauthorized attempts are auditable."""

import pytest


@pytest.mark.skip(
    reason="TODO(owner): writer-to-publisher mapping and denied-attempt audit are unspecified"
)
def test_at_12_writer_publish_is_denied_and_audited() -> None:
    """TODO(owner): preserve the exact role and denial-audit rule from the source PRD."""
