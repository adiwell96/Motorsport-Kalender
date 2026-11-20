#!/usr/bin/env python3
"""Baut die abonnierbaren Motorsport-Kalender (ICS) aus drei Quellen:

1. Motorsport-Total-Gesamtfeed  -> Rennwochenenden (ganztägig) für die meisten Serien
2. Jolpica-F1-API               -> exakte F1-Sessions (Trainings, Quali, Sprint, Rennen)
3. data/sessions/*.json         -> exakte Zeitpläne aller anderen Serien inkl. TV
                                   (werden wöchentlich per Recherche gepflegt)

Zusätzlich: data/tv_overrides.json für TV-Angaben einzelner Wochenenden.
Nur Python-Standardbibliothek. Aufruf:  python generator/build.py [--offline]
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
OUT = ROOT / "public"
BERLIN = ZoneInfo("Europe/Berlin")
UTC = timezone.utc

MT_URL = "https://www.motorsport-total.com/motorsport-termine/termine.ics"
F1_URL = "https://api.jolpi.ca/ergast/f1/{year}.json"
KEEP_PAST_DAYS = 120
UA = "Mozilla/5.0 (motorsport-kalender; +github actions)"

WARNINGS: list[str] = []


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print("WARNUNG:", msg, file=sys.stderr)


# --------------------------------------------------------------------------- Laden

def fetch(url: str, cache_name: str, offline: bool) -> str | None:
    """Lädt eine URL; bei Fehler wird die letzte gute Kopie aus data/cache genutzt."""
    cache_file = CACHE / cache_name
    if not offline:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8", errors="replace")
            if len(text) > 50:
                CACHE.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(text, encoding="utf-8")
                return text
        except Exception as e:  # noqa: BLE001
            warn(f"{url} nicht erreichbar ({e}) – nutze Cache")
    if cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
    warn(f"Kein Cache für {cache_name}")
    return None


# --------------------------------------------------------------------------- ICS lesen

def unfold(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def unescape(v: str) -> str:
    return (v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",")
             .replace("\\;", ";").replace("\\\\", "\\"))


def parse_ics(text: str) -> list[dict]:
    events, cur = [], None
    for line in unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            parts = head.split(";")
            params = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
            cur[parts[0].upper()] = (value, params)
    return events


def ics_time(value: str, params: dict) -> date | datetime:
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").date()
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
    tz = ZoneInfo(params["TZID"].strip('"')) if "TZID" in params else BERLIN
    return datetime.strptime(value[:15], "%Y%m%dT%H%M%S").replace(tzinfo=tz)


# --------------------------------------------------------------------------- Modell

class Event:
    def __init__(self, series: str, title: str, start, end, *, location: str = "",
                 tv: str = "", note: str = "", url: str = "", uid_key: str = "",
                 kind: str = "session"):
        self.series, self.title, self.start, self.end = series, title, start, end
        self.location, self.tv, self.note, self.url = location, tv, note, url
        self.kind = kind  # "weekend" (ganztägig) oder "session"
        key = uid_key or f"{series}|{title}|{start}"
        self.uid = hashlib.sha1(key.encode()).hexdigest()[:20] + "@motorsport-kalender"

    @property
    def all_day(self) -> bool:
        return isinstance(self.start, date) and not isinstance(self.start, datetime)

    def day(self) -> date:
        return self.start if self.all_day else self.start.astimezone(BERLIN).date()

    def last_day(self) -> date:
        if self.all_day:
            return self.end - timedelta(days=1)
        return self.end.astimezone(BERLIN).date()


# --------------------------------------------------------------------------- Quellen

def load_series() -> dict:
    data = json.loads((DATA / "series.json").read_text(encoding="utf-8"))
    return {s["id"]: s for s in data["series"]}


def from_motorsport_total(series: dict, offline: bool) -> list[Event]:
    text = fetch(MT_URL, "motorsport-total.ics", offline)
    if not text:
        return []
    by_name = {n.lower(): sid for sid, s in series.items() for n in s.get("mt", [])}
    out = []
    for ev in parse_ics(text):
        summary = unescape(ev.get("SUMMARY", ("", {}))[0]).strip()
        if ":" not in summary or "DTSTART" not in ev:
            continue
        mt_series, rest = (x.strip() for x in summary.split(":", 1))
        sid = by_name.get(mt_series.lower())
        if not sid:
            continue
        start = ics_time(*ev["DTSTART"])
        end = ics_time(*ev["DTEND"]) if "DTEND" in ev else start
        # Wochenenden immer ganztägig darstellen (Berliner Datum)
        if isinstance(start, datetime):
            s_local, e_local = start.astimezone(BERLIN), end.astimezone(BERLIN)
            start = s_local.date()
            end = e_local.date() + (timedelta(days=0) if e_local.time() == datetime.min.time()
                                    and e_local.date() > start else timedelta(days=1))
        if end <= start:
            end = start + timedelta(days=1)
        loc = unescape(ev.get("LOCATION", ("", {}))[0])
        title = rest
        if sid == "wec" and mt_series.lower() == "24h le mans":
            title = f"24h Le Mans – {rest}" if "le mans" not in rest.lower() else rest
        out.append(Event(sid, title, start, end, location=loc, kind="weekend",
                         url="https://www.motorsport-total.com",
                         uid_key=f"mt|{sid}|{start.isoformat()}|{rest}"))
    return out


F1_SESSIONS = [  # (API-Feld, Name, Dauer in Minuten)
    ("FirstPractice", "1. Freies Training", 60),
    ("SecondPractice", "2. Freies Training", 60),
    ("ThirdPractice", "3. Freies Training", 60),
    ("SprintQualifying", "Sprint-Qualifying", 45),
    ("SprintShootout", "Sprint-Qualifying", 45),
    ("Sprint", "Sprint", 60),
    ("Qualifying", "Qualifying", 60),
]


def from_f1_api(offline: bool) -> list[Event]:
    out = []
    this_year = datetime.now(UTC).year
    for year in (this_year, this_year + 1):
        text = fetch(F1_URL.format(year=year), f"f1-{year}.json", offline)
        if not text:
            continue
        try:
            races = json.loads(text)["MRData"]["RaceTable"]["Races"]
        except (KeyError, ValueError):
            warn(f"F1-API {year}: unerwartetes Format")
            continue
        for race in races:
            gp = race["raceName"].replace("Grand Prix", "GP")
            circuit = race.get("Circuit", {})
            loc = ", ".join(x for x in (circuit.get("circuitName", ""),
                                         circuit.get("Location", {}).get("locality", ""),
                                         circuit.get("Location", {}).get("country", "")) if x)
            items = [(f, n, d) for f, n, d in F1_SESSIONS if f in race]
            items.append(("__race__", "Rennen", 120))
            for field, name, minutes in items:
                block = race if field == "__race__" else race[field]
                if "time" not in block:
                    continue  # Zeit noch nicht veröffentlicht
                start = datetime.fromisoformat(f"{block['date']}T{block['time'].replace('Z', '+00:00')}")
                out.append(Event("f1", f"{gp} – {name}", start, start + timedelta(minutes=minutes),
                                 location=loc, url=race.get("url", ""),
                                 uid_key=f"f1|{year}|{race['round']}|{name}"))
    return out


DEFAULT_MIN = [("rennen", 120), ("race", 120), ("qualifying", 60), ("training", 60),
               ("practice", 60), ("warm", 30), ("wp", 180), ("etappe", 480), ("stage", 480)]


def default_minutes(name: str) -> int:
    n = name.lower()
    for key, mins in DEFAULT_MIN:
        if key in n:
            return mins
    return 60


def parse_local(value: str, tz: ZoneInfo) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=tz)


def from_session_files(series: dict) -> list[Event]:
    out = []
    for path in sorted(p for p in (DATA / "sessions").glob("*.json") if not p.name.startswith("_")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            sid = doc["series"]
            if sid not in series:
                warn(f"{path.name}: unbekannte Serie '{sid}'")
                continue
            for w in doc.get("weekends", []):  # Saison-Übersicht (ganztägig)
                d_from = date.fromisoformat(w["from"])
                d_to = date.fromisoformat(w.get("to", w["from"]))
                out.append(Event(sid, w["event"], d_from, d_to + timedelta(days=1),
                                 location=w.get("location", ""), tv=w.get("tv", ""),
                                 note=w.get("note", ""), url=doc.get("source", ""),
                                 kind="weekend",
                                 uid_key=f"wk|{sid}|{w['event']}|{d_from}"))
            if "sessions" not in doc:
                continue
            tz = ZoneInfo(doc.get("timezone", "Europe/Berlin"))
            event_name = doc["event"]
            for s in doc["sessions"]:
                start = parse_local(s["start"], tz)
                end = parse_local(s["end"], tz) if s.get("end") else \
                    start + timedelta(minutes=default_minutes(s["name"]))
                if end <= start:
                    raise ValueError(f"Ende vor Start bei {s['name']}")
                out.append(Event(sid, f"{event_name} – {s['name']}", start, end,
                                 location=doc.get("location", ""),
                                 tv=s.get("tv") or doc.get("tv", ""),
                                 note=s.get("note", ""), url=doc.get("source", ""),
                                 uid_key=f"file|{sid}|{event_name}|{s['name']}|{start.date()}"))
        except Exception as e:  # noqa: BLE001
            warn(f"{path.name} fehlerhaft: {e}")
    return out


def load_tv_overrides() -> list[dict]:
    f = DATA / "tv_overrides.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("overrides", [])
    except ValueError as e:
        warn(f"tv_overrides.json fehlerhaft: {e}")
        return []


# --------------------------------------------------------------------------- Zusammenführen

def apply_tv(events: list[Event], series: dict, overrides: list[dict]) -> None:
    for ev in events:
        if not ev.tv:
            for o in overrides:
                if o.get("series") != ev.series:
                    continue
                d_from = date.fromisoformat(o["from"])
                d_to = date.fromisoformat(o.get("to", o["from"]))
                if ev.day() <= d_to and ev.last_day() >= d_from:
                    if not o.get("session") or o["session"].lower() in ev.title.lower():
                        ev.tv = o["tv"]
                        break
        if not ev.tv:
            ev.tv = series[ev.series]["tv"]


def dedupe(events: list[Event]) -> list[Event]:
    seen, out = set(), []
    for ev in events:
        if ev.uid not in seen:
            seen.add(ev.uid)
            out.append(ev)
    return out


# --------------------------------------------------------------------------- ICS schreiben

def esc(v: str) -> str:
    return (v.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\n", "\\n"))


def fold(line: str) -> str:
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, cur = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        limit = 75 if not parts else 74
        if len(cur) + len(b) > limit:
            parts.append(cur.decode("utf-8"))
            cur = b""
        cur += b
    parts.append(cur.decode("utf-8"))
    return "\r\n ".join(parts)


def fmt(dt) -> str:
    if isinstance(dt, datetime):
        return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%d")


def render(cal_name: str, events: list[Event], series: dict, stamp: str) -> str:
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//motorsport-kalender//DE",
         "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{esc(cal_name)}",
         "X-WR-TIMEZONE:Europe/Berlin", "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
         "X-PUBLISHED-TTL:PT6H"]
    for ev in sorted(events, key=lambda e: (fmt(e.start) if not e.all_day else fmt(e.start) + "T000000Z")):
        s = series[ev.series]
        prefix = "🏁" if ev.kind == "weekend" else "🏎️"
        summary = f"{prefix} {s['kurz']}: {ev.title}"
        desc = [f"📺 Deutschland: {ev.tv}"]
        if ev.kind == "session":
            local = ev.start.astimezone(BERLIN)
            wd = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][local.weekday()]
            desc.append(f"🕒 {wd} {local.strftime('%d.%m.%Y, %H:%M')} Uhr deutscher Zeit")
        else:
            desc.append("Rennwochenende – genaue Session-Zeiten folgen als eigene Termine, "
                        "sobald veröffentlicht.")
        if ev.note:
            desc.append(ev.note)
        if ev.url:
            desc.append(f"Quelle: {ev.url}")
        L += ["BEGIN:VEVENT", f"UID:{ev.uid}", f"DTSTAMP:{stamp}"]
        if ev.all_day:
            L += [f"DTSTART;VALUE=DATE:{fmt(ev.start)}", f"DTEND;VALUE=DATE:{fmt(ev.end)}",
                  "TRANSP:TRANSPARENT"]
        else:
            L += [f"DTSTART:{fmt(ev.start)}", f"DTEND:{fmt(ev.end)}", "TRANSP:TRANSPARENT"]
        L += [f"SUMMARY:{esc(summary)}", f"DESCRIPTION:{esc(chr(10).join(desc))}",
              f"CATEGORIES:{esc(s['name'])}"]
        if ev.location:
            L.append(f"LOCATION:{esc(ev.location)}")
        if ev.url:
            L.append(f"URL:{ev.url}")
        L.append("END:VEVENT")
    L.append("END:VCALENDAR")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


def render_index(series: dict, counts: dict, base_note: str) -> str:
    rows = "\n".join(
        f'<li><a href="{sid}.ics">{s["name"]}</a> <small>({counts.get(sid, 0)} Termine)</small></li>'
        for sid, s in series.items())
    return f"""<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motorsport-Kalender</title>
<style>body{{font-family:-apple-system,system-ui,sans-serif;max-width:640px;margin:2rem auto;padding:0 1rem;line-height:1.5}}
a.btn{{display:block;background:#c1121f;color:#fff;text-align:center;padding:1rem;border-radius:12px;text-decoration:none;font-weight:600;font-size:1.1rem}}
small{{color:#666}}</style></head><body>
<h1>🏁 Motorsport-Kalender</h1>
<p>Alle Serien in einem Kalender, Zeiten automatisch in deiner Zeitzone, mit deutscher TV-Übertragung.</p>
<p><a class="btn" id="all" href="motorsport.ics">Gesamtkalender abonnieren</a></p>
<h2>Einzelne Serien</h2><ul>{rows}</ul>
<p><small>{base_note}</small></p>
<script>for(const a of document.querySelectorAll('a[href$=".ics"]')){{const u=new URL(a.getAttribute('href'),location.href);a.href='webcal://'+u.host+u.pathname;}}</script>
</body></html>"""


# --------------------------------------------------------------------------- Main

def main() -> int:
    offline = "--offline" in sys.argv
    series = load_series()
    events = []
    events += from_motorsport_total(series, offline)
    events += from_f1_api(offline)
    events += from_session_files(series)
    events = dedupe(events)
    apply_tv(events, series, load_tv_overrides())

    cutoff = datetime.now(BERLIN).date() - timedelta(days=KEEP_PAST_DAYS)
    events = [e for e in events if e.last_day() >= cutoff]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(exist_ok=True)
    (OUT / "motorsport.ics").write_text(render("Motorsport", events, series, stamp), encoding="utf-8")
    counts = {}
    for sid, s in series.items():
        sub = [e for e in events if e.series == sid]
        counts[sid] = len(sub)
        (OUT / f"{sid}.ics").write_text(render(f"Motorsport – {s['name']}", sub, series, stamp),
                                        encoding="utf-8")
    note = f"Stand: {datetime.now(BERLIN).strftime('%d.%m.%Y %H:%M')} Uhr · {len(events)} Termine"
    (OUT / "index.html").write_text(render_index(series, counts, note), encoding="utf-8")
    (OUT / "status.json").write_text(json.dumps(
        {"stand": stamp, "termine": len(events), "pro_serie": counts, "warnungen": WARNINGS},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(events)} Termine geschrieben. Pro Serie: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
