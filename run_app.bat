@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_CFG=%VENV_DIR%\pyvenv.cfg"
set "BOOTSTRAP_PYTHON="

echo [LatexFormulaTool] Project dir: %PROJECT_DIR%

if exist "%VENV_DIR%" if not exist "%VENV_PYTHON%" goto repair_venv
if exist "%VENV_PYTHON%" if not exist "%VENV_CFG%" goto repair_venv

if not exist "%VENV_PYTHON%" (
    echo [LatexFormulaTool] .venv not found, preparing runtime...
    call :resolve_bootstrap_python
    if errorlevel 1 goto python_missing
)

if not exist "%VENV_PYTHON%" (
    echo [LatexFormulaTool] Creating virtual environment: %VENV_DIR%
    call %BOOTSTRAP_PYTHON% -m venv "%VENV_DIR%"
    if errorlevel 1 goto venv_failed
)

echo [LatexFormulaTool] Python in use:
"%VENV_PYTHON%" --version
if errorlevel 1 goto venv_broken
"%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if errorlevel 1 goto wrong_python

echo.
echo [LatexFormulaTool] Checking dependencies...
"%VENV_PYTHON%" scripts\check_environment.py >nul 2>&1
if errorlevel 1 (
    echo [LatexFormulaTool] Missing dependencies detected, installing requirements...
    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto deps_install_failed

    echo [LatexFormulaTool] Re-checking dependencies...
    "%VENV_PYTHON%" scripts\check_environment.py
    if errorlevel 1 goto deps_failed
) else (
    "%VENV_PYTHON%" scripts\check_environment.py
)

echo.
echo [LatexFormulaTool] Ensuring bundled Pandoc...
"%VENV_PYTHON%" scripts\install_pandoc.py
if errorlevel 1 goto pandoc_install_failed

echo.
echo [LatexFormulaTool] Starting app...
"%VENV_PYTHON%" -m latex_formula_tool
if errorlevel 1 goto app_failed

goto done

:repair_venv
echo [LatexFormulaTool] Broken .venv detected, recreating...
call :resolve_bootstrap_python
if errorlevel 1 goto python_missing
if exist "%VENV_DIR%" rmdir /s /q "%VENV_DIR%"
if exist "%VENV_DIR%" goto venv_broken
echo [LatexFormulaTool] Creating virtual environment: %VENV_DIR%
call %BOOTSTRAP_PYTHON% -m venv "%VENV_DIR%"
if errorlevel 1 goto venv_failed
goto :after_repair

:resolve_bootstrap_python
set "BOOTSTRAP_PYTHON="
for /f "delims=" %%I in ('where.exe py 2^>nul') do (
    py -3.11 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PYTHON=py -3.11"
        exit /b 0
    )
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PYTHON=py -3"
        exit /b 0
    )
)
for /f "delims=" %%I in ('where.exe python 2^>nul') do (
    set "BOOTSTRAP_PYTHON=python"
    exit /b 0
)
exit /b 1

:after_repair

:python_missing
echo.
echo [ERROR] No usable Python found.
echo Install Python 3.10+ first, then rerun this script.
pause
exit /b 1

:venv_failed
echo.
echo [ERROR] Failed to create .venv.
pause
exit /b 1

:venv_broken
echo.
echo [ERROR] .venv exists but is not usable.
echo Close any process using "%VENV_DIR%" , delete it, then rerun this script.
pause
exit /b 1

:wrong_python
echo.
echo [ERROR] .venv was not created with Python 3.11.
echo Delete "%VENV_DIR%" and rerun this script. The launcher now prefers py -3.11.
pause
exit /b 1

:deps_install_failed
echo.
echo [ERROR] Failed to install dependencies from requirements.txt.
pause
exit /b 1

:deps_failed
echo.
echo [ERROR] Dependency check still failed after auto install.
echo Please inspect the log above.
pause
exit /b 1

:pandoc_install_failed
echo.
echo [ERROR] Failed to install bundled Pandoc.
pause
exit /b 1

:app_failed
echo.
echo [ERROR] App exited with an error.
pause
exit /b 1

:done
endlocal
