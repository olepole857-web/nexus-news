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
    # Luftfahrt: Sicherheitslage, Airport-Betrieb und Hersteller
    ("luftfahrt", "Flughafen gesperrt OR Flughafenstörung OR Flugausfall when:4d"),
    ("luftfahrt", "Luftraum gesperrt NOTAM Umleitung Annullierungen when:4d"),
    ("luftfahrt", "Flughafen Riad Saudi Arabien Flugverkehr Reise Lage when:7d"),
    ("luftfahrt", "Airbus Boeing neue Flugzeuge Triebwerke Bestellungen when:7d"),
    ("luftfahrt", "Lufthansa Eurowings Ryanair Fluggesellschaft Streik Flugplan when:4d"),
    ("luftfahrt", "Flug umgeleitet Notlandung Luftfahrt Zwischenfall when:4d"),
    ("luftfahrt", "Flughafen Düsseldorf Köln Dortmund Frankfurt München aktuell when:3d"),
    ("luftfahrt", "site:airbus.com/en/newsroom/press-releases when:7d"),
    ("luftfahrt", "site:boeing.com/principles/vision.page aviation when:7d"),
    # Querbezüge: Regierungsreisen, Politiker an Flughäfen, Konflikte
    ("politik", "Ministerin Minister Regierung Flughafen festgesessen Reise Flug gestrandet when:7d"),
    ("politik", "Katherina Reiche Riad Flughafen Saudi Arabien when:7d"),
    ("politik", "Deutschland Regierung Reise Flughafen Sicherheitslage Ausland when:4d"),
    ("politik", "Bundesregierung Bundestag aktuelle Eilmeldung Entscheidung when:3d"),
    ("politik", "Bundestag Bundesregierung Gesetze Entscheidungen Politik Deutschland when:7d"),
    ("politik", "Bundesrat Bundestag Haushalt Gesetzesreform politische Entwicklung when:7d"),
    ("politik", "deutsche Ministerin Minister Regierung Koalition Streit Beschluss when:4d"),
    ("politik", "site:bundesregierung.de Pressemitteilung Beschluss when:7d"),
    ("politik", "site:bundestag.de aktuelle Meldungen when:7d"),
    # Fußball / Sport
    ("fussball", "Hamburger SV HSV Transfer Gerücht Spieler when:7d"),
    ("fussball", "Hamburger SV Trainer Verletzung Aufstellung Fußball Nachrichten when:4d"),
    ("fussball", "Bundesliga Transfer Gerücht Fußball when:7d"),
    ("fussball", "Iserlohn Roosters Spieler Gerüchte DEL when:7d"),
    # Wirtschaft und Politik/Wirtschaft-Schnittstelle
    ("wirtschaft", "Deutschland Wirtschaft Konjunktur Unternehmen Arbeitsmarkt BIP when:4d"),
    ("wirtschaft", "deutsche Wirtschaft Inflation Energiepreise Zinsen Unternehmen when:4d"),
    ("wirtschaft", "Wirtschaftsministerin Reiche Konferenz Politik Wirtschaft when:7d"),
    ("wirtschaft", "DAX Börse Wirtschaft Börsenentwicklung Deutschland when:3d"),
    ("wirtschaft", "Industrie Automobilhersteller Werke Stellenabbau Deutschland when:4d"),
    # Technik, KI, PC und Games
    ("technik", "Innovation KI Technik NVIDIA AMD Microsoft when:4d"),
    ("technik", "Apple Google OpenAI Anthropic künstliche Intelligenz Produkt when:4d"),
    ("technik", "Neuerungen Technik Smartphone Software Chip Forschung when:4d"),
    ("technik", "site:blogs.nvidia.com when:7d"),
    ("gaming", "PC Nvidia AMD Intel Grafikkarten Gaming when:4d"),
    ("gaming", "Rainbow Six Siege Ubisoft Update when:7d"),
    ("gaming", "Steam Playstation Xbox neue Spiele Updates when:4d"),
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
    for entry in root.findall("./channel/item")[:30]:
        title = unescape((entry.findtext("title") or "").strip())
        link = (entry.findtext("link") or "").strip()
        source = entry.find("source")
        publisher = (source.text or "").strip() if source is not None else ""
        publisher = publisher or "Google News"
        source_url = source.attrib.get("url", "") if source is not None else ""
        if title.lower().endswith(" - " + publisher.lower()):
            title = title[:-(len(publisher) + 3)]
        try:
            published = parsedate_to_datetime(entry.findtext("pubDate") or "")
            date = published.date()
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
            "date": date.isoformat(), "published_at": published.isoformat(timespec="minutes"),
            "priority": 2 if status == "rumor" else 3,
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


# Jede Meldung kann in mehreren Themenwelten auftauchen,
# ohne auf der Übersichtsseite doppelt gezählt zu werden.
TOPIC_TERMS = {
    "luftfahrt": re.compile(r"\b(?:flughaf\w*|airport\w*|flugzeug\w*|flugverkehr\w*|fluggesellschaf\w*|flieger\w*|flug\w*|luftraum\w*|luftfahr\w*|airbus|boeing|lufthansa|eurowings|ryanair|airport|airline\w*|pilot\w*|notlandung|startbahn\w*)\b", re.I),
    "politik": re.compile(r"\b(?:minister\w*|bundesregierung|bundestag|bundesrat|kanzler\w*|partei\w*|koalition\w*|präsident\w*|präsidentschaft|cdu|csu|spd|afd|bsw|grüne\w*|bundespolit\w*|regierungs\w*|eu-kommission|staatsoberhaupt\w*)\b", re.I),
    "wirtschaft": re.compile(r"\b(?:wirtschaft\w*|dax|inflation\w*|unternehmen\w*|konjunktur\w*|industrie\w*|arbeitsmarkt\w*|arbeitsplätze|energiepreis\w*|energieversorgung|börsen\w*|aktien\w*|milliarden\w*|rezession\w*|zoll\w*|export\w*|investition\w*|zins\w*)\b", re.I),
    "technik": re.compile(r"\b(?:ki|künstliche intelligenz|artificial intelligence|openai|anthropic|chatgpt|chip\w*|innovation\w*|technologie\w*|software\w*|nvidia|microsoft|apple|google|robot\w*)\b", re.I),
    "gaming": re.compile(r"\b(?:gaming|videospiel\w*|playstation|xbox|steam|ubisoft|rainbow six|grafikkart\w*|geforce|radeon|nintendo|spielekonsole\w*)\b", re.I),
    "fussball": re.compile(r"\b(?:fußball\w*|fussball\w*|bundesliga|hamburger sv|hsv|transfer\w*|torjäger\w*|trainerwechsel|iserlohn roosters|eishockey|del)\b", re.I),
}

def story_categories(story: dict) -> list[str]:
    primary = story.get("cat", "politik")
    result = [primary]
    for previous in story.get("categories", []):
        if previous in TOPIC_TERMS and previous not in result:
            result.append(previous)
    for theme, pattern in TOPIC_TERMS.items():
        if theme not in result and pattern.search(story.get("title", "")):
            result.append(theme)
    return result

def is_same_event(a: dict, b: dict) -> bool:
    cross_topic = a.get("cat") != b.get("cat")
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
    if cross_topic:
        return len(common) >= 4 and (jaccard >= 0.72 or containment >= 0.92)
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
        merged["categories"] = list(dict.fromkeys(
            theme for item in group for theme in story_categories(item)))
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
    stories = sorted(group_stories(unique.values()), key=lambda x: x.get("published_at", x["date"]), reverse=True)[:350]
    output = {
        "generated_at": now.isoformat(timespec="seconds"),
        "mode": "Erweiterter RSS-Abruf · stündlich",
        "feed_count": successful,
        "stories": stories
    }
    DATA_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Aktualisierte Nachrichten:", len(stories))


if __name__ == "__main__":
    main()
