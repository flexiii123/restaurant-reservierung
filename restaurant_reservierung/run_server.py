from waitress import serve
from app import app

if __name__ == '__main__':
    host = '127.0.0.1'
    port = 5001
    print(f"INFO: Starte Restaurant-Reservierungsserver mit Waitress...")
    print(f"INFO: Programm läuft auf http://{host}:{port}")
    print(f"INFO: Programmgenerierung abgeschlossen")
    serve(app, host=host, port=port, threads=4)