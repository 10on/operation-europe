@echo off
rem stdio Ghidra MCP server for an agent: pyghidra_mcp.cmd claude^|codex
rem Each client gets its own Ghidra project (a project cannot be opened by two processes).
rem Install: scripts\setup_pyghidra_mcp.ps1
setlocal
set "CLIENT=%~1"
if "%CLIENT%"=="" set "CLIENT=claude"
rem Ghidra ProjectLocator rejects paths containing "..", so resolve it first
for %%I in ("%~dp0..") do set "OE=%%~fI"
set "GHIDRA_INSTALL_DIR=C:\Tools\ghidra_12.2_PUBLIC"
set "TEMP=C:\oe-tools\tmp"
set "TMP=C:\oe-tools\tmp"
rem UTF-8 stderr: Codex stops reading a non-UTF-8 stderr stream (Cyrillic paths in log lines)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
"C:\oe-tools\venv\Scripts\pyghidra-mcp.exe" --project-path "%OE%\private\mcp-002\project-%CLIENT%" --project-name "oe-%CLIENT%" --wait-for-analysis "%OE%\private\mcp-002\main.exe"
