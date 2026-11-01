#!/usr/bin/env python3
"""Correlate selected Ghidra filename/call addresses with original MZ file offsets."""

import argparse
import hashlib
import json
from pathlib import Path


PATTERNS = {
    "SCEDATA": bytes.fromhex("8d1e8c2e"),
    "HEXMAP.DAT": bytes.fromhex("8d1e0a2f"),
    "MSG": bytes.fromhex("8d1e482f"),
}


def linear(address: str) -> int:
    segment, offset = address.split(":")
    return int(segment, 16) * 16 + int(offset, 16)


def records(path: Path, key: str):
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "> OE_" + key + "\t" in line:
            yield line.split("> OE_" + key + "\t", 1)[1].split(" (GhidraScript)", 1)[0].strip().split("\t")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe", type=Path)
    parser.add_argument("mz_metadata", type=Path)
    parser.add_argument("ghidra_metadata", type=Path)
    parser.add_argument("names_log", type=Path)
    parser.add_argument("sites_log", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    data = args.exe.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    mz = next(x for x in json.loads(args.mz_metadata.read_text(encoding="utf-8"))["files"]
              if x["file"] == args.exe.name)
    ghidra = next(x for x in json.loads(args.ghidra_metadata.read_text(encoding="utf-8"))["programs"]
                  if x["program"] == args.exe.name)
    if digest != mz["sha256"]:
        raise ValueError("EXE hash differs from TASK-002 MZ metadata")
    if ghidra["initialized_image_bytes"] != mz["load_image_bytes"]:
        raise ValueError("Ghidra image size differs from MZ image size")
    header = mz["header_bytes"]
    base = 0x10000  # observed 1000:0000 first image block in this import

    def file_offset(address: str) -> int:
        offset = linear(address) - base + header
        if not 0 <= offset < len(data):
            raise ValueError(f"mapped offset outside EXE: {address}")
        return offset

    block_start = linear(ghidra["last_image_block"]["start"])
    names = []
    for name, address, block, ref_count in records(args.names_log, "MATCH"):
        if name not in PATTERNS:
            continue
        offset = file_offset(address)
        if data[offset:offset + len(name)] != name.encode("ascii"):
            raise ValueError(f"filename bytes do not match at {address}")
        names.append({"name": name, "ghidra_address": address, "file_offset": offset,
                      "block": block, "offset_in_last_image_block": linear(address) - block_start,
                      "automatic_reference_count": int(ref_count)})

    sites = []
    for name, address, block, lea, call in records(args.sites_log, "SITE"):
        offset = file_offset(address)
        if data[offset:offset + 4] != PATTERNS[name]:
            raise ValueError(f"LEA bytes do not match at {address}")
        target = next((x[2] for x in records(args.sites_log, "CALL_TARGET")
                       if x[0] == name and x[1] == address), None)
        sites.append({"name": name, "ghidra_address": address, "file_offset": offset,
                      "block": block, "instruction_1": lea, "instruction_2": call,
                      "ghidra_call_target": target})

    result = {
        "exe_sha256": digest,
        "method": "Match original LEA/string bytes to read-only Ghidra addresses; test each address with file_offset = linear(Ghidra address) - 0x10000 + MZ header bytes for this import only.",
        "warning": "Ghidra addresses and mapped file offsets are not runtime DOS segment:offset addresses. LEA plus a matching offset does not alone establish DS at the call site.",
        "names": names,
        "sites": sites,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(names)} names and {len(sites)} call sites")


if __name__ == "__main__":
    main()
