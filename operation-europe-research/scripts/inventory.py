#!/usr/bin/env python3
"""Read-only file inventory; no execution, disassembly or game-specific guesses."""
import argparse
import hashlib
import json
import math
import os
import re
import struct
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

MAX_SAMPLE = 4 * 1024 * 1024
STRINGS_LIMIT = 30


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def entropy(raw):
    if not raw:
        return 0.0
    return round(-sum((count / len(raw)) * math.log2(count / len(raw)) for count in Counter(raw).values()), 3)


def analyze_mz(prefix, file_size):
    if len(prefix) < 28 or prefix[:2] not in (b"MZ", b"ZM"):
        return None
    fields = struct.unpack_from("<14H", prefix, 0)
    (_magic, cblp, cp, crlc, cparhdr, minalloc, maxalloc, ss, sp,
     checksum, ip, cs, lfarlc, ovno) = fields
    expected_size = ((cp - 1) * 512 + (cblp or 512)) if cp else None
    result = {
        "kind": "DOS_MZ_candidate", "page_count": cp,
        "bytes_last_page": cblp, "header_bytes": cparhdr * 16,
        "relocation_count": crlc, "reloc_table_file_offset": lfarlc,
        "initial_cs_ip": f"{cs:04X}:{ip:04X}",
        "initial_ss_sp": f"{ss:04X}:{sp:04X}",
        "minalloc_paras": minalloc, "maxalloc_paras": maxalloc,
        "overlay_number": ovno, "declared_file_bytes": expected_size,
        "trailing_bytes_beyond_declared": max(0, file_size - expected_size) if expected_size is not None else None,
        "warnings": [],
    }
    if cparhdr * 16 < 28 or cparhdr * 16 > file_size:
        result["warnings"].append("suspicious MZ header size")
    if lfarlc + 4 * crlc > cparhdr * 16:
        result["warnings"].append("MZ relocation table may exceed header")
    if expected_size and expected_size > file_size:
        result["warnings"].append("declared executable larger than actual file")
    if expected_size and file_size > expected_size:
        result["warnings"].append("trailing data may be an overlay, appended data or packing artifact")
    return result


def inspect_file(path, root):
    file_size = path.stat().st_size
    with path.open("rb") as f:
        sample = f.read(MAX_SAMPLE)
    strings = re.findall(rb"[\x20-\x7E]{5,}", sample)
    magic = "DOS_MZ_candidate" if sample[:2] in (b"MZ", b"ZM") else (
        "ZIP_candidate" if sample.startswith(b"PK\x03\x04") else
        "not_identified")
    result = {
        "path": path.relative_to(root).as_posix(), "size": file_size,
        "sha256": sha256_file(path), "magic": magic,
        "first_32_bytes_hex": sample[:32].hex(),
        "sampled_bytes": len(sample), "entropy_first_64k_bits_per_byte": entropy(sample[:65536]),
        "printable_ascii_strings_count_in_sample": len(strings),
        "ascii_strings_preview": [s[:160].decode("ascii", "replace") for s in strings[:STRINGS_LIMIT]],
        "mz": analyze_mz(sample, file_size),
        "notes": [],
    }
    if path.suffix.lower() == ".com":
        result["notes"].append(".COM extension: raw 16-bit program is possible; extension alone is not proof")
    if len(sample) == MAX_SAMPLE and file_size > MAX_SAMPLE:
        result["notes"].append("strings and entropy sampled, not full file")
    return result


def main():
    p = argparse.ArgumentParser(description="Read-only inventory of candidate DOS game directory")
    p.add_argument("directory", type=Path)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    root = args.directory.resolve()
    if not root.is_dir():
        p.error(f"Not a directory: {root}")
    output = args.out.resolve()
    if output == root or root in output.parents:
        p.error("Output JSON must be outside the inventoried source directory")
    files = sorted(x for x in root.rglob("*") if x.is_file())
    result = {
        "schema_version": "1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(root), "notice": "All candidate formats/strings are heuristic, not game-specific findings",
        "count": len(files), "files": [inspect_file(path, root) for path in files],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, output)
    print(f"Indexed {len(files)} file(s); wrote {output}")


if __name__ == "__main__":
    main()
