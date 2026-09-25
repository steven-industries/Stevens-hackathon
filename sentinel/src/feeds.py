"""Feed fetchers. Every fetch writes cache/<name>.json; every reader falls back to cache."""
import json, time, pathlib, datetime as dt
import httpx, feedparser

CACHE = pathlib.Path("cache"); CACHE.mkdir(exist_ok=True)
UA = {"User-Agent": "sentinel-hackathon/0.1 (stevens hackathon; contact: team)"}
NOW = lambda: dt.datetime.now(dt.timezone.utc).isoformat()

FEEDS = {
    "gdacs":    "https://www.gdacs.org/xml/rss.xml",
    "nhc_atl":  "https://www.nhc.noaa.gov/index-at.xml",
    "nhc_epac": "https://www.nhc.noaa.gov/index-ep.xml",
    "usgs":     "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson",
    "reliefweb": ("https://api.reliefweb.int/v1/disasters?appname=sentinel&limit=30&sort[]=date:desc"
                  "&fields[include][]=name&fields[include][]=status&fields[include][]=primary_type.name"
                  "&fields[include][]=country.name&fields[include][]=url&fields[include][]=date.created"),
}

def _get(url, timeout=15):
    with httpx.Client(headers=UA, timeout=timeout, follow_redirects=True) as c:
        r = c.get(url); r.raise_for_status(); return r.text

def _cache_write(name, items):
    (CACHE / f"{name}.json").write_text(json.dumps({"retrieved": NOW(), "items": items}, indent=1))

def _cache_read(name):
    p = CACHE / f"{name}.json"
    return json.loads(p.read_text())["items"] if p.exists() else []

def norm(feed, id_, type_, title, country, url, published, text, scale=None, value=None, lat=None, lon=None):
    return {"id": f"{feed}:{id_}", "feed": feed, "type": type_, "title": title, "country": country,
            "lat": lat, "lon": lon, "issued_severity": {"scale": scale, "value": value},
            "published": published, "url": url, "text": text, "retrieved": NOW()}

def fetch_gdacs(offline=False):
    if offline: return _cache_read("gdacs")
    try:
        d = feedparser.parse(_get(FEEDS["gdacs"])); items = []
        for e in d.entries:
            items.append(norm("gdacs", e.get("gdacs_eventid", e.get("id", e.link)), e.get("gdacs_eventtype", "?"),
                              e.title, e.get("gdacs_country", ""), e.link, e.get("published", ""),
                              e.get("summary", ""), "GDACS", e.get("gdacs_alertlevel", ""),
                              float(e.get("geo_lat", 0) or 0), float(e.get("geo_long", 0) or 0)))
        _cache_write("gdacs", items); return items
    except Exception as ex:
        print("gdacs live failed, using cache:", ex); return _cache_read("gdacs")

def fetch_nhc(name, offline=False):
    if offline: return _cache_read(name)
    try:
        d = feedparser.parse(_get(FEEDS[name])); items = []
        for e in d.entries:
            wind = e.get("nhc_wind", ""); cyc = e.get("nhc_name", "")
            items.append(norm(name, e.get("id", e.link), "TC", e.title, "", e.link, e.get("published", ""),
                              e.get("summary", ""), "NHC_SSHWS", f"{cyc} {wind}".strip() or e.get("nhc_headline", "")))
        _cache_write(name, items); return items
    except Exception as ex:
        print(name, "live failed, using cache:", ex); return _cache_read(name)

def fetch_usgs(offline=False):
    if offline: return _cache_read("usgs")
    try:
        g = json.loads(_get(FEEDS["usgs"])); items = []
        for f in g["features"]:
            p = f["properties"]; lon, lat = f["geometry"]["coordinates"][:2]
            items.append(norm("usgs", f["id"], "EQ", p["title"], p.get("place", ""), p["url"],
                              dt.datetime.fromtimestamp(p["time"]/1000, dt.timezone.utc).isoformat(),
                              p["title"], "USGS_PAGER", f"M{p['mag']} / PAGER {p.get('alert')}", lat, lon))
        _cache_write("usgs", items); return items
    except Exception as ex:
        print("usgs live failed, using cache:", ex); return _cache_read("usgs")

def fetch_reliefweb(offline=False):
    if offline: return _cache_read("reliefweb")
    try:
        j = json.loads(_get(FEEDS["reliefweb"])); items = []
        for d in j["data"]:
            f = d["fields"]
            items.append(norm("reliefweb", d["id"], (f.get("primary_type") or {}).get("name", "?"), f["name"],
                              ", ".join(c["name"] for c in f.get("country", [])), f.get("url", ""),
                              (f.get("date") or {}).get("created", ""), f["name"], "RELIEFWEB", f.get("status", "")))
        _cache_write("reliefweb", items); return items
    except Exception as ex:
        print("reliefweb live failed, using cache:", ex); return _cache_read("reliefweb")

def fetch_gdelt(query, lang=None, offline=False, key=None):
    key = key or f"gdelt_{abs(hash((query, lang)))}"
    if offline: return _cache_read(key)
    q = query + (f" sourcelang:{lang}" if lang else "")
    url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={httpx.URL(q).path}&mode=artlist&format=json&maxrecords=30&timespan=3d"
    try:
        j = json.loads(_get(url)); items = []
        for a in j.get("articles", []):
            items.append(norm("gdelt", a["url"], "NEWS", a["title"], a.get("sourcecountry", ""), a["url"],
                              a.get("seendate", ""), a["title"], None, None) | {"lang": a.get("language", "")})
        _cache_write(key, items); return items
    except Exception as ex:
        print("gdelt live failed, using cache:", ex); return _cache_read(key)

def fetch_all(offline=False):
    items = []
    items += fetch_gdacs(offline); items += fetch_nhc("nhc_atl", offline); items += fetch_nhc("nhc_epac", offline)
    items += fetch_usgs(offline); items += fetch_reliefweb(offline)
    # WHO DON: TODO scrape https://www.who.int/emergencies/disease-outbreak-news item pages (see SPEC)
    return items

if __name__ == "__main__":
    import sys
    its = fetch_all(offline="--offline" in sys.argv)
    print(len(its), "items"); [print(i["feed"], "|", i["issued_severity"]["value"], "|", i["title"][:90]) for i in its[:40]]
