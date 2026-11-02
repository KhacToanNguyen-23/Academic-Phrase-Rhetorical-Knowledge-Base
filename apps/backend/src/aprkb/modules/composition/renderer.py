"""FR-02.1 / FR-07.5 / BR-02 slot renderer.

Insert declared slot values literally, preserve missing placeholders, and
never invent values.
"""

import re
from collections.abc import Mapping

SLOT = re.compile(r"\{([A-Za-z][A-Za-z0-9_]*)\}")


def render_frame(
    frame: str, schema: Mapping[str, object], values: Mapping[str, str]
) -> tuple[str, list[str]]:
    placeholders = set(SLOT.findall(frame))
    if placeholders != set(schema):
        raise ValueError("Pattern frame and slot schema do not match")
    if set(values) - placeholders:
        raise ValueError("Unknown slot name")
    for definition in schema.values():
        slot_type = (
            definition
            if isinstance(definition, str)
            else (definition.get("type") if isinstance(definition, dict) else None)
        )
        if not isinstance(slot_type, str) or not slot_type.strip():
            raise ValueError("Pattern has an invalid slot type")

    unfilled: list[str] = []

    def substitute(match: re.Match[str]) -> str:
        name = match.group(1)
        value = values.get(name, "")
        if not value.strip():
            if name not in unfilled:
                unfilled.append(name)
            return match.group(0)
        return value

    return SLOT.sub(substitute, frame), unfilled
