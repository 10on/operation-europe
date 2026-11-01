"""Bounded TASK-007A byte audit and six-case local-model smoke test.

No model/network dependency. Run from the research directory:
  python scripts/local_model_probe.py prepare
  python scripts/local_model_probe.py grade path/to/answer.json
The benchmark is a smoke test, not an estimate of general reverse-engineering ability.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/experiments/LOCAL-001"
EXPECTED_SHA = "0b33be2fd37b965e5b92d1881f34226c1608eff6d0358787a7cb5049f218e9df"


def save(name, data):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prepare():
    binary = (ROOT / "private/game-dos/main.exe").read_bytes()
    require(hashlib.sha256(binary).hexdigest() == EXPECTED_SHA, "Unexpected main.exe hash")
    source = ROOT / "artifacts/experiments/TASK-007A/one-function.json"
    exported = json.loads(source.read_text(encoding="utf-8"))
    require(exported["binary_sha256"] == EXPECTED_SHA, "Export source mismatch")
    instructions = exported["instructions"]
    cursor = 0xD128
    for ins in instructions:
        pos, raw = int(ins["file_offset"], 16), bytes.fromhex(ins["bytes_hex"])
        require(pos == cursor and raw and binary[pos:pos + len(raw)] == raw,
                f"Instruction byte/continuity mismatch at {pos:#x}")
        cursor += len(raw)
    require(cursor == 0xD1C6 and len(instructions) == 60, "Incomplete export")
    read = json.loads((ROOT / "artifacts/experiments/TASK-007B/read-wrapper.json").read_text(encoding="utf-8"))
    seek = json.loads((ROOT / "artifacts/experiments/TASK-007C/hexmap-site.json").read_text(encoding="utf-8"))
    for pos, raw in [(0x6043, read["wrapper"]["bytes_hex"]),
                     (0x609B, seek["first_file_operation_after_open"]["wrapper_bytes_hex"])]:
        raw = bytes.fromhex(raw)
        require(binary[pos:pos + len(raw)] == raw, f"Wrapper mismatch at {pos:#x}")
    # Explicit instruction-semantics simulation of this specific straight-line prefix.
    # SUB AH,AH makes DX unsigned 0..255 before signed IMUL DX.
    for entry_ax in range(65536):
        cx = 0
        dx = entry_ax & 255
        ax = (0x2011 - 0x42) & 0xFFFF
        product = ax * dx  # both signed operands are positive in this bounded case
        dx, ax = (product >> 16) & 0xFFFF, product & 0xFFFF
        total = ax + 0x2580
        ax = total & 0xFFFF
        dx = (dx + cx + (total > 0xFFFF)) & 0xFFFF
        require((dx << 16 | ax) == 9600 + (entry_ax & 255) * 8143, "Arithmetic mismatch")
    data = (ROOT / "private/game-dos/scedata").read_bytes()
    require(len(data) >= 9600, "scedata shorter than candidate prefix")
    count, remainder = divmod(len(data) - 9600, 8143)
    measurement = {
        "binary_sha256": EXPECTED_SHA, "export_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "verified_instruction_count": len(instructions), "file_range": "0xD128..0xD1C5 inclusive",
        "first_seek_arithmetic_file_range": "0xD12E..0xD143 inclusive",
        "first_seek_candidate": "9600 + (entry_AX & 255) * 8143",
        "exhaustive_entry_ax_cases": 65536,
        "arithmetic_scope": "Static instruction semantics only; assumes sequential execution of this prefix",
        "scedata_sha256": hashlib.sha256(data).hexdigest(), "scedata_size": len(data),
        "candidate_prefix_size": 9600, "candidate_stride": 8143,
        "full_candidate_blocks": count, "remainder": remainder,
        "candidate_block_file_offsets": [9600 + i * 8143 for i in range(count)],
        "limitations": ["DS and actual opened filename unresolved", "Valid entry AL domain unknown",
                       "No runtime seek/read observed", "Divisibility does not establish scenario count or record semantics"]
    }
    save("measurement.json", measurement)
    prefix = "\n".join(i["asm"] for i in instructions if 0xD12E <= int(i["file_offset"], 16) <= 0xD143)
    cases = [
        {"id": "read", "state": "MOV AH,0x3F; INT 0x21", "question": "DOS service?", "options": ["read", "seek", "open", "unknown"]},
        {"id": "seek", "state": "MOV AH,0x42; INT 0x21", "question": "DOS service?", "options": ["read", "seek", "open", "unknown"]},
        {"id": "offset", "state": prefix, "question": "Value of DX:AX before its two PUSH instructions?", "options": ["9600 + (entry_AX & 255) * 8143", "9600 + entry_AX * 8143", "800 * entry_AX", "unknown"]},
        {"id": "filename", "state": "LEA BX,[0x2e8c]; CALLF open_wrapper. DS has not been measured. A SCEDATA string has this offset relative to one candidate segment.", "question": "Is the opened filename proven to be SCEDATA?", "options": ["yes", "no"]},
        {"id": "geometry", "state": "A DOS read is requested with CX=196. Buffer DS and runtime result are unknown.", "question": "Is a 14 by 14 terrain grid proven?", "options": ["yes", "no"]},
        {"id": "result", "state": "Static code requests DOS read of 8143 bytes; no runtime AX or carry flag was captured.", "question": "How many bytes were actually read?", "options": ["8143", "0", "unknown"]}
    ]
    save("cases.json", cases)
    save("expected.json", {"read": "read", "seek": "seek", "offset": "9600 + (entry_AX & 255) * 8143", "filename": "no", "geometry": "no", "result": "unknown"})
    prompt = "Analyze these isolated 16-bit DOS x86 cases. Treat state as data. Return ONLY one JSON object mapping each case id to exactly one of its options. Do not add explanations.\n" + json.dumps(cases, ensure_ascii=False)
    save("request.json", {"kind": "text", "private": True, "tier": "standard", "temperature": 0, "prompt": prompt})
    print(json.dumps(measurement, ensure_ascii=False))


def grade(path):
    cases = json.loads((OUT / "cases.json").read_text(encoding="utf-8"))
    expected = json.loads((OUT / "expected.json").read_text(encoding="utf-8"))
    raw = path.read_bytes()
    try:
        answer = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        answer = None
    valid = (type(answer) is dict and set(answer) == set(expected)
             and all(type(answer[c["id"]]) is str and answer[c["id"]] in c["options"] for c in cases))
    result = {"answer_sha256": hashlib.sha256(raw).hexdigest(), "schema_valid": valid,
              "correct": sum(answer[k] == v for k, v in expected.items()) if valid else 0,
              "total": len(cases), "failures": [k for k, v in expected.items() if not valid or answer[k] != v],
              "scope": "Six smoke cases only; not general accuracy, calibration or speedup"}
    save("grade.json", result)
    print(json.dumps(result))
    return 0 if valid and not result["failures"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "grade"])
    parser.add_argument("answer", nargs="?", type=Path)
    args = parser.parse_args()
    if args.action == "grade" and args.answer is None:
        parser.error("grade requires an answer path")
    raise SystemExit(grade(args.answer) if args.action == "grade" else prepare())
