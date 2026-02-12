# main.py
# Nur zum Starten der Anwendung app.py

import sys
import os

try:
    print("Starte Hauptanwendung (app.py) via Import...")
    # Führt den synchronen Initialisierungsblock in app.py aus
    import app_demo
    
    # Startet den Asyncio-Scheduler mit der run_app Funktion
    app_demo.run_app()
    
except Exception as e:
    # Dies fängt nur Fehler ab, die *vor* oder *während* des Imports passieren
    print(f"FATALER FEHLER beim Start von app.py: {e}")