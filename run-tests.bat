@echo off
REM Windows batch script to run tests

echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Installing test dependencies...
python -m pip install pytest pytest-asyncio responses beautifulsoup4

echo Running tests with coverage...
python -m pytest tests/ -v --tb=short

echo.
echo Test run complete!
pause