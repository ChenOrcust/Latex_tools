@echo off
setlocal EnableExtensions

cd /d "%~dp0"
set "PROJECT_DIR=%CD%"
set "VENV_DIR=%PROJECT_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"


echo [LatexFormulaTool] Project dir: %PROJECT_DIR%

if not exist "%VENV_PYTHON%" (
    echo [LatexFormulaTool] .venv not found, preparing runtime...
    call :find_bootstrap_python
    if errorlevel 1 goto python_missing

    echo [LatexFormulaTool] Creating virtual environment: %VENV_DIR%
    "%BOOTSTRAP_PYTHON_EXE%" %BOOTSTRAP_PYTHON_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 goto venv_failed
)

echo [LatexFormulaTool] Python in use:
"%VENV_PYTHON%" --version
if errorlevel 1 goto venv_broken

echo.
echo [LatexFormulaTool] Checking dependencies...
"%VENV_PYTHON%" scripts\check_environment.py >nul 2>&1
if errorlevel 1 (
    echo [LatexFormulaTool] Missing dependencies detected, installing requirements...
    "%VENV_PYTHON%" -m pip install --upgrade pip
    if errorlevel 1 goto pip_failed

    "%VENV_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto deps_install_failed

    echo [LatexFormulaTool] Re-checking dependencies...
    "%VENV_PYTHON%" scripts\check_environment.py
    if errorlevel 1 goto deps_failed
) else (
    "%VENV_PYTHON%" scripts\check_environment.py
)

echo.
echo [LatexFormulaTool] Starting app...
"%VENV_PYTHON%" -m latex_formula_tool
if errorlevel 1 goto app_failed

goto done

:find_bootstrap_python
set "BOOTSTRAP_PYTHON_EXE="
set "BOOTSTRAP_PYTHON_ARGS="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        set "BOOTSTRAP_PYTHON_EXE=py"
        set "BOOTSTRAP_PYTHON_ARGS=-3"
    )
)

if not defined BOOTSTRAP_PYTHON_EXE (
    where python >nul 2>&1
    if not errorlevel 1 set "BOOTSTRAP_PYTHON_EXE=python"
)

if not defined BOOTSTRAP_PYTHON_EXE exit /b 1
exit /b 0

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
echo Delete "%VENV_DIR%" and rerun this script.
pause
exit /b 1

:pip_failed
echo.
echo [ERROR] Failed to upgrade pip in .venv.
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

:app_failed
echo.
echo [ERROR] App exited with an error.
pause
exit /b 1

:done
endlocal
