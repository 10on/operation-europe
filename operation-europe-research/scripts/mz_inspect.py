#!/usr/bin/env python3
"""Read-only DOS MZ header and relocation metadata; never executes the input."""

import argparse
import hashlib
import json
import os
import struct
from collections import Counter
from pathlib import Path


DEFAULT_NAMES = ("main.exe", "open.exe", "end.exe", "koei.exe", "install.exe")
MZ_FIELDS = (
    "e_magic", "e_cblp", "e_cp", "e_crlc", "e_cparhdr", "e_minalloc",
    "e_maxalloc", "e_ss", "e_sp", "e_csum", "e_ip", "e_cs",
    "e_lfarlc", "e_ovno",
)


def inspect(path: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) < 28:
        raise ValueError(f"{path.name}: too short for MZ header")
    fields = dict(zip(MZ_FIELDS, struct.unpack_from("<14H", raw)))
    if raw[:2] not in (b"MZ", b"ZM"):
        raise ValueError(f"{path.name}: missing MZ/ZM signature")

    header_bytes = fields["e_cparhdr"] * 16
    declared_bytes = ((fields["e_cp"] - 1) * 512 +
                      (fields["e_cblp"] or 512)) if fields["e_cp"] else None
    relocation_start = fields["e_lfarlc"]
    relocation_end = relocation_start + fields["e_crlc"] * 4
    if header_bytes < 28 or header_bytes > len(raw):
        raise ValueError(f"{path.name}: header extends outside file")
    if relocation_end > header_bytes:
        raise ValueError(f"{path.name}: relocation table extends outside header")

    image_bytes = len(raw) - header_bytes
    entry_image_offset = fields["e_cs"] * 16 + fields["e_ip"]
    stack_image_offset = fields["e_ss"] * 16 + fields["e_sp"]
    targets = []
    samples = []
    for i in range(fields["e_crlc"]):
        entry_file_offset = relocation_start + i * 4
        offset, segment = struct.unpack_from("<HH", raw, entry_file_offset)
        target_image_offset = segment * 16 + offset
        targets.append(target_image_offset)
        if i < 3 or i >= fields["e_crlc"] - 3:
            samples.append({
                "table_entry_file_offset": entry_file_offset,
                "target_image_offset": target_image_offset,
                "target_file_offset": header_bytes + target_image_offset,
                "target_segment_offset": f"{segment:04X}:{offset:04X}",
            })

    counts = Counter(targets)
    nested_signatures = []
    plausible_nested_mz = []
    for signature in (b"MZ", b"ZM"):
        pos = raw.find(signature, 1)
        while pos != -1:
            nested_signatures.append(pos)
            if pos + 28 <= len(raw):
                nested = dict(zip(MZ_FIELDS, struct.unpack_from("<14H", raw, pos)))
                nested_header = nested["e_cparhdr"] * 16
                nested_end = nested["e_lfarlc"] + nested["e_crlc"] * 4
                nested_declared = ((nested["e_cp"] - 1) * 512 +
                                   (nested["e_cblp"] or 512)) if nested["e_cp"] else 0
                if (nested["e_cblp"] <= 511 and nested_header >= 28 and
                        nested_end <= nested_header <= nested_declared <= len(raw) - pos):
                    plausible_nested_mz.append(pos)
            pos = raw.find(signature, pos + 1)
    return {
        "file": path.name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "actual_file_bytes": len(raw),
        "mz_header_fields": fields,
        "declared_file_bytes": declared_bytes,
        "trailing_bytes_beyond_declared": (len(raw) - declared_bytes)
        if declared_bytes is not None else None,
        "header_bytes": header_bytes,
        "load_image_bytes": image_bytes,
        "relocation_table_file_range_half_open": [relocation_start, relocation_end],
        "header_bytes_after_relocation_table": header_bytes - relocation_end,
        "entry_image_offset": entry_image_offset,
        "entry_file_offset": header_bytes + entry_image_offset,
        "entry_within_file_image": entry_image_offset < image_bytes,
        "stack_image_offset": stack_image_offset,
        "stack_extra_bytes_beyond_file_image": max(0, stack_image_offset - image_bytes),
        "minalloc_bytes": fields["e_minalloc"] * 16,
        "stack_within_file_image_plus_minalloc": stack_image_offset < image_bytes + fields["e_minalloc"] * 16,
        "relocation_targets": {
            "count": len(targets),
            "unique_count": len(counts),
            "min_image_offset": min(targets) if targets else None,
            "max_image_offset": max(targets) if targets else None,
            "outside_file_image_count": sum(x + 2 > image_bytes for x in targets),
            "duplicate_target_count": sum(n - 1 for n in counts.values()),
            "sample_first_and_last": samples,
        },
        "embedded_mz_signature_file_offsets": sorted(nested_signatures),
        "plausible_embedded_mz_header_file_offsets": sorted(plausible_nested_mz),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--names", nargs="+", default=DEFAULT_NAMES)
    args = parser.parse_args()
    source_dir = args.source_dir.resolve()
    output = args.out.resolve()
    if not source_dir.is_dir():
        parser.error(f"not a directory: {source_dir}")
    if output == source_dir or source_dir in output.parents:
        parser.error("output must be outside source directory")
    files = [inspect(source_dir / name) for name in args.names]
    result = {
        "schema_version": "1",
        "source_root": str(source_dir),
        "coordinate_systems": {
            "file_offset": "byte offset in original EXE, starting at zero",
            "image_offset": "byte offset from DOS load image after MZ header",
            "segment_offset": "relative to load image; runtime segment requires unknown DOS load segment",
        },
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(output.name + ".tmp")
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, output)
    print(f"Inspected {len(files)} MZ files; wrote {output}")


if __name__ == "__main__":
    main()
