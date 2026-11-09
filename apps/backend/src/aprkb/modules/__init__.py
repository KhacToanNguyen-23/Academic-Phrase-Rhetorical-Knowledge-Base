"""Domain modules and SQLAlchemy model registration."""


def load_models() -> None:
    """Import every domain model module so Alembic sees its tables."""
    from importlib import import_module

    for domain in (
        "audit",
        "corpus",
        "extraction",
        "identity",
        "journals",
        "mining",
        "patterns",
        "academic_phrase_bank",
        "recommendation",
        "reference_library",
        "taxonomy",
        "vocabulary",
    ):
        import_module(f"aprkb.modules.{domain}.models")
    import_module("aprkb.shared.models")
