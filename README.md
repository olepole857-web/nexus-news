# NEXUS NEWS 2.0

Persönliches, kostenloses und responsives News-Terminal: Luftfahrt, Hamburger SV und Fußballtransfers, Wirtschaft, KI-Technik, PC und Gaming.

## Webseite
Nach Aktivierung von GitHub Pages: https://olepole857-web.github.io/nexus-news/

## Veröffentlichung einrichten
1. Unter Repository **Settings → Pages** bei **Build and deployment → Source** die Option **GitHub Actions** auswählen.
2. Unter **Actions** den Workflow **NEXUS NEWS – RSS aktualisieren und veröffentlichen** prüfen.
3. Falls noch kein erfolgreicher Lauf vorhanden ist: den Workflow öffnen, **Run workflow** wählen und Branch **main** bestätigen.
4. Im erfolgreichen Workflow-Lauf zeigt GitHub die öffentliche Seitenadresse an.

## Automatisches Update
Der GitHub-Actions-Workflow läuft bei Änderungen, auf manuellen Befehl und planmäßig etwa alle 4 Stunden.
Er lädt frei verfügbare RSS-Suchergebnisse von Google News und stellt das Dashboard erneut bereit. Bei einem Ausfall bleiben die vorherigen Startnachrichten bestehen. GitHub kann geplante Workflows verzögern, auslassen oder nach 60 Tagen ohne Repository-Aktivität deaktivieren. Eine garantierte Echtzeit-Aktualisierung gibt es nicht.

## Nachrichtenstatus
- **Gerücht**: automatische Schlüsselwort-Erkennung, keine Bestätigung
- **Medienbericht**: Veröffentlichung einer externen Quelle
- **Bestätigt**: offizielle Primärmeldung einer gelisteten Stelle (keine unabhängige Verifikation)

Die automatische Klassifizierung ist nicht fehlerfrei. Quellenlinks gegebenenfalls über Google News öffnen und Informationen selbst prüfen. Flughafensperrungen sind stets bei Flughafen, Airline oder offiziellen NOTAM-Diensten abzugleichen.

## Kosten, Rechte, Privatsphäre
Dieses Projekt benötigt keine bezahlten API-Schlüssel. Die Veröffentlichung nutzt die kostenlosen Bedingungen von GitHub Pages und GitHub Actions für öffentliche Repositories, soweit diese verfügbar sind.
Das Repository ist **öffentlich**. Keine Zugangsdaten eintragen. Merkliste und Filter werden lokal im Browser gespeichert und nicht über Geräte synchronisiert. Es gibt keine Push-Mitteilungen.

## Themen und Quellen ändern
Neue RSS-Themen: `scripts/update_news.py`, Liste `FEEDS`. 
Design und Kategorien: `index.html`.
Kuratierten Ausgangsstand: `news.json` (wird beim Build aktualisiert, nicht ins Repo zurückgeschrieben).

Das Dashboard ist ein persönliches Informationsprojekt, kein redaktionell geprüftes Nachrichtenangebot.
