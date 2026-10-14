#!/usr/bin/env python3
"""Öffentliche Nachrichten-RSS-Feeds für NEXUS NEWS. Keine kostenpflichtige API.
Statusangaben werden heuristisch vergeben, sie sind keine Faktenprüfung.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from xml.etree import ElementTree
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT / "news.json"
FEEDS = [
    ("luftfahrt", "Flughafen gesperrt OR Flughafensperrung OR Flugausfall when:14d"),
    ("luftfahrt", "Airbus Boeing neue Flugzeuge Triebwerke Bestellungen when:14d"),
    ("fussball", "Hamburger SV HSV Transfer Gerücht Spieler when:14d"),
    ("fussball", "Bundesliga Transfer Gerücht Fußball when:14d"),
    ("fussball", "Iserlohn Roosters Spieler Gerüchte when:14d"),
    ("wirtschaft", "deutsche Wirtschaft Konjunktur Unternehmen BIP when:14d"),
    ("technik", "Innovation KI Technik NVIDIA AMD Microsoft when:14d"),
    ("gaming", "PC Nvidia AMD Intel Grafikkarten Gaming when:14d"),
    ("gaming", "Rainbow Six Siege Ubisoft Update when:14d"),
    ("politik", "Bundestag Bundesregierung Gesetze Entscheidungen Politik Deutschland when:14d"),
    ("politik", "Bundesrat Bundestag Haushalt Gesetzesreform politische Entwicklung when:14d"),
    ("politik", "site:bundesregierung.de Politik Gesetz Beschluss when:14d"),
    ("politik", "site:bundestag.de Plenum Beschlüsse Bundestag when:14d"),
    ("luftfahrt", "Flug umgeleitet Notlandung Squawk 7700 Luftfahrt Zwischenfall when:7d"),
    ("luftfahrt", "site:airbus.com/en/newsroom/press-releases when:14d"),
    ("technik", "site:blogs.nvidia.com when:14d"),
]
TRUSTED_OFFICIAL = {
    "airbus.com", "boeing.com", "blogs.nvidia.com", "nvidia.com",
    "amd.com", "hsv.de", "iserlohn-roosters.de", "bundesregierung.de",
    "munich-airport.de", "lufthansa.com", "eurocontrol.int",
    "bundestag.de", "bundesrat.de",
}
UNCERTAIN = re.compile(
    r"\b(?:gerücht(?:e)?|angeblich|mutmaßlich|unbestätigt|insider|"
    r"leak(?:s|ed)?|geleakt|soll(?:en|te)?|könnte|reportedly|rumou?rs?|"
    r"may|could|speculation)\b", re.I
)
# Kennzeichnung wichtiger Schlagwörter, KEIN amtlicher Echtzeit-Notfallalarm.
# Eine einzelne Schlagzeile kann irreführend sein und wird nicht unabhängig verifiziert.
BREAKING = re.compile(
    r"\b(?:eilmeldung|breaking(?: news)?|notlandung|"
    r"flugzeugnotfall|flughafensperrung|flughafen gesperrt|"
    r"flugverkehr eingestellt|evakuiert|squawk 7700|"
    r"rücktritt|misstrauensvotum)\b", re.I
)
UA = "NexusPersonalNews/2.0 (+public RSS feed)"


def official_source(source_url: str) -> bool:
    try:
        host = (urllib.parse.urlparse(source_url).hostname or "").lower()
        return any(host == domain or host.endswith("." + domain)
                   for domain in TRUSTED_OFFICIAL)
    except ValueError:
        return False


def parse_feed(raw: bytes, category: str, today) -> list[dict]:
    root = ElementTree.fromstring(raw)
    results = []
    for entry in root.findall("./channel/item")[:22]:
        title = unescape((entry.findtext("title") or "").strip())
        link = (entry.findtext("link") or "").strip()
        source = entry.find("source")
        publisher = (source.text or "").strip() if source is not None else ""
        publisher = publisher or "Google News"
        source_url = source.attrib.get("url", "") if source is not None else ""
        if title.lower().endswith(" - " + publisher.lower()):
            title = title[:-(len(publisher) + 3)]
        try:
            date = parsedate_to_datetime(entry.findtext("pubDate") or "").date()
        except (ValueError, TypeError, OverflowError):
            continue
        if (not title or not link.startswith("https://")
                or date < today - timedelta(days=21)
                or date > today + timedelta(days=1)):
            continue
        status = ("rumor" if UNCERTAIN.search(title) else
                  "confirmed" if official_source(source_url) else "report")
        summary = {
            "rumor": "Unbestätigte Meldung. Originalbericht lesen und weitere Quellen abgleichen.",
            "confirmed": "Offizielle Primärmeldung laut RSS-Quelle. Details in der Veröffentlichung prüfen.",
            "report": "Journalistischer Bericht. Aussagen und Aktualisierungen bitte bei der Quelle prüfen.",
        }[status]
        key = category + "|" + title.casefold().strip()
        item_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:18]
        results.append({
            "id": "rss-" + item_id, "cat": category, "status": status,
            "date": date.isoformat(), "priority": 2 if status == "rumor" else 3,
            "title": title[:240], "summary": summary, "source": publisher[:90],
            "url": link, "tags": ["RSS", "automatisch"],
            "breaking": bool(BREAKING.search(title) and (today - date).days <= 1),
        })
    return results


def download_feed(query: str) -> bytes:
    args = urllib.parse.urlencode({
        "q": query, "hl": "de", "gl": "DE", "ceid": "DE:de"
    })
    request = urllib.request.Request(
        "https://news.google.com/rss/search?" + args,
        headers={"User-Agent": UA, "Accept": "application/rss+xml,application/xml,text/xml"}
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        return response.read(2_500_000)



# Konservative Ereignis-Bündelung: Nur sehr ähnliche Schlagzeilen,
# gleiche Themenwelt und enges Zeitfenster. Im Zweifel getrennt lassen.
import unicodedata

TITLE_STOPWORDS = {
    "der","die","das","den","dem","des","ein","eine","einer","eines","einem",
    "und","oder","mit","von","vom","zur","zum","aus","auf","für","bei",
    "über","unter","nach","wegen","durch","gegen","sich","auch","noch",
    "aber","dass","haben","hat","wird","werden","ist","sind","als",
    "am","im","in","an","um","zu","es","er","sie","man","bereits",
    "erneut","jetzt","aktuell","neue","neuer","neues","neuen","neuer",
    "diese","dieser","laut","berichtet","meldet","sagt","bestätigt",
    "offiziell","aktuelle","weitere","deutsche","deutschen","deutscher",
    "deutschland","news","eilmeldung","breaking","bericht","update",
}

def headline_tokens(title: str) -> set[str]:
    norm = unicodedata.normalize("NFKD", title.casefold())
    norm = "".join(c for c in norm if not unicodedata.combining(c))
    words = re.findall(r"[a-z0-9]+", norm)
    return {w for w in words if (len(w) >= 4 or any(c.isdigit() for c in w)
            or w in {"hsv", "bvb", "spd", "afd", "bsw", "ki"})
            and w not in TITLE_STOPWORDS}

def is_same_event(a: dict, b: dict) -> bool:
    if a.get("cat") != b.get("cat"):
        return False
    try:
        days = abs((datetime.fromisoformat(a["date"][:10]) -
                    datetime.fromisoformat(b["date"][:10])).days)
        if days > 2:
            return False
    except (ValueError, KeyError):
        return False
    left, right = headline_tokens(a["title"]), headline_tokens(b["title"])
    common = left & right
    if len(common) < 3 or min(len(left), len(right)) < 4:
        return False
    # Widersprüchliche Flugnummern niemals als dasselbe Flugereignis bündeln.
    flight_pattern = re.compile(r"^[a-z]{2,3}[0-9]{2,4}$")
    flights_a = {w for w in left if flight_pattern.fullmatch(w)}
    flights_b = {w for w in right if flight_pattern.fullmatch(w)}
    if flights_a and flights_b and not flights_a.intersection(flights_b):
        return False
    jaccard = len(common) / max(1, len(left | right))
    containment = len(common) / max(1, min(len(left), len(right)))
    return jaccard >= 0.58 or (len(common) >= 4 and containment >= 0.84)

def source_entries(story: dict) -> list[dict]:
    existing = story.get("sources")
    if isinstance(existing, list) and existing:
        return [x for x in existing if isinstance(x, dict) and x.get("url")]
    return [{
        "source": story.get("source", "Quelle"),
        "title": story["title"],
        "url": story["url"],
        "status": story.get("status", "report"),
        "date": story.get("date", ""),
        "id": story.get("id", ""),
    }]

def group_stories(stories) -> list[dict]:
    """Mehrere Berichte zu *einem* Ereignis, inklusive Quellenlinks."""
    candidates = sorted(stories,
        key=lambda s: (s.get("date", ""), s.get("status") == "confirmed"),
        reverse=True)
    clusters = []
    for story in candidates:
        found = None
        for group in clusters:
            if any(is_same_event(story, existing) for existing in group):
                found = group
                break
        if found is None:
            clusters.append([story])
        else:
            found.append(story)
    result = []
    ranking = {"confirmed": 0, "report": 1, "rumor": 2}
    for group in clusters:
        # Bei mehreren Perspektiven bevorzugt eine offizielle Quelle.
        main_story = sorted(group, key=lambda s: (
            ranking.get(s.get("status"), 3), -int(s.get("date", "0000-00-00")[:10].replace("-", "") or "0")
        ))[0]
        merged = dict(main_story)
        sources = []
        urls = set()
        for item in sorted(group, key=lambda s: (
            ranking.get(s.get("status"), 3), s.get("source", "")
        )):
            for source in source_entries(item):
                url = source.get("url", "")
                if url and url not in urls:
                    sources.append(source)
                    urls.add(url)
        merged["sources"] = sources[:18]
        merged["source_count"] = len(sources)
        merged["breaking"] = any(item.get("breaking") for item in group)
        merged["date"] = max(item.get("date", "") for item in group)
        merged["priority"] = min(item.get("priority", 5) for item in group)
        result.append(merged)
    return result


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    original = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    fetched = []
    successful = 0
    for category, query in FEEDS:
        try:
            fetched.extend(parse_feed(download_feed(query), category, today))
            successful += 1
        except (urllib.error.URLError, OSError, ElementTree.ParseError, ValueError) as e:
            print("RSS-Quelle vorübergehend nicht erreichbar:", category, str(e))
        time.sleep(0.25)
    print("Erfolgreiche RSS-Feeds:", successful, "Meldungen:", len(fetched))
    if not successful or not fetched:
        print("Ohne neue Daten: bisherigen Stand beibehalten.")
        return

    curated = []
    for story in original.get("stories", []):
        if str(story.get("id", "")).startswith("rss-"):
            continue
        try:
            day = datetime.strptime(story["date"][:10], "%Y-%m-%d").date()
            if today - timedelta(days=21) <= day <= today:
                curated.append(story)
        except (KeyError, ValueError, TypeError):
            continue

    unique = {story["id"]: story for story in curated}
    for story in fetched:
        unique[story["id"]] = story
    stories = sorted(group_stories(unique.values()), key=lambda x: x["date"], reverse=True)[:150]
    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": "Automatischer RSS-Abruf",
        "stories": stories
    }
    DATA_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Aktualisierte Nachrichten:", len(stories))


if __name__ == "__main__":
    main()
