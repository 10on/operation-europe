#!/usr/bin/env python3
"""Проверка готовности окружения проекта одной командой (oe-check). Ничего не меняет."""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

OE = Path(os.getenv("OE_ROOT") or Path(__file__).resolve().parents[1])
PRIV = OE / "private"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


check("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
try:
    import yaml  # noqa: F401
    check("pyyaml", True, yaml.__version__)
except ImportError:
    check("pyyaml", False, "pip install pyyaml")

java = Path(os.getenv("JAVA_HOME", "")) / "bin" / "java.exe"
if java.exists():
    out = subprocess.run([str(java), "-version"], capture_output=True, text=True).stderr.splitlines()
    check("java 25 (нужна Ghidra 12.2)", "25" in (out[0] if out else ""), out[0] if out else "")
else:
    check("java 25 (нужна Ghidra 12.2)", False, "JAVA_HOME не задан (выполните . .\\scripts\\env.ps1)")

g = Path(os.getenv("OE_GHIDRA", ""))
check("ghidra", (g / "support" / "analyzeHeadless.bat").exists(), str(g))
dba = Path(os.getenv("OE_DOSBOX_AUTOMATION", ""))
check("dosbox-automation 0.85.1", dba.exists() and "0.85.1" in str(dba), str(dba))
check("dosbox-x", Path(os.getenv("OE_DOSBOX_X", "C:/DOSBox-X/dosbox-x.exe")).exists())

tok = os.getenv("DOSBOX_API_TOKEN", "")
tok_ok = len(tok) == 64 and all(c in "0123456789abcdefABCDEF" for c in tok)
check("DOSBOX_API_TOKEN (64 hex)", tok_ok,
      "задайте токен в переменной окружения; env.ps1 не загружает его из файла" if not tok_ok else "")

# Целостность мастер-копии private/game-dos по манифесту
man = PRIV / "game-dos.sha256"
if man.exists():
    bad, n = [], 0
    for line in man.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        n += 1
        f = PRIV / "game-dos" / rel
        if not f.exists() or sha256(f) != digest:
            bad.append(rel)
    check("master copy game-dos == манифест", not bad, f"{n} файлов" + (f"; расхождения: {bad[:5]}" if bad else ""))
else:
    check("манифест game-dos.sha256", False, "нет private/game-dos.sha256")
check("рабочая копия game-dos-working", (PRIV / "game-dos-working" / "main.exe").exists())
check("artifacts/inventory.json", (OE / "artifacts" / "inventory.json").exists(), "oe-inv")

# API (необязателен: DOSBox может быть не запущен)
try:
    req = urllib.request.Request(os.getenv("DOSBOX_API_URL", "http://127.0.0.1:8386") + "/api/v1/status",
                                 headers={"Authorization": "Bearer " + tok})
    with urllib.request.urlopen(req, timeout=3) as r:
        print(f"[INFO] DOSBox API отвечает: HTTP {r.status}")
except Exception as e:  # noqa: BLE001
    print(f"[INFO] DOSBox API недоступен (ок, если не запущен oe-dosbox): {str(e)[:80]}")

print("\nИТОГ:", "ГОТОВО" if all(results) else "ЕСТЬ ПРОБЛЕМЫ")
sys.exit(0 if all(results) else 1)
