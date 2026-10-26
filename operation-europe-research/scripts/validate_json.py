#!/usr/bin/env python3
"""Validate a JSON file with jsonschema if installed, otherwise simple subset."""
import json
import sys
from pathlib import Path


def minimal_validate(schema, value, where="$", errors=None):
    errors = [] if errors is None else errors
    kinds = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool, "null": type(None)}
    typ = schema.get("type")
    if typ and (not isinstance(value, kinds[typ]) or (typ in ("integer", "number") and isinstance(value, bool))):
        errors.append(f"{where}: expected {typ}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{where}: expected one of {schema['enum']}")
    if typ == "object":
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{where}: missing {name}")
        for name, val in value.items():
            if name in schema.get("properties", {}):
                minimal_validate(schema["properties"][name], val, f"{where}.{name}", errors)
            elif schema.get("additionalProperties") is False:
                errors.append(f"{where}: unexpected {name}")
    elif typ == "array":
        if isinstance(schema.get("items"), dict):
            for i, val in enumerate(value):
                minimal_validate(schema["items"], val, f"{where}[{i}]", errors)
    elif typ == "string":
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{where}: string too short")
    elif typ in ("integer", "number") and "minimum" in schema and value < schema["minimum"]:
        errors.append(f"{where}: value too small")
    return errors


def main():
    if len(sys.argv) != 3:
        print("Usage: python validate_json.py SCHEMA.json INPUT.json", file=sys.stderr)
        return 2
    schema = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    data = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        errors = minimal_validate(schema, data)
        print("Using bundled minimal validator; pip install jsonschema for full JSON Schema validation")
    else:
        errors = [str(err) for err in Draft202012Validator(schema).iter_errors(data)]
    if errors:
        print("INVALID:\n" + "\n".join(errors), file=sys.stderr)
        return 1
    print("VALID")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
