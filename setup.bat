@echo off
REM Dochive Setup Script for Windows
REM Cross-platform installer for AI IDE skills (OpenCode, Claude Code, Codex, Cursor)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "SKILLS_DIR=%SCRIPT_DIR%skills"

REM Supported IDE configurations
set "IDES=opencode claude codex cursor"

REM Skills to install
set "SKILLS=dochive-mirror dochive-mirror-verify"

REM Flags
set "FLAG_ALL=false"
set "FLAG_GLOBAL=false"
set "FLAG_LIST=false"
set "FLAG_FORCE=false"
set "FLAG_CREATE_RESULTS=false"
set "TARGET_IDE=""

REM Colors (not supported in standard cmd, but we can try with ANSI if enabled)
REM We'll stick to plain text for maximum compatibility

:usage
if "%1"=="-h" goto show_usage
if "%1"=="--help" goto show_usage
goto parse_args

:show_usage
echo Dochive Setup - install skills for your AI IDE
echo.
echo Usage:
echo   setup.bat [options]
echo.
echo Options:
echo   --all                Install to all detected IDE configurations
echo   --global             Install to global/user configuration (%%USERPROFILE%%\.
echo   --target ^<ide^>       Install to specific IDE (opencode^|claude^|codex^|cursor)
echo   --list               Show what would be installed without copying (dry-run)
echo   --force              Overwrite existing skills without prompting
echo   --create-results-dir Create dochive-mirror-runs\ directory
echo   -h, --help           Show this help message
echo.
echo Examples:
echo   setup.bat                    # Auto-detect IDE in current project
echo   setup.bat --all              # Install to all detected IDEs
echo   setup.bat --target claude    # Install to Claude Code only
echo   setup.bat --global           # Install to global user config
echo   setup.bat --list             # Preview what will happen
goto :eof

:parse_args
if "%1"=="" goto check_skills
if "%1"=="--all" (
    set "FLAG_ALL=true"
    shift
    goto parse_args
)
if "%1"=="--global" (
    set "FLAG_GLOBAL=true"
    shift
    goto parse_args
)
if "%1"=="--target" (
    if "%~2"=="" (
        echo [ERROR] --target requires an argument (opencode^|claude^|codex^|cursor)
        exit /b 1
    )
    set "TARGET_IDE=%~2"
    shift
    shift
    goto parse_args
)
if "%1"=="--list" (
    set "FLAG_LIST=true"
    shift
    goto parse_args
)
if "%1"=="--force" (
    set "FLAG_FORCE=true"
    shift
    goto parse_args
)
if "%1"=="--create-results-dir" (
    set "FLAG_CREATE_RESULTS=true"
    shift
    goto parse_args
)
if "%1"=="-h" goto show_usage
if "%1"=="--help" goto show_usage

echo [ERROR] Unknown option: %1
goto show_usage

:check_skills
if not exist "%SKILLS_DIR%" (
    echo [ERROR] Skills directory not found: %SKILLS_DIR%
    echo [INFO] Make sure you run this script from the repository root.
    exit /b 1
)

REM Detect IDE configurations in current project
set "DETECTED_IDES=""
for %%i in (%IDES%) do (
    call :check_ide %%i
)

goto determine_targets

:check_ide
set "IDE=%1"
if "%IDE%"=="opencode" set "DIR=.opencode\skills"
if "%IDE%"=="claude" set "DIR=.claude\skills"
if "%IDE%"=="codex" set "DIR=.codex\skills"
if "%IDE%"=="cursor" set "DIR=.cursor\skills"

if exist "%SCRIPT_DIR%%DIR%" (
    if "!DETECTED_IDES!"=="" (
        set "DETECTED_IDES=%IDE%"
    ) else (
        set "DETECTED_IDES=!DETECTED_IDES! %IDE%"
    )
)
goto :eof

:get_target_dir
set "IDE=%1"
if "%FLAG_GLOBAL%"=="true" (
    if "%IDE%"=="opencode" set "RESULT=%USERPROFILE%\.opencode\skills"
    if "%IDE%"=="claude" set "RESULT=%USERPROFILE%\.claude\skills"
    if "%IDE%"=="codex" set "RESULT=%USERPROFILE%\.codex\skills"
    if "%IDE%"=="cursor" set "RESULT=%USERPROFILE%\.cursor\skills"
) else (
    if "%IDE%"=="opencode" set "RESULT=%SCRIPT_DIR%.opencode\skills"
    if "%IDE%"=="claude" set "RESULT=%SCRIPT_DIR%.claude\skills"
    if "%IDE%"=="codex" set "RESULT=%SCRIPT_DIR%.codex\skills"
    if "%IDE%"=="cursor" set "RESULT=%SCRIPT_DIR%.cursor\skills"
)
goto :eof

:determine_targets
set "TARGETS=""

if not "%TARGET_IDE%"=="" (
    set "VALID=false"
    for %%i in (%IDES%) do (
        if "%%i"=="%TARGET_IDE%" set "VALID=true"
    )
    if "%VALID%"=="false" (
        echo [ERROR] Unknown IDE: %TARGET_IDE%
        echo [INFO] Supported: %IDES%
        exit /b 1
    )
    set "TARGETS=%TARGET_IDE%"
) else (
    if "%DETECTED_IDES%"=="" (
        if "%FLAG_GLOBAL%"=="true" (
            set "TARGETS=%IDES%"
        ) else (
            echo [WARN] No IDE configuration detected in current project.
            echo [INFO] Detected IDE configs look for directories like: .opencode\, .claude\, .codex\, .cursor\
            echo [INFO] You can:
            echo   - Run with --target ^<ide^> to force a specific IDE
            echo   - Run with --global to install to user config
            echo   - Initialize your IDE config first
            echo.
            echo [INFO] Or copy skills manually:
            for %%s in (%SKILLS%) do (
                echo   xcopy /E /I skills\%%s %%USERPROFILE%%\.opencode\skills\
            )
            goto :eof
        )
    ) else (
        if "%FLAG_ALL%"=="true" (
            set "TARGETS=%DETECTED_IDES%"
        ) else (
            REM Pick the first detected one
            for /f "tokens=1" %%a in ("%DETECTED_IDES%") do set "TARGETS=%%a"
            set "COUNT=0"
            for %%a in (%DETECTED_IDES%) do set /a "COUNT+=1"
            if %COUNT% gtr 1 (
                echo [WARN] Multiple IDE configs detected: %DETECTED_IDES%
                echo [INFO] Use --all to install to all, or --target ^<ide^> to pick one.
                echo [INFO] Defaulting to first detected: %TARGETS%
            )
        )
    )
)

goto main

:install_skill
set "SKILL=%1"
set "TARGET_DIR=%2"
set "SKILL_SRC=%SKILLS_DIR%\%SKILL%"
set "SKILL_DST=%TARGET_DIR%\%SKILL%"

if not exist "%SKILL_SRC%" (
    echo [WARN] Skill source not found: %SKILL_SRC%
    goto :eof
)

if exist "%SKILL_DST%" (
    if "%FLAG_FORCE%"=="true" (
        echo [INFO] Overwriting existing skill: %SKILL_DST%
        rmdir /S /Q "%SKILL_DST%"
    ) else (
        echo [WARN] Skill already exists: %SKILL_DST%
        set /p "answer=Overwrite? [y/N]: "
        if /I not "!answer!"=="y" (
            echo [INFO] Skipping %SKILL%
            goto :eof
        )
        rmdir /S /Q "%SKILL_DST%"
    )
)

if not exist "%TARGET_DIR%" mkdir "%TARGET_DIR%"
xcopy /E /I /Q "%SKILL_SRC%" "%SKILL_DST%"
echo [OK] Installed %SKILL% -^> %SKILL_DST%
goto :eof

:main
echo.
echo ==============================================
echo      Dochive Skill Installer
echo ==============================================
echo.

if "%TARGETS%"=="" goto :eof

REM List mode
if "%FLAG_LIST%"=="true" (
    echo [INFO] Dry-run mode. Would install to:
    for %%i in (%TARGETS%) do (
        call :get_target_dir %%i
        echo   [%%i] -^> %RESULT%
        for %%s in (%SKILLS%) do (
            echo     - %%s
        )
    )
    goto :eof
)

REM Perform installation
for %%i in (%TARGETS%) do (
    call :get_target_dir %%i
    set "TARGET_DIR=!RESULT!"
    echo [INFO] Installing to [%%i] -^> !TARGET_DIR!
    for %%s in (%SKILLS%) do (
        call :install_skill %%s "!TARGET_DIR!"
    )
)

REM Create results directory if requested
if "%FLAG_CREATE_RESULTS%"=="true" (
    set "RESULTS_DIR=%SCRIPT_DIR%dochive-mirror-runs"
    if not exist "!RESULTS_DIR!" mkdir "!RESULTS_DIR!"
    echo [OK] Created results directory: !RESULTS_DIR!
)

echo.
echo [OK] Installation complete!
echo.
echo Next steps:
for %%i in (%TARGETS%) do (
    if "%%i"=="opencode" echo   - OpenCode: skills available automatically if in .opencode\skills\
    if "%%i"=="claude" echo   - Claude Code: use /dochive-mirror or /dochive-mirror-verify to invoke
    if "%%i"=="codex" echo   - Codex: skills loaded from .codex\skills\
    if "%%i"=="cursor" echo   - Cursor: check .cursor\ settings for custom instructions
)
echo.

goto :eof
