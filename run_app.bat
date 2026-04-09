@echo off
setlocal

set "ENV_NAME=pyqt6"
cd /d "%~dp0"

echo [LatexFormulaTool] Project dir: %CD%
echo [LatexFormulaTool] Activating conda env: %ENV_NAME%

set "CONDA_BAT="
if exist "%USERPROFILE%\anaconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\anaconda3\condabin\conda.bat"
if exist "%USERPROFILE%\miniconda3\condabin\conda.bat" set "CONDA_BAT=%USERPROFILE%\miniconda3\condabin\conda.bat"
if exist "D:\anaconda3\condabin\conda.bat" set "CONDA_BAT=D:\anaconda3\condabin\conda.bat"
if exist "D:\miniconda3\condabin\conda.bat" set "CONDA_BAT=D:\miniconda3\condabin\conda.bat"

if defined CONDA_BAT (
    call "%CONDA_BAT%" activate "%ENV_NAME%"
) else (
    call conda activate "%ENV_NAME%"
)

if errorlevel 1 goto conda_failed

echo [LatexFormulaTool] Python:
python --version

echo.
echo [LatexFormulaTool] Checking dependencies...
python scripts\check_environment.py
if errorlevel 1 goto deps_failed

echo.
echo [LatexFormulaTool] Starting app...
python -m latex_formula_tool
if errorlevel 1 goto app_failed

goto done

:conda_failed
echo.
echo [ERROR] Failed to activate conda env "%ENV_NAME%".
echo Run this command to check the env name:
echo   conda env list
pause
exit /b 1

:deps_failed
echo.
echo [ERROR] Dependency check failed.
echo Install dependencies in the pyqt6 env:
echo   conda activate pyqt6
echo   cd /d "%~dp0"
echo   pip install -r requirements.txt
pause
exit /b 1

:app_failed
echo.
echo [ERROR] App exited with an error.
pause
exit /b 1

:done
endlocal

