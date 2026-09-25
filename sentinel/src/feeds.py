"""Feed fetchers. Every live fetch writes cache/<name>.json; failures (or --offline) fall back to cache.
Each fetcher returns normalized items:
{id, feed, type, title, country, lat, lon, issued_severity{scale,value}, published, url, text, retrieved, lang, extra{}}"""
import datetime as dt, hashlib, html, json, os, pathlib, re, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
import feedparser, httpx

CACHE = pathlib.Path("cache"); CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "sentinel-hackathon/0.2 (Stevens Business+AI hackathon; research prototype)"}
TIMEOUT = 10


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def iso(t):
    """struct_time / datetime / epoch-ms / str -> ISO Z (best effort)."""
    try:
        if t is None or t == "":
            return None
        if isinstance(t, time.struct_time):
            d = dt.datetime(*t[:6], tzinfo=dt.timezone.utc)
        elif isinstance(t, (int, float)):
            d = dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc)
        elif isinstance(t, dt.datetime):
            d = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        else:
            s = str(t).strip().replace("Z", "+00:00")
            d = dt.datetime.fromisoformat(s)
            d = d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
        return d.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except Exception:
        return None


def parse_iso(s):
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def clean(s):
    s = re.sub(r"<br\s*/?>", " ", s or "", flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def _get(url, timeout=TIMEOUT, params=None):
    with httpx.Client(headers=UA, timeout=timeout, follow_redirects=True) as c:
        r = c.get(url, params=params); r.raise_for_status(); return r


def _cache_write(name, items):
    (CACHE / f"{name}.json").write_text(json.dumps({"retrieved": now_iso(), "items": items}, ensure_ascii=False))


def _cache_read(name):
    p = CACHE / f"{name}.json"
    if not p.exists():
        return [], None
    d = json.loads(p.read_text()); return d["items"], d.get("retrieved")


def norm(feed, id_, type_, title, url, published, text, scale=None, value=None, lat=None, lon=None,
         country="", lang="en", extra=None):
    return {"id": f"{feed}:{id_}", "feed": feed, "type": type_, "title": clean(title), "country": country or "",
            "lat": lat, "lon": lon, "issued_severity": {"scale": scale, "value": value},
            "published": published, "url": url, "text": clean(text), "retrieved": now_iso(), "lang": lang,
            "extra": extra or {}}


# ---------------------------------------------------------------- parsers
def p_gdacs():
    d = feedparser.parse(_get("https://www.gdacs.org/xml/rss.xml").text); out = []
    for e in d.entries:
        pop = e.get("gdacs_population") or {}
        sev = e.get("gdacs_severity") or {}
        out.append(norm("gdacs", e.get("gdacs_eventtype", "") + str(e.get("gdacs_eventid", e.get("id"))),
                        e.get("gdacs_eventtype", "?"), e.title, e.link, iso(e.get("published_parsed")),
                        e.title + ". " + e.get("summary", ""), "GDACS", e.get("gdacs_alertlevel", ""),
                        float(e.get("geo_lat") or 0), float(e.get("geo_long") or 0), e.get("gdacs_country", ""),
                        extra={"eventname": e.get("gdacs_eventname", ""), "iscurrent": e.get("gdacs_iscurrent"),
                               "population": pop.get("value") if isinstance(pop, dict) else None,
                               "severity_text": sev.get("value") if isinstance(sev, dict) else None,
                               "fromdate": e.get("gdacs_fromdate"), "todate": e.get("gdacs_todate"),
                               "modified": iso(e.get("gdacs_datemodified"))}))
    return out


def _nhc_track(txt):
    pts = []
    for m in re.finditer(r"(?:FORECAST|OUTLOOK) VALID (\d\d/\d{4}Z)\s+(\d+\.\d)([NS])\s+(\d+\.\d)([EW])", txt):
        lat = float(m.group(2)) * (1 if m.group(3) == "N" else -1)
        lon = float(m.group(4)) * (-1 if m.group(5) == "W" else 1)
        pts.append({"valid": m.group(1), "lat": lat, "lon": lon})
    return pts


def p_nhc(basin):
    url = f"https://www.nhc.noaa.gov/index-{basin}.xml"
    d = feedparser.parse(_get(url).text); storms = {}; out = []
    for e in d.entries:
        t = e.title
        if e.get("nhc_atcf"):
            storms.setdefault(e.nhc_atcf, {})["sum"] = e
        else:
            m = re.search(r"(Hurricane|Tropical Storm|Tropical Depression|Post-Tropical Cyclone|Potential Tropical Cyclone|Remnants of) (\w+) (Public Advisory|Forecast Advisory)", t)
            if m and "Update" not in t:
                for k, s in storms.items():
                    if s["sum"].nhc_name.lower() == m.group(2).lower():
                        s.setdefault("pub" if "Public" in m.group(3) else "fcst", e)
    for atcf, s in storms.items():
        e = s["sum"]; lat, lon = [float(x) for x in e.nhc_center.split(",")]
        pub = s.get("pub"); fc = s.get("fcst")
        text = clean(e.get("summary", "")) + " " + (clean(pub.get("summary", "")) if pub else "")
        wind = int(re.sub(r"\D", "", e.get("nhc_wind", "0")) or 0)
        name = f"{e.nhc_type} {e.nhc_name}"
        out.append(norm(f"nhc_{basin}", atcf, "TC", name, (pub.link if pub else e.link),
                        iso(pub.get("published_parsed") if pub else e.get("published_parsed")) or now_iso(), text,
                        "NHC_SSHWS", sshws(e.nhc_type, wind), lat, lon, "",
                        extra={"storm": e.nhc_name, "wind_mph": wind, "pressure": e.get("nhc_pressure"),
                               "movement": e.get("nhc_movement"), "headline": clean(e.get("nhc_headline")),
                               "nhc_type": e.nhc_type,
                               "track": _nhc_track(clean(fc.get("summary", "")) if fc else "")}))
    return out


def sshws(kind, mph):
    if "Hurricane" in kind or mph >= 74:
        cat = 5 if mph >= 157 else 4 if mph >= 130 else 3 if mph >= 111 else 2 if mph >= 96 else 1
        return f"Cat {cat} ({mph} mph)"
    return f"{kind} ({mph} mph)"


def p_usgs():
    seen = {}; out = []
    for u in ("significant_week", "4.5_day"):
        g = _get(f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{u}.geojson").json()
        for f in g["features"]:
            seen[f["id"]] = f
    for fid, f in seen.items():
        p = f["properties"]; lon, lat, depth = f["geometry"]["coordinates"][:3]
        txt = (f"{p['title']} | mag={p['mag']} {p.get('magType') or ''} | depth_km={depth} | PAGER alert={p.get('alert') or 'none'} | "
               f"tsunami={p.get('tsunami')} | felt reports={p.get('felt') or 0} | significance={p.get('sig')} | place={p.get('place')}")
        out.append(norm("usgs", fid, "EQ", p["title"], p["url"], iso(p["time"]), txt, "USGS_PAGER",
                        f"M{p['mag']} / PAGER {p.get('alert') or 'n/a'}", lat, lon, (p.get("place") or "").split(", ")[-1],
                        extra={"mag": p["mag"], "alert": p.get("alert"), "sig": p.get("sig"), "felt": p.get("felt"),
                               "tsunami": p.get("tsunami"), "depth": depth, "place": p.get("place")}))
    return out


def p_who():
    r = _get("https://www.who.int/api/news/diseaseoutbreaknews",
             params={"$orderby": "PublicationDate desc", "$top": "15"}).json()
    out = []
    for x in r.get("value", []):
        title = x.get("OverrideTitle") or x.get("Title") or ""
        disease, _, where = title.partition(" - ")
        if not where:
            disease, _, where = title.partition(", ")
        url = "https://www.who.int/emergencies/disease-outbreak-news/item" + (x.get("ItemDefaultUrl") or "/" + x.get("UrlName", ""))
        text = " ".join(clean(x.get(k)) for k in ("Summary", "Overview", "Epidemiology", "Assessment") if x.get(k))
        out.append(norm("who_don", x.get("UrlName") or x.get("DonId") or x.get("Id"), "OUTBREAK", title, url,
                        iso(x.get("PublicationDate")), text[:20000], "WHO_DON", x.get("UrlName"),
                        country=where.strip(), extra={"disease": disease.strip(), "don": x.get("UrlName")}))
    return out


def p_ecdc():
    d = feedparser.parse(_get("https://www.ecdc.europa.eu/en/taxonomy/term/1244/feed").text)
    return [norm("ecdc", hashlib.md5(e.link.encode()).hexdigest()[:10], "HEALTH", e.title, e.link,
                 iso(e.get("published_parsed")), e.title + ". " + e.get("summary", ""), "ECDC", None) for e in d.entries]


def p_eonet():
    j = _get("https://eonet.gsfc.nasa.gov/api/v3/events", params={"status": "open", "limit": 80}, timeout=20).json()
    cmap = {"severeStorms": "TC", "wildfires": "WF", "volcanoes": "VO", "floods": "FL", "earthquakes": "EQ", "drought": "DR"}
    out = []
    for e in j["events"]:
        g = e["geometry"][-1]; c = e["categories"][0]["id"]
        if g.get("type") != "Point":
            continue
        lon, lat = g["coordinates"][:2]
        mag = f"{g.get('magnitudeValue')} {g.get('magnitudeUnit')}" if g.get("magnitudeValue") else ""
        src = (e.get("sources") or [{}])[0].get("url") or e.get("link")
        out.append(norm("eonet", e["id"], cmap.get(c, c), e["title"], src, iso(g["date"]),
                        f"{e['title']} ({c}) observed {g['date']} {mag}".strip(), "EONET", mag, lat, lon,
                        extra={"category": c, "eonet_link": e.get("link")}))
    return out


FEEDS = {"gdacs": p_gdacs, "nhc_at": lambda: p_nhc("at"), "nhc_ep": lambda: p_nhc("ep"), "nhc_cp": lambda: p_nhc("cp"),
         "usgs": p_usgs, "who_don": p_who, "ecdc": p_ecdc, "eonet": p_eonet}


def fetch_one(name, fn, offline=False):
    if not offline:
        try:
            items = fn(); _cache_write(name, items)
            return items, {"name": name, "items": len(items), "status": "live", "retrieved": now_iso()}
        except Exception as ex:
            print(f"  [{name}] live fetch failed ({type(ex).__name__}: {str(ex)[:80]}); using cache")
    items, ret = _cache_read(name)
    return items, {"name": name, "items": len(items), "status": "cache" if ret else "error", "retrieved": ret or now_iso()}


def fetch_all(offline=False):
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {n: ex.submit(fetch_one, n, fn, offline) for n, fn in FEEDS.items()}
        res = {n: f.result() for n, f in futs.items()}
    items = [i for n in FEEDS for i in res[n][0]]
    return items, [res[n][1] for n in FEEDS]


# ---------------------------------------------------------------- corroboration searches
GN_LOCALE = {"en": ("en-US", "US", "US:en"), "es": ("es-419", "MX", "MX:es-419"), "fr": ("fr", "FR", "FR:fr"),
             "pt": ("pt-BR", "BR", "BR:pt-419"), "ja": ("ja", "JP", "JP:ja"), "zh": ("zh-TW", "TW", "TW:zh-Hant"),
             "ar": ("ar", "AE", "AE:ar"), "hi": ("hi", "IN", "IN:hi"), "id": ("id", "ID", "ID:id"),
             "tr": ("tr", "TR", "TR:tr")}


def gnews(query, lang="en", offline=False):
    """Google News RSS search -> normalized items (title is the fetched text used for quote verification)."""
    key = "gnews_" + hashlib.md5(f"{query}|{lang}".encode()).hexdigest()[:12]
    hl, gl, ceid = GN_LOCALE.get(lang, GN_LOCALE["en"])
    items, st = [], "cache"
    if not offline:
        try:
            r = _get("https://news.google.com/rss/search", params={"q": query, "hl": hl, "gl": gl, "ceid": ceid})
            d = feedparser.parse(r.text)
            for e in d.entries[:40]:
                src = e.get("source") or {}
                dom = re.sub(r"^https?://(www\.)?", "", src.get("href", "")).split("/")[0]
                items.append(norm("gnews", hashlib.md5(e.link.encode()).hexdigest()[:12], "NEWS", e.title, e.link,
                                  iso(e.get("published_parsed")), e.title, None, None, lang=lang,
                                  extra={"domain": dom, "outlet": src.get("title", ""), "query": query}))
            _cache_write(key, items); st = "live"
        except Exception as ex:
            print(f"  [gnews {lang}] {query!r} failed: {type(ex).__name__}")
    if st != "live":
        items, _ = _cache_read(key)
    return items


def gdelt(query, offline=False):
    """Optional best-effort (often rate-limited). Enabled only with SENTINEL_GDELT=1."""
    if offline or os.environ.get("SENTINEL_GDELT") != "1":
        return []
    try:
        j = _get(f"https://api.gdeltproject.org/api/v2/doc/doc?query={quote_plus(query)}&mode=artlist&format=json&maxrecords=20&timespan=3d", timeout=8).json()
        return [norm("gdelt", hashlib.md5(a["url"].encode()).hexdigest()[:12], "NEWS", a["title"], a["url"],
                     iso(a.get("seendate", "").replace("T", "").replace("Z", "")), a["title"], lang="en",
                     extra={"domain": a.get("domain", ""), "outlet": a.get("domain", "")}) for a in j.get("articles", [])]
    except Exception:
        return []


if __name__ == "__main__":
    import sys
    its, st = fetch_all(offline="--offline" in sys.argv)
    for s in st:
        print(s)
    print(len(its), "items")
