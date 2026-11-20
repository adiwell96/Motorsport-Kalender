# 🏁 Motorsport-Kalender

Abonnierbarer Kalender für 23 Rennserien, mit Zeiten in deutscher Zeit und der
deutschen TV-Übertragung in jedem Termin.

**Serien:** Formel 1, Porsche Supercup, WEC, IMSA, Formel E, Rallye-WM, W2RC, Dakar,
DTM, ADAC GT Masters, Porsche Carrera Cup Deutschland, GT World Challenge, IGTC,
weitere SRO-GT3-Serien, Asian Le Mans Series, Super GT, Supercars, 24H Series,
NLS, 24h Nürburgring, GT Open, Campionato Italiano GT, TCR World Tour.

## So funktioniert es

| Quelle | Liefert | Aktualisierung |
|---|---|---|
| Motorsport-Total-Gesamtfeed | Rennwochenenden (ganztägig) | 2× täglich automatisch |
| F1-API (Jolpica) | alle F1-Sessions minutengenau | 2× täglich automatisch |
| `data/sessions/*.json` | Session-Zeitpläne aller anderen Serien + TV | wöchentliche Recherche durch Claude |
| `data/series.json`, `data/tv_overrides.json` | deutsche TV-Sender | wöchentliche Recherche durch Claude |

GitHub Actions baut daraus `motorsport.ics` (alles) und eine Datei pro Serie und
veröffentlicht sie über GitHub Pages. Fällt eine Quelle aus, wird die letzte
gute Kopie aus `data/cache/` verwendet.

## Einmalige Einrichtung

1. Repository anlegen und diesen Ordner hochladen.
2. **Settings → Pages → Source: GitHub Actions** wählen.
3. **Actions → Kalender bauen → Run workflow** einmal starten.
4. Die Seite `https://<benutzer>.github.io/<repo>/` öffnen und auf
   **Gesamtkalender abonnieren** tippen.

### Abo in Apple Kalender (für alle Geräte)

Am besten auf dem Mac oder auf icloud.com abonnieren, damit das Abo über iCloud
auf iPhone, iPad und Mac erscheint:

- **Mac:** Kalender → Ablage → Neues Kalenderabonnement → Adresse
  `webcal://<benutzer>.github.io/<repo>/motorsport.ics` → Ort: **iCloud**,
  Aktualisieren: **Stündlich**.
- **iPhone:** Einstellungen → Apps → Kalender → Accounts → Account hinzufügen →
  Andere → Kalenderabo hinzufügen. (Dieses Abo bleibt nur auf dem iPhone.)

## Status

`status.json` auf der Pages-Seite zeigt den Stand, die Zahl der Termine pro Serie
und eventuelle Warnungen.
