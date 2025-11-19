@echo off
setlocal enabledelayedexpansion

REM Name des Virtual Environments
set VENV_DIR=venv

REM Pfad zu requirements.txt
set REQ_FILE=requirements.txt

REM Python finden
where py >nul 2>&1
if %errorlevel%==0 (
    set PYEXEC=py
) else (
    where python >nul 2>&1
    if %errorlevel%==0 (
        set PYEXEC=python
    ) else (
        echo Fehler: Kein Python gefunden.
        pause
        exit /b 1
    )
)

echo.
echo --- Pruefe Virtual Environment ---

IF NOT EXIST "%VENV_DIR%\Scripts\python.exe" (
    echo Kein venv gefunden - erzeuge neues venv...
    %PYEXEC% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo Fehler beim Erstellen des venv.
        pause
        exit /b 1
    )

    echo Installiere Pakete aus %REQ_FILE% ...
    call "%VENV_DIR%\Scripts\activate.bat"
    
    "%VENV_DIR%\Scripts\python.exe" -m pip install --upgrade pip
    "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%REQ_FILE%"
    if %errorlevel% neq 0 (
        echo Fehler beim Installieren der Pakete.
        pause
        exit /b 1
    )
) ELSE (
    echo venv existiert bereits - aktiviere...
    call "%VENV_DIR%\Scripts\activate.bat"
    
    echo.
    echo --- Synchronisiere Pakete mit requirements.txt ---
    
    REM Temporäre Dateien
    set TEMP_INSTALLED=temp_installed.txt
    set TEMP_REQUIRED=temp_required.txt
    set TEMP_DEPENDENCIES=temp_dependencies.txt
    
    REM Liste installierter Pakete
    "%VENV_DIR%\Scripts\python.exe" -m pip list --format=freeze > "!TEMP_INSTALLED!"
    
    REM Extrahiere Paketnamen aus requirements.txt
    if exist "!TEMP_REQUIRED!" del "!TEMP_REQUIRED!"
    for /f "tokens=1 delims==><!~" %%a in (%REQ_FILE%) do (
        set line=%%a
        REM Entferne Leerzeichen
        set line=!line: =!
        if not "!line!"=="" echo !line!>> "!TEMP_REQUIRED!"
    )
    
    REM Erstelle Liste aller Abhängigkeiten der requirements
    echo Ermittle Abhaengigkeiten...
    if exist "!TEMP_DEPENDENCIES!" del "!TEMP_DEPENDENCIES!"
    
    REM Kopiere requirements in dependencies
    type "!TEMP_REQUIRED!" > "!TEMP_DEPENDENCIES!"
    
    REM Hole Abhängigkeiten für jedes Paket
    for /f %%a in (!TEMP_REQUIRED!) do (
        "%VENV_DIR%\Scripts\python.exe" -m pip show %%a 2>nul | findstr /i "Requires:" > temp_deps_line.txt
        for /f "tokens=2*" %%b in (temp_deps_line.txt) do (
            set DEPS=%%b
            set DEPS=!DEPS:,= !
            for %%d in (!DEPS!) do (
                echo %%d>> "!TEMP_DEPENDENCIES!"
            )
        )
    )
    if exist temp_deps_line.txt del temp_deps_line.txt
    
    REM Prüfe fehlende Pakete
    echo Pruefe fehlende Pakete...
    set MISSING=0
    for /f %%a in (!TEMP_REQUIRED!) do (
        set FOUND=0
        for /f "tokens=1 delims==" %%b in (!TEMP_INSTALLED!) do (
            if /i "%%a"=="%%b" set FOUND=1
        )
        if !FOUND!==0 (
            echo   Fehlt: %%a
            set MISSING=1
        )
    )
    
    if !MISSING!==1 (
        echo.
        echo Installiere fehlende Pakete...
        "%VENV_DIR%\Scripts\python.exe" -m pip install -r "%REQ_FILE%"
        if %errorlevel% neq 0 (
            echo Warnung: Fehler beim Installieren einiger Pakete.
        )
    ) else (
        echo Alle benoetigten Pakete sind installiert.
    )
    

    
    REM Aufräumen
    if exist "!TEMP_INSTALLED!" del "!TEMP_INSTALLED!"
    if exist "!TEMP_REQUIRED!" del "!TEMP_REQUIRED!"
    if exist "!TEMP_DEPENDENCIES!" del "!TEMP_DEPENDENCIES!"
)

echo.
echo --- Starte main.py im venv ---
"%VENV_DIR%\Scripts\python.exe" main.py

pause
endlocal
exit /b 0