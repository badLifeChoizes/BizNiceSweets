@echo off
REM Update Documentation Checklist after documenting a file
REM
REM Usage:
REM   update_docs_checklist.bat path\to\file.ts
REM   update_docs_checklist.bat path\to\file.ts "Added comprehensive JSDoc comments"

setlocal enabledelayedexpansion

set FILE_PATH=%~1
set NOTES=%~2

if "%FILE_PATH%"=="" (
    echo Error: File path required
    echo Usage: %~nx0 ^<file_path^> [notes]
    exit /b 1
)

if not exist "%FILE_PATH%" (
    echo Error: File not found: %FILE_PATH%
    exit /b 1
)

REM Get script directory
set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Find project root (directory containing .claude)
set CURRENT_DIR=%CD%
set PROJECT_ROOT=

:find_root
if exist "%CURRENT_DIR%\.claude" (
    set PROJECT_ROOT=%CURRENT_DIR%
    goto :found_root
)
for %%i in ("%CURRENT_DIR%") do set PARENT_DIR=%%~dpi
set PARENT_DIR=%PARENT_DIR:~0,-1%
if "%PARENT_DIR%"=="%CURRENT_DIR%" (
    goto :found_root
)
set CURRENT_DIR=%PARENT_DIR%
goto :find_root

:found_root
if "%PROJECT_ROOT%"=="" (
    echo Warning: Could not find project root ^(.claude directory^)
    set PROJECT_ROOT=%CD%
)

REM Find the most recent documentation analysis directory
set DOC_ANALYSIS_DIR=%PROJECT_ROOT%\docs\documentation-analysis

if not exist "%DOC_ANALYSIS_DIR%" (
    echo Error: Documentation analysis directory not found: %DOC_ANALYSIS_DIR%
    exit /b 1
)

REM Get the most recent dated directory (simple approach - use current date format)
for /f "delims=" %%d in ('dir /b /ad /o-n "%DOC_ANALYSIS_DIR%\20*" 2^>nul') do (
    set LATEST_DIR=%DOC_ANALYSIS_DIR%\%%d
    goto :found_latest
)

:found_latest
if "%LATEST_DIR%"=="" (
    echo Error: No dated analysis directories found in %DOC_ANALYSIS_DIR%
    exit /b 1
)

echo.
echo Documentation Checklist Updater
echo ================================================================
echo.
for %%i in ("%LATEST_DIR%") do echo Analysis directory: %%~nxi
echo File: %FILE_PATH%
echo.

REM Find checklists
set YAML_CHECKLIST=%LATEST_DIR%\documentation-checklist.yml
set MARKDOWN_CHECKLIST=%LATEST_DIR%\DOCUMENTATION_CHECKLIST.md

if not exist "%YAML_CHECKLIST%" if not exist "%MARKDOWN_CHECKLIST%" (
    echo Error: No checklists found in %LATEST_DIR%
    echo    Expected: documentation-checklist.yml or DOCUMENTATION_CHECKLIST.md
    exit /b 1
)

REM Step 1: Re-analyze the file
echo Step 1: Re-analyzing file for documentation coverage...
echo.

python -X utf8 "%SCRIPT_DIR%\analyze.py" "%FILE_PATH%" 2>&1

echo.

REM Get relative file path for checklist update
set RELATIVE_PATH=%FILE_PATH%
set RELATIVE_PATH=%RELATIVE_PATH:*command-center\=%

REM Step 2: Update YAML checklist if it exists
if exist "%YAML_CHECKLIST%" (
    echo Step 2a: Updating YAML checklist...

    if "%NOTES%"=="" (
        python -X utf8 "%SCRIPT_DIR%\update_checklist.py" "%YAML_CHECKLIST%" --file "%RELATIVE_PATH%" --status completed
    ) else (
        python -X utf8 "%SCRIPT_DIR%\update_checklist.py" "%YAML_CHECKLIST%" --file "%RELATIVE_PATH%" --status completed --notes "%NOTES%"
    )
    echo.
)

REM Step 3: Update Markdown checklist if it exists
if exist "%MARKDOWN_CHECKLIST%" (
    echo Step 2b: Updating Markdown checklist...
    echo    Manual update required for Markdown checklist
    echo    File: %MARKDOWN_CHECKLIST%
    echo    Pattern to find: %RELATIVE_PATH%
    echo    Change: [ ] to [x] if coverage ^>= 100%%
    echo.
)

echo ================================================================
echo Checklist update complete!
echo.

endlocal
exit /b 0
