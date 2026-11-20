# Wöchentliche Zeitplan- und TV-Recherche

Diese Anleitung wird jede Woche automatisch von Claude ausgeführt. Sie hält
`data/sessions/` und `data/tv_overrides.json` aktuell.

## Auftrag

1. Lies `data/series.json`, um die Serien-IDs zu kennen.
2. Ermittle für **jede Serie** alle Rennwochenenden, die in den **nächsten 21 Tagen**
   beginnen. Bei der Dakar und der W2RC gilt jede Etappe als eigene Session.
   Vergiss dabei nicht die Serien ohne Wochenend-Feed: `w2rc`, `gtopen`, `sro`
   (GT3-Serien von SRO außerhalb von GTWC/IGTC, z. B. British GT) sowie
   `24hseries`-Läufe außer Dubai.
3. Für jedes Wochenende: Hole den **offiziellen Zeitplan**. Hat die Serie in
   `data/series.json` ein Feld `quellen`, nutze diese Seiten zuerst. Sonst die Website der Serie oder
   des Veranstalters; nur wenn nicht vorhanden, eine seriöse Fachquelle).
   Wichtig sind Trainings, Qualifyings, Rennen und Etappen. Nebenserien lässt du weg.
4. Recherchiere, **wo die Sessions in Deutschland laufen** (TV-Sender, Stream,
   Free-TV oder Pay-TV). Sei konkret pro Session, falls es Unterschiede gibt
   (z. B. F1: Sky für alles, RTL nur für bestimmte Rennen).
4a. **YouTube-Abgleich:** Prüfe auf dem offiziellen YouTube-Kanal der Serie (Feld
   `youtube` in `data/series.json`), ob für die Sessions Livestreams angekündigt
   sind (Tab „Live“ bzw. geplante Streams). Trage den direkten Link zum Stream
   pro Session im Feld `stream` ein (Format `https://www.youtube.com/watch?v=…`).
   Prüfe dabei, ob der Stream in Deutschland verfügbar ist (Hinweise auf
   Geo-Sperren beachten); ist er gesperrt, keinen Link eintragen und das in
   `note` vermerken. Ist bei einer Serie das Feld `youtube` leer, ermittle den
   offiziellen Kanal (verlinkt auf der Website der Serie) und trage ihn ein.
   Prüfe bereits eingetragene Stream-Links erneut und korrigiere sie, wenn sich
   der Link geändert hat. Bei Formel 1 entfällt das (kein YouTube-Livestream).
5. Schreibe pro Wochenende eine Datei `data/sessions/JJJJ-MM-TT_<serie>_<ort>.json`
   nach dem Muster von `data/sessions/_beispiel.json`. Gib die Zeiten in der
   Ortszeit der Strecke an und setze `timezone` passend (IANA-Name), oder gib sie
   mit UTC-Offset an. Gibt es die Datei schon, aktualisiere sie, statt eine
   zweite anzulegen.
6. **Formel 1:** Keine Session-Dateien anlegen, die Zeiten kommen automatisch aus
   der F1-API. Trage stattdessen die deutsche Übertragung pro Wochenende in
   `data/tv_overrides.json` ein (z. B. `{"series":"f1","from":"2027-03-05","to":"2027-03-07","tv":"Sky Sport F1 / WOW; Rennen auch live bei RTL"}`).
7. Wenn sich die Standard-Übertragung einer Serie geändert hat, passe `tv` und
   `tv_stand` in `data/series.json` an.
8. **Saison-Übersicht** für die Serien ohne Wochenend-Feed (`w2rc`, `gtopen`,
   `24hseries`, `sro`): Pflege je Serie und Jahr eine Datei
   `data/sessions/saison_<serie>_<jahr>.json` mit allen Rennwochenenden der
   laufenden und, sobald veröffentlicht, der nächsten Saison (Muster:
   `data/sessions/_beispiel_saison.json`). Quelle: die Seiten unter `quellen`.
9. Lösche Session-Dateien, deren Wochenende mehr als 120 Tage zurückliegt.
10. Prüfe mit `python generator/build.py --offline`, dass keine Warnung zu einer
   Session-Datei ausgegeben wird. Behebe Fehler.
11. Committe mit der Nachricht `Zeitpläne aktualisiert (KW xx)` und pushe auf `main`.

## Regeln

- Nur Zeiten eintragen, die du in einer Quelle gefunden hast. Nichts schätzen.
  Ist ein Zeitplan noch nicht veröffentlicht, lass das Wochenende weg; es kommt
  nächste Woche dran.
- Kennzeichne vorläufige Zeitpläne mit `"note": "vorläufiger Zeitplan"`.
- Trage die Quelle im Feld `source` ein.
- Ändere nichts am Generator (`generator/`) und am Workflow.
