@echo off
:: Prüfen ob Venv existiert
if not exist venv (
    echo [!] Venv nicht gefunden. Bitte zuerst install.bat ausfuehren.
    pause
    exit
)

:: Aktiviere Umgebung und starte App
call venv\Scripts\activate
echo Starte VIRAL ENGINE V9...
python dein_scriptname.py
pause