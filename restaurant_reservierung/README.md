# Tischreservierungssystem für das Restaurant "Schwarzer Adler"

Willkommen zum Tischreservierungssystem für das Restaurant "Schwarzer Adler" in Andrian! Diese Webanwendung wurde mit Python und dem Flask-Framework entwickelt, um eine einfache und effiziente Verwaltung von Tischreservierungen zu ermöglichen. Das System bietet eine klare Übersicht über die aktuelle Tischbelegung sowie Werkzeuge zur Erstellung, Bearbeitung und Verwaltung aller anstehenden und vergangenen Reservierungen.

## Kernfunktionen im Überblick

Das Herzstück der Anwendung ist die **dynamische Tischübersicht**. Hier werden alle verfügbaren Tische des Restaurants, übersichtlich gruppiert nach Bereichen wie Saal, Stube, Garten und Bar, visualisiert. Für jeden Tisch wird der aktuelle Status (ob frei oder belegt) angezeigt. Bei Auswahl eines bestimmten Datums und einer Schicht (Mittag- oder Abendservice) werden die für diesen Zeitraum existierenden Reservierungen direkt unter dem jeweiligen Tisch mit Namen, Uhrzeit und Personenzahl aufgelistet. Eine farbliche Hervorhebung signalisiert Tische, bei denen bereits Gäste eingetroffen sind.

Die **Erstellung neuer Reservierungen** erfolgt intuitiv über ein dediziertes Formular. Dieses wird erreicht, indem man auf einen freien Tisch in der Übersicht klickt. Das System schlägt basierend auf der aktuellen Belegung des gewählten Tisches, des Datums und der Schicht nur verfügbare Uhrzeiten vor. Neben den Standardinformationen wie Name, Datum, Uhrzeit und Personenzahl können auch zusätzliche Notizen zur Reservierung hinterlegt werden.

Eine umfassende **Reservierungsverwaltung** ist über einen eigenen Navigationspunkt erreichbar. Diese tabellarische Ansicht listet alle erfassten Reservierungen auf und bietet mächtige Funktionen:
*   **Filterung:** Benutzer können die Liste nach einem spezifischen Datum, allen zukünftigen Reservierungen (ab heute) oder allen noch relevanten vergangenen Reservierungen (bis zu 7 Tage zurück) filtern.
*   **Sortierung:** Die Tabelle lässt sich nach Name des Gastes, Tischnamen, Datum, Uhrzeit oder Personenanzahl auf- und absteigend sortieren, um schnell die gewünschten Informationen zu finden.
*   **Bearbeitung:** Bestehende Reservierungen können in all ihren Details (Name, Datum, Zeit, Personen, Tisch, Notizen, Schicht) modifiziert werden.
*   **Löschung:** Nicht mehr benötigte Reservierungen lassen sich unkompliziert entfernen.
*   **Verschiebung:** Sollte ein Gast an einen anderen Tisch umgesetzt werden müssen, kann eine Reservierung auf einen anderen, zum selben Zeitpunkt verfügbaren Tisch verschoben werden.
*   **Status-Updates:** Mitarbeiter können Gäste als "Angekommen" markieren, sobald sie eintreffen, und später als "Gegangen", wenn sie das Restaurant verlassen. Dies aktualisiert auch die Statusanzeige in der Tischübersicht.

Alle Reservierungsdaten werden persistent in einer lokalen **JSON-Datei** (`data/reservations.json`) gespeichert. Um die Datenmenge überschaubar zu halten und die Performance zu gewährleisten, verfügt das System über eine **automatische Bereinigungsfunktion**, die regelmäßig Reservierungen entfernt, die älter als ein konfigurierbarer Zeitraum (standardmäßig 7 Tage) sind.

## Technische Umsetzung

Das Projekt basiert auf einem schlanken Technologie-Stack, der auf bewährte Open-Source-Komponenten setzt:

*   **Backend-Logik:** Realisiert in Python 3, nutzt das Micro-Webframework Flask für das Routing von Anfragen, die Verarbeitung von Geschäftslogik und die Bereitstellung von API-Endpunkten.
*   **Frontend-Darstellung:** Standardkonformes HTML5 strukturiert die Inhalte, CSS3 sorgt für das visuelle Erscheinungsbild und die Benutzerführung. Reines (Vanilla) JavaScript wird für clientseitige Interaktionen, DOM-Manipulationen und asynchrone API-Aufrufe (mittels `fetch`) zur Kommunikation mit dem Backend eingesetzt.
*   **Dynamische Inhalte:** Die Jinja2 Template Engine, die eng mit Flask integriert ist, ermöglicht die dynamische Generierung von HTML-Seiten basierend auf den aktuellen Daten.
*   **Datenhaltung:** Als einfache und dateibasierte Lösung zur Speicherung der Reservierungsdaten dient eine JSON-Datei. Dies ermöglicht einen unkomplizierten Betrieb ohne externe Datenbankabhängigkeiten für kleinere bis mittlere Anwendungsfälle.

## Inbetriebnahme und Setup

Um die Anwendung lokal auszuführen, sind folgende Schritte notwendig:

1.  **Systemvoraussetzungen:** Stellen Sie sicher, dass Python (Version 3.8 oder neuer) und der Python Package Installer `pip` auf Ihrem System installiert sind.
2.  **Projektdateien beziehen:** Klonen Sie das Repository von seiner Quelle (z.B. GitHub) mit `git clone <URL_DES_REPOSITORIES>` und navigieren Sie in das erstellte Projektverzeichnis `cd <PROJEKTVERZEICHNIS>`.
3.  **Virtuelle Umgebung (Empfohlen):** Es wird dringend empfohlen, eine virtuelle Python-Umgebung zu verwenden, um Abhängigkeitskonflikte zu vermeiden.
    *   Unter Windows: `python -m venv .venv` gefolgt von `.venv\Scripts\activate`.
    *   Unter macOS/Linux: `python3 -m venv .venv` gefolgt von `source .venv/bin/activate`.
4.  **Installation der Abhängigkeiten:** Installieren Sie die benötigten Python-Pakete (primär Flask) mit dem Befehl `pip install -r requirements.txt`. Die Datei `requirements.txt` listet alle externen Bibliotheken auf.
5.  **Anwendungsstart:** Führen Sie die Hauptanwendungsdatei aus mit `python app.py`. Der integrierte Entwicklungsserver von Flask startet die Anwendung. Sie ist dann üblicherweise unter der Adresse `http://127.0.0.1:5001/` (oder dem in `app.py` alternativ konfigurierten Port) in Ihrem Webbrowser erreichbar.

Die grundlegende **Projektstruktur** ist modular aufgebaut, um eine klare Trennung der Verantwortlichkeiten zu gewährleisten. Der `core`-Ordner beinhaltet die Geschäftslogik (`manager.py`) und Datenmodelle (`models.py`). Statische Assets wie CSS, JavaScript und Bilder befinden sich im `static`-Verzeichnis, während HTML-Templates im `templates`-Ordner liegen. Die `app.py` dient als zentraler Einstiegspunkt und konfiguriert die Flask-Anwendung.

## Ausblick und mögliche Weiterentwicklungen

Obwohl das System in seiner aktuellen Form voll funktionsfähig ist, gibt es zahlreiche Möglichkeiten für zukünftige Erweiterungen und Verfeinerungen:

*   Implementierung eines robusteren Logging-Mechanismus anstelle von reinen `print`-Ausgaben.
*   Einführung von atomarem Schreiben für die JSON-Datenspeicherung zur Minimierung von Datenverlustrisiken.
*   Entwicklung von Unit- und Integrationstests zur Sicherstellung der Codequalität und frühzeitigen Fehlererkennung.
*   Verbesserung der Benutzererfahrung im Reservierungsformular durch dynamische Aktualisierung der verfügbaren Uhrzeiten bei Änderung von Datum oder Schicht.
*   Einführung von Benutzerrollen und einem Authentifizierungssystem für Mitarbeiter.
*   Langfristig könnte eine Umstellung von der JSON-Datei auf eine relationale Datenbank (wie SQLite oder PostgreSQL) für verbesserte Skalierbarkeit und komplexere Abfragemöglichkeiten in Betracht gezogen werden.

Dieses Projekt wurde von **Felix Prackwieser** entwickelt.