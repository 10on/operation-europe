#!/usr/bin/env python3
"""Compact, read-only byte measurements for selected Operation Europe data files."""

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path


NAMES = ("scedata", "hexmap.dat", "msg", "msg.16p", "emsg", "emsg.16p")


def profile(path):
    data = path.read_bytes()
    counts = collections.Counter(data)
    total = len(data)
    entropy = -sum((n / total) * math.log2(n / total) for n in counts.values()) if total else 0.0
    result = {
        "name": path.name,
        "size": total,
        "sha256": hashlib.sha256(data).hexdigest(),
        "first_32_bytes_hex": data[:32].hex(),
        "distinct_byte_values": len(counts),
        "entropy_bits_per_byte": round(entropy, 4),
        "zero_count": counts[0],
        "ascii_printable_count": sum(counts[b] for b in range(32, 127)),
        "high_bit_count": sum(counts[b] for b in range(128, 256)),
        "cr_count": counts[13],
        "lf_count": counts[10],
        "crlf_count": data.count(b"\r\n"),
        "top_bytes": [{"hex": f"{b:02x}", "count": n} for b, n in counts.most_common(12)],
    }
    if path.name == "scedata":
        starts = [0] + [i + 1 for i, b in enumerate(data) if b == 10]
        lengths = [end - start for start, end in zip(starts, starts[1:] + [total])]
        zero_runs = []
        printable_runs = []
        start = 0
        while start < total:
            b = data[start]
            end = start + 1
            while end < total and (data[end] == 0 if b == 0 else 32 <= b <= 126 and 32 <= data[end] <= 126):
                end += 1
            if b == 0 and end - start >= 64:
                zero_runs.append({"file_offset": start, "length": end - start})
            elif 32 <= b <= 126 and end - start >= 32:
                printable_runs.append({"file_offset": start, "length": end - start})
            start = end
        result["line_starts_first_16_file_offsets"] = starts[:16]
        result["line_count_by_lf"] = len(starts)
        result["line_length_min_max"] = [min(lengths), max(lengths)]
        result["zero_runs_ge_64_first_32"] = zero_runs[:32]
        result["printable_runs_ge_32_first_32"] = printable_runs[:32]
        result["first_12_blocks_of_800"] = [
            {
                "file_offset": i * 800,
                "nonzero_count": sum(b != 0 for b in data[i * 800:(i + 1) * 800]),
                "non_text_nonzero_count": sum(
                    b not in (0, 9, 10, 13) and not 32 <= b <= 126
                    for b in data[i * 800:(i + 1) * 800]
                ),
                "zero_suffix_length": 800 - len(data[i * 800:(i + 1) * 800].rstrip(b"\x00")),
            }
            for i in range(12)
        ]
        result["non_ascii_or_control_file_offsets_first_32"] = [
            i for i, b in enumerate(data) if b not in (9, 10, 13) and not 32 <= b <= 126
        ][:32]
    if path.name == "hexmap.dat":
        runs = []
        start = 0
        for i in range(1, total + 1):
            if i == total or data[i] != data[start]:
                if i - start >= 8:
                    runs.append({"file_offset": start, "value_hex": f"{data[start]:02x}", "length": i - start})
                start = i
        result["longest_same_byte_runs"] = sorted(runs, key=lambda r: r["length"], reverse=True)[:12]
        result["equal_adjacent_bytes"] = sum(data[i] == data[i - 1] for i in range(1, total))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    files = {name: root / name for name in NAMES}
    missing = [name for name, path in files.items() if not path.is_file()]
    if missing:
        parser.error("missing files: " + ", ".join(missing))
    result = {
        "method": "Read bytes only; all offsets are zero-based file offsets. No format decoder or decompressor used.",
        "files": [profile(files[name]) for name in NAMES],
        "pairs": [],
    }
    for left, right in (("msg", "msg.16p"), ("emsg", "emsg.16p")):
        a, b = files[left].read_bytes(), files[right].read_bytes()
        result["pairs"].append({
            "left": left,
            "right": right,
            "identical": a == b,
            "first_difference_file_offset": next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), None),
        })
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
