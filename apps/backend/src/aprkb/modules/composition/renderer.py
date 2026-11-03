"""FR-02.1 / FR-07.5 / BR-02 slot renderer.

Insert declared slot values literally, preserve missing placeholders, and
never invent values.
"""

import re
from collections.abc import Mapping


class SlotValidationError(ValueError):
    """A render validation error associated with one or more slot fields."""

    def __init__(self, field_errors: dict[str, str]) -> None:
        self.field_errors = field_errors
        super().__init__("One or more slot values are invalid")


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

    field_errors: dict[str, str] = {}
    for name, definition in schema.items():
        if isinstance(definition, str):
            required = True
            min_length = 1
        elif isinstance(definition, dict):
            required = definition.get("required", True)
            min_length = definition.get("min_length", 1)
            if (
                not isinstance(required, bool)
                or not isinstance(min_length, int)
                or isinstance(min_length, bool)
                or min_length < 1
            ):
                raise ValueError("Pattern has an invalid slot definition")
        else:
            raise ValueError("Pattern has an invalid slot definition")

        value = values.get(name, "").strip()
        if not value and required:
            field_errors[name] = "This field is required."
        elif value and len(value) < min_length:
            field_errors[name] = f"Enter at least {min_length} characters."
    if field_errors:
        raise SlotValidationError(field_errors)

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
