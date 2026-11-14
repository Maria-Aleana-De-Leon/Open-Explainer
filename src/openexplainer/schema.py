"""A tiny declarative validator that reports every problem at once (no third-party schema library).

Spec mini-language:
    {"type": "object", "fields": {name: spec}, "required": [...], "extra": False}
    {"type": "array", "items": spec, "min": 1}
    {"type": "string", "enum": [...], "pattern": regex}
    {"type": "number", "min": 0, "max": 10}   {"type": "integer"}   {"type": "boolean"}
    {"type": ["string", "number"]}            {"any": True}
Defaults are applied by the caller (config.py), not here.
"""
from __future__ import annotations

import re

_TYPES = {
    "object": dict, "array": list, "string": str, "boolean": bool,
    "number": (int, float), "integer": int, "null": type(None),
}


def _is(value, t: str) -> bool:
    if t in ("number", "integer") and isinstance(value, bool):
        return False
    return isinstance(value, _TYPES[t])


def check(value, spec: dict, path: str = "$") -> list[str]:
    if spec.get("any"):
        return []
    types = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
    if not any(_is(value, t) for t in types):
        got = type(value).__name__
        return [f"{path}: expected {' or '.join(types)}, got {got} ({value!r})"[:200]]
    out: list[str] = []
    if isinstance(value, dict) and "fields" in spec:
        for r in spec.get("required", []):
            if r not in value:
                out.append(f"{path}: missing required field '{r}'")
        for k, v in value.items():
            if k in spec["fields"]:
                out += check(v, spec["fields"][k], f"{path}.{k}")
            elif not spec.get("extra", False):
                close = [f for f in spec["fields"] if f.lower().startswith(k.lower()[:3])]
                hint = f" (did you mean '{close[0]}'?)" if close else ""
                out.append(f"{path}: unknown field '{k}'{hint}; allowed: {', '.join(spec['fields'])}")
    if isinstance(value, list):
        if len(value) < spec.get("min", 0):
            out.append(f"{path}: needs at least {spec['min']} item(s)")
        if "items" in spec:
            for i, v in enumerate(value):
                out += check(v, spec["items"], f"{path}[{i}]")
    if isinstance(value, str):
        if "enum" in spec and value not in spec["enum"]:
            out.append(f"{path}: '{value}' is not one of {spec['enum']}")
        if "pattern" in spec and not re.fullmatch(spec["pattern"], value):
            out.append(f"{path}: '{value}' does not match {spec['pattern']}")
    if _is(value, "number") and not isinstance(value, str):
        if "min" in spec and value < spec["min"]:
            out.append(f"{path}: {value} is below the minimum {spec['min']}")
        if "max" in spec and value > spec["max"]:
            out.append(f"{path}: {value} is above the maximum {spec['max']}")
    return out


S = {"type": "string"}
N = {"type": "number"}
B = {"type": "boolean"}
CUE = {"type": ["string", "number"]}  # a phrase from the scene's narration, or seconds from the scene start
HEX = {"type": "string", "pattern": r"#[0-9a-fA-F]{6}"}
