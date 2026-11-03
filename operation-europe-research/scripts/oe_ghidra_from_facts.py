#!/usr/bin/env python3
"""Строит Ghidra-проект для main.exe из facts/main_exe.facts.json (задача хаба #48).

    python -I scripts/oe_ghidra_from_facts.py [--project-dir private/ghidra-facts] [--force]

Порядок: схема facts -> SHA-256 main.exe == facts.binary.sha256 (до любого вызова Ghidra)
-> analyzeHeadless (импорт MZ, без авто-анализа) + scripts/ghidra/ApplyOeFacts.java
-> check.json -> сверка с artifacts/experiments/TASK-007A/one-function.json.
Коды выхода: 0 успех; 1 расхождение с фактами/TASK-007A; 2 неверные входные данные
(схема, SHA, адреса); 3 ошибка окружения/Ghidra или проект уже существует без --force.
Применяются только адреса kind=ghidra; file_offset используется лишь для сверки.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "facts" / "main_exe.facts.json"
SCHEMA = ROOT / "schemas" / "facts.schema.json"
EXE = ROOT / "private" / "game-dos-working" / "main.exe"
REF = ROOT / "artifacts" / "experiments" / "TASK-007A" / "one-function.json"
CHECK = ROOT / "artifacts" / "experiments" / "GHIDRA-FACTS-20261103" / "check.json"
SCRIPT_DIR = ROOT / "scripts" / "ghidra"
PROJECT_NAME = "OeFacts"
GHIDRA_RE = re.compile(r"^([0-9a-fA-F]{1,4}):([0-9a-fA-F]{1,4})$")


class FactsError(Exception):
    """Неверные входные данные (код выхода 2)."""


class EnvError(Exception):
    """Проблема окружения / Ghidra (код выхода 3)."""


# ---------- чистые части (покрыты tests/test_oe_ghidra_from_facts.py) ----------

def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_sha(exe, expected):
    actual = sha256_of(exe)
    if actual != expected.lower():
        raise FactsError(f"SHA-256 {exe} = {actual}, ожидалось {expected}")


def validate_facts(facts, schema):
    from jsonschema import Draft202012Validator
    errors = sorted(Draft202012Validator(schema).iter_errors(facts), key=lambda e: list(e.path))
    if errors:
        raise FactsError("facts не проходит схему: " + "; ".join(e.message for e in errors[:5]))


def parse_ghidra(value):
    m = GHIDRA_RE.match(value)
    if not m:
        raise FactsError(f"не адрес Ghidra SSSS:OOOO: {value!r}")
    return int(m.group(1), 16), int(m.group(2), 16)


def fmt_ghidra(seg, off):
    return f"{seg:04x}:{off:04x}"


def pick_ghidra(addrs, what):
    """Адрес kind=ghidra из списка; другие системы для применения не годятся."""
    found = [a for a in addrs if a.get("kind") == "ghidra"]
    if len(found) != 1:
        kinds = [a.get("kind") for a in addrs]
        raise FactsError(f"{what}: нужен ровно один адрес kind=ghidra, есть {kinds}")
    return fmt_ghidra(*parse_ghidra(found[0]["value"]))


def file_offset_of(addrs):
    for a in addrs:
        if a.get("kind") == "file_offset":
            return int(a["value"], 16)
    return None


def ghidra_to_file(seg, off, mz):
    return mz["header_bytes"] + (seg - int(mz["ghidra_image_base_segment"], 16)) * 16 + off


def dgroup_delta(facts):
    """Смещение DGROUP от базы загрузки (в параграфах) из segments[].relation, либо None."""
    for s in facts.get("segments", []):
        if s.get("name") == "DGROUP":
            m = re.fullmatch(r"load_base\+0x([0-9A-Fa-f]+)", s.get("relation", ""))
            if m:
                return int(m.group(1), 16)
    return None


def sanitize_name(name):
    out = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    return out if out and not out[0].isdigit() else "L_" + out


def one_line(text):
    return re.sub(r"\s+", " ", text).replace("\t", " ").strip()


def build_plan(facts):
    """Возвращает (строки TSV для Java, список предупреждений). Все адреса — kind=ghidra."""
    mz = facts["binary"]["mz"]
    base = int(mz["ghidra_image_base_segment"], 16)
    rows, notes = [], []
    for fn in facts["functions"]:
        start = pick_ghidra(fn["start"], fn["id"] + ".start")
        end = pick_ghidra(fn["end"], fn["id"] + ".end") if fn.get("end") else "-"
        for label, addrs, g in (("start", fn["start"], start), ("end", fn.get("end") or [], end)):
            fo = file_offset_of(addrs)
            if fo is not None and g != "-" and ghidra_to_file(*parse_ghidra(g), mz) != fo:
                raise FactsError(f"{fn['id']}.{label}: file_offset 0x{fo:X} не соответствует {g}")
        comment = one_line(f"[{fn['status']}] {fn['id']}: {fn['role']} | источники: "
                           + ", ".join(s["path"] for s in fn["sources"]))
        rows.append("\t".join(["FUNC", fn["id"], sanitize_name(fn["name"]), start, end, comment]))
    delta = dgroup_delta(facts)
    for dl in facts.get("data_labels", []):
        comment = one_line(f"[{dl['status']}] {dl['id']}: {dl['name']} ({dl.get('type', '')}) | "
                           + ", ".join(s["path"] for s in dl["sources"]))
        gh = [a for a in dl["at"] if a["kind"] == "ghidra"]
        dg = [a for a in dl["at"] if a["kind"] == "dgroup_offset"]
        if gh:
            address = pick_ghidra(dl["at"], dl["id"])
        elif dg and delta is not None:
            off = int(dg[0]["value"], 16)
            address = fmt_ghidra(base + delta, off)
            fo = file_offset_of(dl["at"])
            if fo is not None and mz["header_bytes"] + delta * 16 + off != fo:
                raise FactsError(f"{dl['id']}: dgroup_offset {dg[0]['value']} и file_offset 0x{fo:X} не согласуются")
            comment += f" | DGROUP={fmt_ghidra(base + delta, 0)}, смещение {dg[0]['value']}"
        else:
            notes.append(f"{dl['id']}: нет адреса Ghidra и нет DGROUP — пропущено")
            continue
        rows.append("\t".join(["LABEL", dl["id"], sanitize_name(dl["name"]), address, comment]))
    return rows, notes


def parse_result(text):
    funcs, labels = {}, []
    for line in text.splitlines():
        f = line.split("\t")
        if f[0] == "FUNC":
            funcs[f[1]] = {"name": f[2], "entry": f[3], "body_min": f[4], "body_max": f[5],
                           "instruction_count": int(f[6]), "size_bytes": int(f[7]), "_insns": []}
        elif f[0] == "INSN":
            funcs[f[1]]["_insns"].append((f[2], int(f[3]), f[4].upper()))
        elif f[0] == "LABEL":
            labels.append({"id": f[1], "name": f[2], "address": f[3], "ok": f[4] == "true"})
    return funcs, labels


def insn_digest(insns):
    return hashlib.sha256("\n".join(f"{a}:{n}:{m}" for a, n, m in insns).encode()).hexdigest()


def compare_with_ref(insns, ref):
    """Сверка списка (addr, len, MNEMONIC) с one-function.json; возвращает список расхождений."""
    bad = []
    ref_i = [(fmt_ghidra(*parse_ghidra(i["ghidra"])), len(i["bytes_hex"]) // 2, i["asm"].split()[0].upper())
             for i in ref["instructions"]]
    mine = [(fmt_ghidra(*parse_ghidra(a)), n, m) for a, n, m in insns]
    if len(mine) != ref["instruction_count"] or len(mine) != len(ref_i):
        bad.append(f"число инструкций {len(mine)} != {ref['instruction_count']}")
    if sum(n for _, n, _ in mine) != sum(n for _, n, _ in ref_i):
        bad.append("суммарный размер не совпал")
    for k, (x, y) in enumerate(zip(mine, ref_i)):
        if x != y:
            bad.append(f"инструкция #{k}: Ghidra {x} != эталон {y}")
            if len(bad) > 5:
                break
    return bad


def build_check(facts, funcs, labels, ref_status):
    out = {"binary_sha256": facts["binary"]["sha256"], "facts_format_version": facts.get("format_version"),
           "functions": [], "labels": sorted(labels, key=lambda l: l["id"]),
           "task_007a_comparison": ref_status}
    for fid in sorted(funcs):
        f = funcs[fid]
        out["functions"].append({"id": fid, **{k: v for k, v in f.items() if k != "_insns"},
                                 "instruction_digest_sha256": insn_digest(f["_insns"])})
    return out


# ---------- окружение / Ghidra ----------

def find_ghidra():
    g = os.environ.get("OE_GHIDRA")
    if g and Path(g).is_dir():
        return Path(g)
    cands = sorted(Path("C:/Tools").glob("ghidra_*")) if Path("C:/Tools").is_dir() else []
    if cands:
        return cands[0]
    raise EnvError("Ghidra не найдена (задайте OE_GHIDRA)")


def find_java_home():
    j = os.environ.get("JAVA_HOME")
    if j and Path(j).is_dir():
        return j
    base = Path("C:/Program Files/Eclipse Adoptium")
    cands = sorted(base.glob("jdk-25*")) if base.is_dir() else []
    if cands:
        return str(cands[0])
    raise EnvError("JDK 25 не найден (задайте JAVA_HOME)")


def run_headless(project_dir, exe, plan_tsv, out_tsv, timeout):
    ghidra = find_ghidra()
    env = dict(os.environ, JAVA_HOME=find_java_home())
    bat = ghidra / "support" / ("analyzeHeadless.bat" if os.name == "nt" else "analyzeHeadless")
    cmd = [str(bat), str(project_dir), PROJECT_NAME, "-import", str(exe), "-overwrite", "-noanalysis",
           "-scriptPath", str(SCRIPT_DIR), "-postScript", "ApplyOeFacts.java", str(plan_tsv), str(out_tsv)]
    log = project_dir / "headless.log"
    with open(log, "wb") as lf:
        try:
            r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as e:
            raise EnvError(f"analyzeHeadless не выполнен: {e}")
    if r.returncode != 0 or not out_tsv.exists():
        raise EnvError(f"analyzeHeadless код {r.returncode}; лог: {log}")


def safe_remove(project_dir):
    private = (ROOT / "private").resolve()
    p = project_dir.resolve()
    if private not in p.parents:
        raise EnvError(f"--force удаляет только каталоги внутри {private}; получено {p}")
    shutil.rmtree(p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--project-dir", default=str(ROOT / "private" / "ghidra-facts"))
    ap.add_argument("--force", action="store_true", help="удалить существующий каталог проекта (только внутри private/)")
    ap.add_argument("--facts", default=str(FACTS))
    ap.add_argument("--exe", default=str(EXE))
    ap.add_argument("--check-out", default=str(CHECK))
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args(argv)
    project_dir = Path(a.project_dir)
    try:
        facts = json.loads(Path(a.facts).read_text(encoding="utf-8"))
        validate_facts(facts, json.loads(SCHEMA.read_text(encoding="utf-8")))
        check_sha(Path(a.exe), facts["binary"]["sha256"])  # до любого вызова Ghidra
        rows, notes = build_plan(facts)
        if project_dir.exists() and any(project_dir.iterdir()):
            if not a.force:
                raise EnvError(f"{project_dir} уже существует; используйте --force")
            safe_remove(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        plan, out = project_dir / "plan.tsv", project_dir / "result.tsv"
        plan.write_text("\n".join(rows) + "\n", encoding="utf-8")
        run_headless(project_dir, Path(a.exe), plan, out, a.timeout)
        funcs, labels = parse_result(out.read_text(encoding="utf-8"))
    except FactsError as e:
        print(f"ОШИБКА входных данных: {e}", file=sys.stderr)
        return 2
    except EnvError as e:
        print(f"ОШИБКА окружения: {e}", file=sys.stderr)
        return 3
    problems = []
    for fn in facts["functions"]:
        f = funcs.get(fn["id"])
        if not f:
            problems.append(f"{fn['id']}: нет в экспорте")
        elif (f["instruction_count"], f["size_bytes"]) != (fn["instruction_count"], fn["size_bytes"]):
            problems.append(f"{fn['id']}: Ghidra {f['instruction_count']} инстр./{f['size_bytes']} байт, "
                            f"в facts {fn['instruction_count']}/{fn['size_bytes']}")
    problems += [f"метка {l['id']} не создана" for l in labels if not l["ok"]]
    ref = json.loads(REF.read_text(encoding="utf-8"))
    ref_start = fmt_ghidra(*parse_ghidra(ref["ghidra_range"].split("..")[0]))
    match = [f for f in funcs.values() if f["entry"] == ref_start]
    if not match:
        cmp_bad = ["функция TASK-007A не найдена в проекте"]
    else:
        cmp_bad = compare_with_ref(match[0]["_insns"], ref)
    status = {"reference": "artifacts/experiments/TASK-007A/one-function.json", "match": not cmp_bad,
              "instruction_count": len(match[0]["_insns"]) if match else 0,
              "size_bytes": match[0]["size_bytes"] if match else 0, "differences": cmp_bad}
    check = build_check(facts, funcs, labels, status)
    cp = Path(a.check_out)
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(check, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for n in notes:
        print("ПРЕДУПРЕЖДЕНИЕ:", n)
    for p in problems + cmp_bad:
        print("РАСХОЖДЕНИЕ:", p, file=sys.stderr)
    print(f"проект: {project_dir}; check.json: {cp}; TASK-007A: "
          f"{status['instruction_count']} инстр., {status['size_bytes']} байт, совпадение={'да' if not cmp_bad else 'нет'}")
    return 1 if (problems or cmp_bad) else 0


if __name__ == "__main__":
    sys.exit(main())
