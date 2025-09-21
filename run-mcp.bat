@echo off
setlocal
REM Resolve repo root and make src importable without install
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"

REM Pick a Python: prefer venv, else py launcher, else python
set "PYCMD="
if exist "%ROOT%.venv\Scripts\python.exe" set "PYCMD=%ROOT%.venv\Scripts\python.exe"
if not defined PYCMD where py >nul 2>nul && set "PYCMD=py"
if not defined PYCMD set "PYCMD=python"

echo [run] %PYCMD% -m mcp_server.server stdio
%PYCMD% -m mcp_server.server stdio
endlocal