@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem Rebuild markdown docs to HTML/PDF in this folder.
rem Required: pandoc
rem Optional for PDF: Chrome or Edge (headless mode)

set "ROOT_DIR=%~dp0"
pushd "%ROOT_DIR%" >nul 2>nul || (
    echo [ERROR] Cannot enter script directory.
    exit /b 1
)

where pandoc >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pandoc is not installed or not in PATH.
    popd
    exit /b 1
)

set "BROWSER_EXE="
if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_EXE if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" set "BROWSER_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
if not defined BROWSER_EXE if exist "C:\Program Files\Microsoft\Edge\Application\msedge.exe" set "BROWSER_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if not defined BROWSER_EXE if exist "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" set "BROWSER_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

call :build_one documents_developer || goto :fail
if exist "documents_teacher.md" call :build_one documents_teacher || goto :fail

echo [OK] Document build completed.
popd
exit /b 0

:build_one
set "BASE=%~1"
echo [INFO] Building %BASE%.md

pandoc "%BASE%.md" -s -o "%BASE%.html"
if errorlevel 1 (
    echo [ERROR] HTML build failed for %BASE%.md
    exit /b 1
)

if not defined BROWSER_EXE (
    echo [WARN] Browser not found. PDF skipped for %BASE%.
    exit /b 0
)

set "TMP_PROFILE=%TEMP%\headless-doc-%BASE%-%RANDOM%-%RANDOM%"
mkdir "%TMP_PROFILE%" >nul 2>nul

set "HTML_URI=file:///%CD:\=/%/%BASE%.html"
"%BROWSER_EXE%" --headless=new --disable-gpu --user-data-dir="%TMP_PROFILE%" --allow-file-access-from-files --print-to-pdf="%CD%\%BASE%.pdf" "%HTML_URI%" >nul 2>nul
set "BROWSER_CODE=%ERRORLEVEL%"

rmdir /s /q "%TMP_PROFILE%" >nul 2>nul

if not "%BROWSER_CODE%"=="0" (
    echo [ERROR] PDF build failed for %BASE%.html
    exit /b 1
)

echo [OK] Built %BASE%.html and %BASE%.pdf
exit /b 0

:fail
echo [ERROR] Document build failed.
popd
exit /b 1