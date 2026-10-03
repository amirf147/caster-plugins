# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Option types, definitions, and validation logic for configurable plugin parameters.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union


class OptionType(str, Enum):
    """Supported data types for declarative plugin configuration options."""
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    CHOICE = "choice"
    PATH = "path"


@dataclass(frozen=True)
class OptionDefinition:
    """
    Immutable specification of a single configurable parameter declared in metadata.toml.
    """
    name: str
    option_type: OptionType
    default: Any
    description: str = ""
    choices: List[str] = field(default_factory=list)
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    step: Optional[Union[int, float]] = None

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> "OptionDefinition":
        """Constructs an OptionDefinition from a dictionary parsed from TOML."""
        raw_type = str(data.get("type", "string")).lower()
        try:
            opt_type = OptionType(raw_type)
        except ValueError:
            opt_type = OptionType.STRING

        default_val = data.get("default")
        desc = str(data.get("description", ""))
        choices = list(data.get("choices", []))
        min_val = data.get("min")
        max_val = data.get("max")
        step_val = data.get("step")

        # Type-coerce defaults if needed
        if opt_type == OptionType.BOOL and default_val is not None:
            default_val = bool(default_val)
        elif opt_type == OptionType.INT and default_val is not None:
            default_val = int(default_val)
        elif opt_type == OptionType.FLOAT and default_val is not None:
            default_val = float(default_val)
        elif opt_type == OptionType.STRING and default_val is not None:
            default_val = str(default_val)
        elif opt_type == OptionType.CHOICE and default_val is not None:
            default_val = str(default_val)
        elif opt_type == OptionType.PATH and default_val is not None:
            default_val = str(default_val)

        return cls(
            name=name,
            option_type=opt_type,
            default=default_val,
            description=desc,
            choices=choices,
            min_value=min_val,
            max_value=max_val,
            step=step_val,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serializes definition to dictionary representation."""
        return {
            "name": self.name,
            "type": self.option_type.value,
            "default": self.default,
            "description": self.description,
            "choices": list(self.choices),
            "min": self.min_value,
            "max": self.max_value,
            "step": self.step,
        }


def validate_and_coerce(definition: OptionDefinition, raw_value: Any) -> Tuple[bool, Any, Optional[str]]:
    """
    Validates a raw value against an OptionDefinition and coerces it into the target Python type.
    Returns: (is_valid, coerced_value, error_message)
    """
    if raw_value is None:
        return True, definition.default, None

    opt_type = definition.option_type

    if opt_type == OptionType.BOOL:
        if isinstance(raw_value, bool):
            return True, raw_value, None
        if isinstance(raw_value, str):
            if raw_value.lower() in ("true", "1", "yes", "on"):
                return True, True, None
            if raw_value.lower() in ("false", "0", "no", "off"):
                return True, False, None
        if isinstance(raw_value, (int, float)):
            return True, bool(raw_value), None
        return False, definition.default, f"Expected boolean for option '{definition.name}'."

    elif opt_type == OptionType.INT:
        try:
            val = int(raw_value)
        except (ValueError, TypeError):
            return False, definition.default, f"Value '{raw_value}' is not a valid integer for '{definition.name}'."

        if definition.min_value is not None and val < definition.min_value:
            return False, definition.default, f"Value {val} is below minimum {definition.min_value} for '{definition.name}'."
        if definition.max_value is not None and val > definition.max_value:
            return False, definition.default, f"Value {val} exceeds maximum {definition.max_value} for '{definition.name}'."
        return True, val, None

    elif opt_type == OptionType.FLOAT:
        try:
            val = float(raw_value)
        except (ValueError, TypeError):
            return False, definition.default, f"Value '{raw_value}' is not a valid float for '{definition.name}'."

        if definition.min_value is not None and val < definition.min_value:
            return False, definition.default, f"Value {val} is below minimum {definition.min_value} for '{definition.name}'."
        if definition.max_value is not None and val > definition.max_value:
            return False, definition.default, f"Value {val} exceeds maximum {definition.max_value} for '{definition.name}'."
        return True, val, None

    elif opt_type == OptionType.CHOICE:
        val_str = str(raw_value)
        if definition.choices and val_str not in definition.choices:
            return False, definition.default, f"Value '{val_str}' not in valid choices {definition.choices} for '{definition.name}'."
        return True, val_str, None

    elif opt_type == OptionType.PATH:
        val_str = str(raw_value).strip()
        return True, val_str, None

    elif opt_type == OptionType.STRING:
        return True, str(raw_value), None

    return True, raw_value, None
