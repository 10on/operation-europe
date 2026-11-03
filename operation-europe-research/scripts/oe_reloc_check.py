#!/usr/bin/env python3
"""Read-only check: which MZ relocation targets hold a given 16-bit word.

Input is either a DOS MZ executable (--exe, optional --sha256 guard) or a JSON
extract (--json) of the form {"header_paragraphs": int, "relocations":
[{"seg": int, "off": int, "word": int}, ...]}. For --exe the entry point is
also scanned for B8..BF opcodes followed by the value. Never executes the input.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path


MZ_FIELDS = (
    "e_magic", "e_cblp", "e_cp", "e_crlc", "e_cparhdr", "e_minalloc",
    "e_maxalloc", "e_ss", "e_sp", "e_csum", "e_ip", "e_cs",
    "e_lfarlc", "e_ovno",
)
REG_NAMES = ("ax", "cx", "dx", "bx", "sp", "bp", "si", "di")
ENTRY_WINDOW = 64
MOV_DS_AX = b"\x8e\xd8"
MOV_DS_AX_WINDOW = 16
MAX_OFFSETS = 20
DEFAULT_VALUE = 0x4712


class InputError(Exception):
    """Bad input; reported on stderr with exit code 2."""


def parse_value(text: str) -> int:
    try:
        value = int(text, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an integer: {text!r}")
    if not 0 <= value <= 0xFFFF:
        raise argparse.ArgumentTypeError(f"value out of 16-bit range: {text!r}")
    return value


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def load_json(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read {path.name}: {exc}")
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InputError(f"malformed JSON in {path.name}: {exc}")
    if not isinstance(data, dict):
        raise InputError("JSON root must be an object")
    for key in ("header_paragraphs", "relocations"):
        if key not in data:
            raise InputError(f"missing key: {key}")
    header_paragraphs = data["header_paragraphs"]
    relocations = data["relocations"]
    if not is_int(header_paragraphs) or header_paragraphs < 0:
        raise InputError("header_paragraphs must be a non-negative integer")
    if not isinstance(relocations, list):
        raise InputError("relocations must be a list")
    targets = []
    for i, entry in enumerate(relocations):
        if not isinstance(entry, dict):
            raise InputError(f"relocation {i} must be an object")
        for key in ("seg", "off", "word"):
            if key not in entry:
                raise InputError(f"relocation {i} missing key: {key}")
            if not is_int(entry[key]) or not 0 <= entry[key] <= 0xFFFF:
                raise InputError(f"relocation {i} field {key} must be a 16-bit integer")
        file_offset = header_paragraphs * 16 + entry["seg"] * 16 + entry["off"]
        targets.append((file_offset, entry["word"]))
    return targets


def load_exe(path: Path, expected_sha: str | None, value: int) -> tuple[dict, list]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InputError(f"cannot read {path.name}: {exc}")
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha is not None and sha != expected_sha:
        raise InputError(f"sha256 mismatch for {path.name}: expected {expected_sha}, got {sha}")
    if len(raw) < 28 or raw[:2] not in (b"MZ", b"ZM"):
        raise InputError(f"{path.name}: not a DOS MZ executable")

    fields = dict(zip(MZ_FIELDS, struct.unpack_from("<14H", raw)))
    header_bytes = fields["e_cparhdr"] * 16
    relocation_start = fields["e_lfarlc"]
    relocation_end = relocation_start + fields["e_crlc"] * 4
    if header_bytes < 28 or header_bytes > len(raw):
        raise InputError(f"{path.name}: header extends outside file")
    if relocation_end > header_bytes:
        raise InputError(f"{path.name}: relocation table extends outside header")

    targets = []
    for i in range(fields["e_crlc"]):
        offset, segment = struct.unpack_from("<HH", raw, relocation_start + i * 4)
        file_offset = header_bytes + segment * 16 + offset
        if file_offset + 2 > len(raw):
            raise InputError(f"relocation {i} target 0x{file_offset:X} outside file")
        word = struct.unpack_from("<H", raw, file_offset)[0]
        targets.append((file_offset, word))

    entry_file_offset = header_bytes + fields["e_cs"] * 16 + fields["e_ip"]
    if entry_file_offset >= len(raw):
        raise InputError(f"{path.name}: entry 0x{entry_file_offset:X} outside file")
    window = raw[entry_file_offset:entry_file_offset + ENTRY_WINDOW]
    value_bytes = struct.pack("<H", value)
    hits = []
    for i in range(len(window) - 2):
        opcode = window[i]
        if 0xB8 <= opcode <= 0xBF and window[i + 1:i + 3] == value_bytes:
            hits.append({"reg": REG_NAMES[opcode - 0xB8],
                         "file_offset": entry_file_offset + i})
    mov_ds_ax = False
    for hit in hits:
        if hit["reg"] != "ax":
            continue
        after = hit["file_offset"] + 3
        if MOV_DS_AX in raw[after:after + MOV_DS_AX_WINDOW]:
            mov_ds_ax = True
    entry = {
        "file_offset": entry_file_offset,
        "hits": hits,
        "mov_ds_ax_within_16_bytes_after_ax_hit": mov_ds_ax,
    }
    result = {"input": "exe", "sha256": sha}
    return result, targets, entry


def analyse(targets: list, value: int) -> dict:
    matches = [file_offset for file_offset, word in targets if word == value]
    if not targets:
        verdict = "no_data"
    elif matches:
        verdict = "found"
    else:
        verdict = "not_found"
    return {
        "relocation_count": len(targets),
        "match_count": len(matches),
        "match_file_offsets": [f"0x{offset:X}" for offset in matches[:MAX_OFFSETS]],
        "verdict": verdict,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--exe", type=Path, help="DOS MZ executable (read-only)")
    source.add_argument("--json", type=Path, help="JSON relocation extract")
    parser.add_argument("--sha256", help="expected SHA-256 of --exe; mismatch exits 2")
    parser.add_argument("--value", type=parse_value, default=DEFAULT_VALUE,
                        help="16-bit word to search for (default 0x4712)")
    args = parser.parse_args(argv)

    expected_sha = None
    if args.sha256 is not None:
        if args.exe is None:
            parser.error("--sha256 requires --exe")
        expected_sha = args.sha256.strip().lower()
        if len(expected_sha) != 64 or any(c not in "0123456789abcdef" for c in expected_sha):
            parser.error("--sha256 must be 64 hex characters")

    try:
        if args.exe is not None:
            head, targets, entry = load_exe(args.exe, expected_sha, args.value)
        else:
            head, targets, entry = {"input": "json"}, load_json(args.json), None
    except InputError as exc:
        print(f"oe_reloc_check: error: {exc}", file=sys.stderr)
        return 2

    result = dict(head)
    result["value"] = f"0x{args.value:04X}"
    result.update(analyse(targets, args.value))
    result["entry"] = entry
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
