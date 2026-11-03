"""Stdio MCP probe for pyghidra-mcp: initialize, list tools, dump JSON summary."""
import asyncio, json, sys, time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main(out, binary, project, calls):
    params = StdioServerParameters(
        command=r"C:\oe-tools\venv\Scripts\pyghidra-mcp.exe",
        args=["--project-path", project, "--project-name", "mcp002", "--wait-for-analysis", binary],
        env={"GHIDRA_INSTALL_DIR": r"C:\Tools\ghidra_12.2_PUBLIC", "JAVA_HOME": r"C:\Program Files\Eclipse Adoptium\jdk-25.0.4.101-hotspot", "SystemRoot": r"C:\Windows", "PATH": r"C:\oe-tools\venv\Scripts;C:\Windows\System32", "TEMP": r"C:\oe-tools\tmp", "TMP": r"C:\oe-tools\tmp"},
    )
    res = {"steps": []}
    t0 = time.time()
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            init = await s.initialize()
            res["initialize"] = {"server": init.server_info.name, "version": init.server_info.version, "seconds": round(time.time() - t0, 1)}
            tools = await s.list_tools()
            res["tools"] = [{"name": t.name, "args": list((t.input_schema or {}).get("properties", {}).keys())} for t in tools.tools]
            for name, args in calls:
                t1 = time.time()
                try:
                    r_ = await s.call_tool(name, args)
                    text = "\n".join(getattr(c, "text", "") for c in r_.content)
                    res["steps"].append({"tool": name, "args": args, "error": r_.is_error, "seconds": round(time.time() - t1, 1), "text": text})
                except Exception as e:
                    res["steps"].append({"tool": name, "args": args, "exception": repr(e)})
    open(out, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({"init": res["initialize"], "tools": [t["name"] for t in res["tools"]], "steps": [(x["tool"], x.get("error"), x.get("seconds"), len(x.get("text", ""))) for x in res["steps"]]}, ensure_ascii=False))

if __name__ == "__main__":
    out, binary, project = sys.argv[1:4]
    calls = json.loads(sys.argv[4]) if len(sys.argv) > 4 else []
    asyncio.run(main(out, binary, project, calls))
