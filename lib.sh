#!/bin/bash

# Name des Virtual Environments
VENV_DIR="venv"

# Pfad zu requirements.txt
REQ_FILE="requirements.txt"

# Python finden
if command -v python3 &> /dev/null; then
    PYEXEC="python3"
elif command -v python &> /dev/null; then
    PYEXEC="python"
else
    echo "Fehler: Kein Python gefunden."
    exit 1
fi

echo ""
echo "--- Pruefe Virtual Environment ---"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "Kein venv gefunden - erzeuge neues venv..."
    $PYEXEC -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "Fehler beim Erstellen des venv."
        exit 1
    fi

    echo "Installiere Pakete aus $REQ_FILE ..."
    source "$VENV_DIR/bin/activate"
    
    "$VENV_DIR/bin/python" -m pip install --upgrade pip
    "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
    if [ $? -ne 0 ]; then
        echo "Fehler beim Installieren der Pakete."
        exit 1
    fi
else
    echo "venv existiert bereits - aktiviere..."
    source "$VENV_DIR/bin/activate"
    
    echo ""
    echo "--- Synchronisiere Pakete mit requirements.txt ---"
    
    # Temporäre Dateien
    TEMP_INSTALLED="temp_installed.txt"
    TEMP_REQUIRED="temp_required.txt"
    TEMP_DEPENDENCIES="temp_dependencies.txt"
    
    # Liste installierter Pakete
    "$VENV_DIR/bin/python" -m pip list --format=freeze > "$TEMP_INSTALLED"
    
    # Extrahiere Paketnamen aus requirements.txt
    > "$TEMP_REQUIRED"
    while IFS= read -r line; do
        # Entferne Kommentare und Leerzeichen
        pkg=$(echo "$line" | sed 's/#.*//' | sed 's/[=><!~].*//' | tr -d ' ')
        if [ -n "$pkg" ]; then
            echo "$pkg" >> "$TEMP_REQUIRED"
        fi
    done < "$REQ_FILE"
    
    # Erstelle Liste aller Abhängigkeiten der requirements
    echo "Ermittle Abhaengigkeiten..."
    cp "$TEMP_REQUIRED" "$TEMP_DEPENDENCIES"
    
    # Hole Abhängigkeiten für jedes Paket
    while IFS= read -r pkg; do
        deps=$("$VENV_DIR/bin/python" -m pip show "$pkg" 2>/dev/null | grep -i "Requires:" | cut -d: -f2 | tr ',' '\n' | tr -d ' ')
        if [ -n "$deps" ]; then
            echo "$deps" >> "$TEMP_DEPENDENCIES"
        fi
    done < "$TEMP_REQUIRED"
    
    # Prüfe fehlende Pakete
    echo "Pruefe fehlende Pakete..."
    MISSING=0
    while IFS= read -r pkg; do
        FOUND=0
        while IFS= read -r installed; do
            installed_name=$(echo "$installed" | cut -d= -f1)
            if [ "$(echo "$pkg" | tr '[:upper:]' '[:lower:]')" == "$(echo "$installed_name" | tr '[:upper:]' '[:lower:]')" ]; then
                FOUND=1
                break
            fi
        done < "$TEMP_INSTALLED"
        
        if [ $FOUND -eq 0 ]; then
            echo "  Fehlt: $pkg"
            MISSING=1
        fi
    done < "$TEMP_REQUIRED"
    
    if [ $MISSING -eq 1 ]; then
        echo ""
        echo "Installiere fehlende Pakete..."
        "$VENV_DIR/bin/python" -m pip install -r "$REQ_FILE"
        if [ $? -ne 0 ]; then
            echo "Warnung: Fehler beim Installieren einiger Pakete."
        fi
    else
        echo "Alle benoetigten Pakete sind installiert."
    fi
    
    # Aufräumen
    rm -f "$TEMP_INSTALLED" "$TEMP_REQUIRED" "$TEMP_DEPENDENCIES"
fi

echo ""
echo "--- Starte main.py im venv ---"
"$VENV_DIR/bin/python" main.py

exit 0