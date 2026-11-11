"""The deploy initializer runs in a fresh interpreter; its measurement step must resolve FKs."""

import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]

# Mirrors `python -m aprkb.seeds.load`: only the seed module is imported, never the API app.
SCRIPT = """
import aprkb.seeds.load as seed
from aprkb.modules import load_models
from aprkb.modules.measurement.models import MeasurementImportRun, MeasurementSlotLink

load_models()  # what seed_measurement_catalog() does before writing
for table in (MeasurementImportRun.__table__, MeasurementSlotLink.__table__):
    for fk in table.foreign_keys:
        fk.column  # raises NoReferencedTableError if a target table is unregistered
assert seed.SEED_DIR is not None and (seed.SEED_DIR / "measurement_catalog.json").is_file()
print("ok")
"""


def test_seed_entrypoint_registers_all_tables_for_measurement_writes():
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(BACKEND / "src"), **_inherited_env()},
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip().endswith("ok")


def test_seed_calls_load_models_before_writing():
    source = (BACKEND / "src/aprkb/seeds/load.py").read_text(encoding="utf-8")
    body = source[source.index("async def seed_measurement_catalog") :]
    assert body.index("load_models()") < body.index("await import_catalog(")


def _inherited_env() -> dict[str, str]:
    import os

    return {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
