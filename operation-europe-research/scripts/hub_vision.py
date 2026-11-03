"""Ask a local vision model of Agent Hub about a screenshot without passing the image through the cloud agent.

Calls the hub MCP tool hub_model_run over HTTP (JSON-RPC). Token: env AGENT_HUB_TOKEN. private=true keeps the
image on LAN backends. Usage: python -I hub_vision.py IMAGE "question" [--crop x0,y0,x1,y1]
"""
import argparse
import base64
import io
import json
import os
import urllib.request

from PIL import Image

URL = os.environ.get("AGENT_HUB_MCP", "http://192.168.8.150:7800/mcp?client=claudecode&machine=win")


def rpc(method, params, session=None, rid=1):
    body = json.dumps(dict(jsonrpc="2.0", id=rid, method=method, params=params)).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
               "Authorization": "Bearer " + os.environ.get("AGENT_HUB_TOKEN", "")}
    if session:
        headers["Mcp-Session-Id"] = session
    with urllib.request.urlopen(urllib.request.Request(URL, body, headers), timeout=600) as r:
        sid = r.headers.get("Mcp-Session-Id") or session
        text = r.read().decode("utf-8")
    if text.lstrip().startswith("data:") or "\ndata:" in text:
        text = [ln[5:] for ln in text.splitlines() if ln.startswith("data:")][-1]
    return json.loads(text), sid


def ask(image, question, crop=None, backend=None):
    im = Image.open(image).convert("RGB")
    if crop:
        im = im.crop(crop)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    _, sid = rpc("initialize", dict(protocolVersion="2025-03-26", capabilities={},
                                    clientInfo=dict(name="hub_vision", version="1")))
    # The hub requires a registered session; reuse the calling agent's native session id (env HUB_SESSION_ID).
    rpc("tools/call", dict(name="hub_session", arguments=dict(
        session_id=os.environ["HUB_SESSION_ID"], title="hub_vision helper")), sid, 3)
    args =dict(kind="vision", private=True, prompt=question,
                images=[dict(mime="image/png", base64=base64.b64encode(buf.getvalue()).decode())])
    if backend:
        args["backend"] = backend
    res, _ = rpc("tools/call", dict(name="hub_model_run", arguments=args), sid, 2)
    content = res.get("result", {}).get("content", [{}])
    raw = content[0].get("text", "") if content else json.dumps(res)
    try:
        data = json.loads(raw)
    except ValueError:  # tool error text, not JSON
        return raw, None
    return data.get("text", raw), data.get("backend")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("image")
    ap.add_argument("question")
    ap.add_argument("--crop", type=lambda s: tuple(int(v) for v in s.split(",")))
    ap.add_argument("--backend")
    a = ap.parse_args()
    text, backend = ask(a.image, a.question, a.crop, a.backend)
    print(f"[{backend}] {text}")
