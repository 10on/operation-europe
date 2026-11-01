#!/usr/bin/env python3
"""Summarize InspectOeProgram headless logs without exporting game bytes."""

import argparse
import json
from pathlib import Path


def summarize(log_path: Path) -> dict:
    fields = {}
    blocks = []
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "> OE_" not in line:
            continue
        payload = line.split("> OE_", 1)[1].split(" (GhidraScript)", 1)[0].strip()
        key, *values = payload.split("\t")
        if key == "BLOCK":
            if len(values) != 6:
                raise ValueError(f"malformed OE_BLOCK in {log_path}")
            name, start, end, size, initialized, overlay = values
            blocks.append({"name": name, "start": start, "end": end,
                           "size": int(size), "initialized": initialized == "true",
                           "overlay": overlay == "true"})
        else:
            fields.setdefault(key, []).append("\t".join(values))
    if not blocks or not fields.get("PROGRAM") or not fields.get("ENTRY"):
        raise ValueError(f"missing program, entry or block metadata in {log_path}")
    headers = [b for b in blocks if b["name"] == "HEADER"]
    return {
        "program": fields["PROGRAM"][0],
        "executable_format": fields["EXECUTABLE_FORMAT"][0],
        "language": fields["LANGUAGE"][0],
        "compiler_spec": fields["COMPILER_SPEC"][0],
        "ghidra_image_base": fields["IMAGE_BASE"][0],
        "ghidra_entry_addresses": fields["ENTRY"],
        "block_count": len(blocks),
        "initialized_image_block_count": sum(b["initialized"] and b["name"] != "HEADER" for b in blocks),
        "initialized_image_bytes": sum(b["size"] for b in blocks if b["initialized"] and b["name"] != "HEADER"),
        "uninitialized_bytes": sum(b["size"] for b in blocks if not b["initialized"]),
        "header_bytes": sum(b["size"] for b in headers),
        "header_ghidra_blocks": headers,
        "first_image_block": next((b for b in blocks if b["initialized"] and b["name"] != "HEADER"), None),
        "last_image_block": next((b for b in reversed(blocks) if b["initialized"] and b["name"] != "HEADER"), None),
        "all_blocks_are_non_overlay_except_header": all(b["name"] == "HEADER" or not b["overlay"] for b in blocks),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = {
        "method": "Ghidra analyzeHeadless -process -readOnly -noanalysis -postScript InspectOeProgram.java",
        "coordinate_note": "Ghidra segmented addresses are program addresses; they are not runtime DOS segments or file offsets.",
        "programs": [summarize(path) for path in args.logs],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote metadata for {len(output['programs'])} programs")


if __name__ == "__main__":
    main()
