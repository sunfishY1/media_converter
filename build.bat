@echo off
setlocal

cd /d "%~dp0"
set "PYINSTALLER=%~dp0.venv-win\Scripts\pyinstaller.exe"

if not exist "%PYINSTALLER%" (
    echo Cannot find PyInstaller in the project's Python environment:
    echo   %PYINSTALLER%
    echo.
    echo Activate .venv-win and run: pip install pyinstaller
    pause
    exit /b 1
)

if not exist "%~dp0bin\ffmpeg.exe" (
    echo Warning: %~dp0bin\ffmpeg.exe not found. The built .exe will still
    echo run, but conversions will fail on PCs that don't have ffmpeg on PATH.
    echo Place ffmpeg.exe / ffprobe.exe in the project's bin\ folder before
    echo building so they get copied into dist\bin\ automatically.
)

"%PYINSTALLER%" "%~dp0MediaConverter.spec" --noconfirm
set "BUILD_EXIT=%ERRORLEVEL%"

if not "%BUILD_EXIT%"=="0" (
    echo.
    echo Build failed with code %BUILD_EXIT%.
    pause
    exit /b %BUILD_EXIT%
)

if exist "%~dp0bin" (
    echo Copying bin\ (ffmpeg/ffprobe) next to the built exe...
    rem xcopy can prompt "File or directory?" when the destination folder
    rem doesn't exist yet, which silently hangs/skips when run non-interactively.
    rem Creating the destination first and using a trailing-slash + wildcard
    rem source avoids that prompt entirely.
    if not exist "%~dp0dist\bin" mkdir "%~dp0dist\bin"
    xcopy /e /y "%~dp0bin\*" "%~dp0dist\bin\" >nul
    if not exist "%~dp0dist\bin\ffmpeg.exe" (
        echo.
        echo Warning: dist\bin\ffmpeg.exe is still missing after copying.
        echo Copy %~dp0bin\ into dist\bin\ manually before shipping dist\.
    )
)

echo.
echo Build finished: dist\MediaConverter.exe
echo Ship the whole dist\ folder (exe + bin\) together.
pause
exit /b 0
