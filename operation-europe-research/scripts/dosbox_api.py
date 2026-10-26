#!/usr/bin/env python3
"""Minimal DOSBox Automation v0.85.1 API client (local only, authenticated)."""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path


def do_request(base, token, endpoint, method="GET", body=None):
    headers = {"Authorization": "Bearer " + token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        base.rstrip("/") + endpoint,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        detail = e.read(500).decode("utf-8", "replace")
        raise RuntimeError(f"DOSBox API HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"DOSBox API connection: {e.reason}") from e


def save_bytes(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    print(f"Saved {len(data)} byte(s) -> {target}")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default=os.getenv("DOSBOX_API_URL", "http://127.0.0.1:8386"))
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("info")
    s = sub.add_parser("screenshot")
    s.add_argument("output")
    s = sub.add_parser("memory")
    s.add_argument("offset")
    s.add_argument("length", type=lambda v: int(v, 0))
    s.add_argument("output")
    s = sub.add_parser("key")
    s.add_argument("key_name")
    args = p.parse_args()
    token = os.getenv("DOSBOX_API_TOKEN", "")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", token):
        p.error("DOSBOX_API_TOKEN must be the full 64-character hex bearer token")
    if not (args.url.startswith("http://127.0.0.1:") or args.url.startswith("http://localhost:")):
        p.error("Refusing non-loopback API URL; use SSH local port forwarding")
    try:
        if args.cmd in ("status", "info"):
            endpoint = "/api/v1/status" if args.cmd == "status" else "/api/v1/dosbox/info"
            raw, _ = do_request(args.url, token, endpoint)
            print(json.dumps(json.loads(raw), indent=2, ensure_ascii=False))
        elif args.cmd == "screenshot":
            raw, _ = do_request(args.url, token, "/api/v1/video/frame?format=png&mode=raw")
            if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError("Expected PNG screenshot from emulator")
            save_bytes(args.output, raw)
        elif args.cmd == "memory":
            off = int(args.offset, 0)
            if not (0 <= off < 0x1000000 and 0 < args.length <= 1048576):
                raise RuntimeError("Offset must be 0..16 MiB and read length 1..1 MiB")
            raw, _ = do_request(args.url, token, f"/api/v1/memory/{hex(off)}/{args.length}")
            save_bytes(args.output, raw)
        else:
            if not re.fullmatch(r"KBD_[a-z0-9_]+", args.key_name):
                raise RuntimeError("Invalid DOSBox key name; expected e.g. KBD_enter")
            raw, _ = do_request(args.url, token, "/api/v1/input/sequence", method="POST", body={
                "events": [
                    {"type": "key", "key": args.key_name, "pressed": True, "t": 0},
                    {"type": "key", "key": args.key_name, "pressed": False, "t": 80},
                ]
            })
            print(json.dumps(json.loads(raw), indent=2, ensure_ascii=False))
    except (RuntimeError, ValueError, json.JSONDecodeError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
