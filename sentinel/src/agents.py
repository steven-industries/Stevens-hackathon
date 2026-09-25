"""Sentinel agent stages. Every stage has a deterministic implementation; when ANTHROPIC_API_KEY is set the
LLM stages (scout refinement, assessor rationale, brief writers, router messages) call Claude and fall back to the
deterministic output on any error / invalid JSON / failed guard. Severity numbers always come from authority feeds."""
import csv, datetime as dt, html, json, math, os, re, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from . import feeds

MODEL = os.environ.get("SENTINEL_MODEL", "claude-sonnet-5")
AUTH_FEEDS = {"gdacs": "GDACS", "nhc_at": "NHC", "nhc_ep": "NHC", "nhc_cp": "NHC/CPHC", "usgs": "USGS",
              "who_don": "WHO DON", "ecdc": "ECDC", "eonet": "NASA EONET"}


# ======================================================================= trace
class Tracer:
    def __init__(self, path, run_id):
        self.path, self.run_id, self.lock, self.models = path, run_id, threading.Lock(), set()

    def log(self, agent, event_id, input_refs, output, summary, model="deterministic", latency_ms=0):
        rec = {"ts": feeds.now_iso(), "run_id": self.run_id, "agent": agent, "event_id": event_id,
               "input_refs": list(input_refs)[:40], "output": output, "summary": summary, "model": model,
               "latency_ms": int(latency_ms)}
        self.models.add(model)
        with self.lock, self.path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"  · {agent:<16} {summary[:150]}")


# ======================================================================= LLM helper
_FAILS = {"n": 0}
USED = set()


def llm_on():
    return bool(os.environ.get("ANTHROPIC_API_KEY")) and _FAILS["n"] < 3  # circuit breaker per process/cycle


def llm_json(system, payload, max_tokens=1800):
    """Returns (obj|None, model_label). Never raises."""
    if not llm_on():
        return None, "deterministic"
    try:
        import anthropic
        c = anthropic.Anthropic(timeout=60)
        m = c.messages.create(model=MODEL, max_tokens=max_tokens, system=system + "\nReply with ONE JSON object only, no prose.",
                              messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)[:60000]}])
        txt = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        j = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        _FAILS["n"] = 0; USED.add(MODEL)
        return j, MODEL
    except Exception as ex:
        _FAILS["n"] += 1
        print(f"    LLM fallback: {type(ex).__name__}: {str(ex)[:100]}")
        return None, "deterministic (llm fallback)"


def numbers_ok(text, allowed_text):
    """Guard: an LLM sentence may not introduce numbers absent from its inputs (no invented severities)."""
    allowed = set(re.findall(r"\d+(?:[.,]\d+)?", allowed_text))
    return all(n in allowed for n in re.findall(r"\d+(?:[.,]\d+)?", text or ""))


# ======================================================================= geo helpers
def hav(lat1, lon1, lat2, lon2):
    r = math.radians
    a = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1, a)))


def densify(pts, step_km=25):
    out = []
    for a, b in zip(pts, pts[1:]):
        d = hav(a[0], a[1], b[0], b[1]); n = max(1, int(d / step_km))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    return out + pts[-1:]


COUNTRY_LL = {"Democratic Republic of the Congo": (0.5, 25.0), "Uganda": (1.4, 32.3), "Nigeria": (9.1, 8.7),
              "India": (21.0, 78.0), "China": (35.0, 103.0), "Mexico": (23.6, -102.5), "United States": (39.8, -98.6),
              "Brazil": (-10.0, -52.0), "Indonesia": (-2.5, 118.0), "Philippines": (12.9, 121.8), "Japan": (36.2, 138.3),
              "Chile": (-35.7, -71.5), "Kenya": (0.0, 37.9), "Türkiye": (39.0, 35.2), "Cape Verde": (15.1, -23.6)}
LANGS = {"Mexico": ["es"], "Cape Verde": ["pt", "fr"], "Democratic Republic of the Congo": ["fr"], "Brazil": ["pt"],
         "Japan": ["ja"], "China": ["zh"], "Taiwan": ["zh"], "India": ["hi"], "Indonesia": ["id"], "Chile": ["es"],
         "Colombia": ["es"], "Peru": ["es"], "Türkiye": ["tr"], "United States": ["es"], "Philippines": [],
         "Uganda": ["fr"], "Haiti": ["fr"], "Cuba": ["es"], "Guatemala": ["es"], "Morocco": ["ar", "fr"],
         "Egypt": ["ar"], "Saudi Arabia": ["ar"], "Angola": ["pt"], "Mozambique": ["pt"], "Vanuatu": ["fr"],
         "Papua New Guinea": [], "Thailand": [], "Tonga": []}
CNAME = {"fr": {"Democratic Republic of the Congo": "RDC", "Mexico": "Mexique", "India": "Inde", "Cape Verde": "Cap-Vert"},
         "es": {"Democratic Republic of the Congo": "Congo", "Mexico": "México", "United States": "Estados Unidos"},
         "pt": {"Democratic Republic of the Congo": "Congo", "Cape Verde": "Cabo Verde", "Mexico": "México"},
         "en": {"Democratic Republic of the Congo": "Congo"}}
HAZ = {
    "TC": {"en": "hurricane", "es": "huracán", "fr": "ouragan", "pt": "furacão", "ja": "台風", "zh": "颱風", "hi": "चक्रवात", "ar": "إعصار", "id": "badai"},
    "TS": {"en": "tropical storm", "es": "tormenta tropical", "fr": "tempête tropicale", "pt": "tempestade tropical", "ja": "台風", "zh": "颱風", "hi": "चक्रवात"},
    "TY": {"en": "typhoon", "es": "tifón", "fr": "typhon", "pt": "tufão", "ja": "台風", "zh": "颱風"},
    "CY": {"en": "cyclone", "es": "ciclón", "fr": "cyclone", "pt": "ciclone", "hi": "चक्रवात", "ar": "إعصار"},
    "EQ": {"en": "earthquake", "es": "sismo", "fr": "séisme", "pt": "terremoto", "ja": "地震", "zh": "地震", "hi": "भूकंप", "ar": "زلزال", "id": "gempa", "tr": "deprem"},
    "FL": {"en": "floods", "es": "inundaciones", "fr": "inondations", "pt": "inundações", "ja": "洪水", "zh": "洪水", "hi": "बाढ़", "ar": "فيضانات", "id": "banjir", "tr": "sel"},
    "VO": {"en": "volcano", "es": "volcán", "fr": "volcan", "pt": "vulcão", "ja": "火山", "zh": "火山", "id": "gunung"},
    "WF": {"en": "wildfire", "es": "incendio", "fr": "incendie", "pt": "incêndio"},
    "DR": {"en": "drought", "es": "sequía", "fr": "sécheresse", "pt": "seca"},
}


# ======================================================================= portfolio
def load_book():
    locs = []
    with open("data/portfolio.csv") as f:
        for r in csv.DictReader(f):
            r["lat"], r["lon"], r["tiv_usd"] = float(r["lat"]), float(r["lon"]), int(r["tiv_usd"]); locs.append(r)
    trav = {}
    with open("data/travelers.csv") as f:
        for r in csv.DictReader(f):
            trav[r["country"]] = (int(r["insured_travelers"]), int(r["ah_members"]))
    return locs, trav


SCALE_NAME = {"NHC_SSHWS": "NHC Saffir-Simpson", "USGS_PAGER": "USGS PAGER", "WHO_DON": "WHO DON", "GDACS": "GDACS"}


def sname(sc):
    return SCALE_NAME.get(sc, sc)


def money(x):
    return f"${x/1e9:.2f}B" if x >= 1e9 else f"${x/1e6:.0f}M" if x >= 1e6 else f"${x:,.0f}"


# ======================================================================= verification primitives
def normtxt(s):
    s = html.unescape(s or ""); s = unicodedata.normalize("NFKC", s)
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def verify_quote(quote, item):
    if not quote or item is None:
        return False
    return normtxt(quote) in normtxt((item.get("title") or "") + " \n " + (item.get("text") or ""))


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])|\.\.\.\s*|\s{2,}|-{5,}|\s\|\s", text or "")
    return [p.strip(" .-") for p in parts if len(p.strip()) > 8]


def span(item, keywords, maxlen=260):
    """A verbatim span from the item's fetched text containing any keyword (first match in keyword order)."""
    if not item:
        return None
    ss = [x for x in sentences(item.get("text", "")) if not re.search(r"KNHC|BULLETIN|\bWT[A-Z]{2}\d|INCHES|Issued at|\bNNNN\b|-{3,}", x)]
    for kw in keywords:
        for s in ss:
            if kw.lower() in s.lower():
                if len(s) > maxlen:
                    i = s.lower().index(kw.lower()); a = max(0, i - maxlen // 2)
                    s = s[a:a + maxlen]
                    s = s[s.find(" ") + 1:] if a else s
                    s = s[:s.rfind(" ")] if len(s) >= maxlen - 5 else s
                return s.strip()
    return None


def news_quote(item):
    t = item.get("title", ""); o = (item.get("extra") or {}).get("outlet", "")
    return t[: -len(o) - 3].strip() if o and t.endswith(" - " + o) else t


# ======================================================================= 1. SCOUT
def _age_h(item, ref):
    d = feeds.parse_iso(item.get("published") or "")
    return (ref - d).total_seconds() / 3600 if d else 1e9


def _tc_name(item):
    if item["feed"].startswith("nhc"):
        return item["extra"]["storm"].lower()
    m = re.search(r"cyclone ([A-Z]+)-\d+", item["title"], re.I) or re.search(r"(?:Hurricane|Typhoon|Tropical Storm|Tropical Cyclone|Cyclone|Super Typhoon) (\w+)", item["title"])
    return m.group(1).lower() if m else ""


def scout(items, tr, max_events=8):
    t0 = time.time(); ref = dt.datetime.now(dt.timezone.utc)
    seeds, joiners = [], []
    for i in items:
        f, sev = i["feed"], (i["issued_severity"] or {}).get("value") or ""
        ex = i.get("extra") or {}
        if f.startswith("nhc"):
            seeds.append((0, i))
        elif f == "usgs" and _age_h(i, ref) < 24 * 8 and ((ex.get("mag") or 0) >= 6 or ex.get("alert") in ("yellow", "orange", "red")):
            seeds.append((1, i))
        elif f == "gdacs" and ex.get("iscurrent") == "true" and sev in ("Orange", "Red") and _age_h(i, ref) < 24 * 45 and i["type"] != "DR":
            seeds.append((2, i))
        elif f == "who_don" and _age_h(i, ref) < 24 * 60:
            seeds.append((3, i))
        elif f == "gdacs" and ex.get("iscurrent") == "true" and _age_h(i, ref) < 24 * 14 and i["type"] in ("TC", "EQ", "FL", "VO"):
            joiners.append(i)
        elif f == "eonet" and ex.get("category") in ("severeStorms", "volcanoes", "wildfires") and _age_h(i, ref) < 24 * 10:
            joiners.append(i)
        elif f == "ecdc" and _age_h(i, ref) < 24 * 21:
            joiners.append(i)
    events = []

    def match(ev, i):
        if ev["type"] == "OUTBREAK":
            if i["feed"] == "who_don":
                return ev["key"] == _dkey(i)
            return i["feed"] == "ecdc" and ev["disease_kw"] in i["title"].lower()
        if i["feed"] == "ecdc":
            return False
        t = "TC" if i["type"] in ("TC",) or (i.get("extra") or {}).get("category") == "severeStorms" else i["type"]
        if t != ev["type"] or i.get("lat") is None:
            return False
        if t == "TC":
            n = _tc_name(i)
            if n and ev.get("storm") and n == ev["storm"]:
                return True
            if n and ev.get("storm") and n not in ("one", "two", "three") and not n.isdigit() and not re.match(r"\d+[a-z]", n):
                return False
        lim = 300 if t == "EQ" else 600
        if t == "EQ":
            a, b = feeds.parse_iso(i["published"] or ""), feeds.parse_iso(ev["members"][0]["published"] or "")
            if a and b and abs((a - b).total_seconds()) > 2 * 86400:
                return False
        return hav(i["lat"], i["lon"], ev["lat"], ev["lon"]) < lim

    def new_event(i):
        ex = i.get("extra") or {}
        if i["type"] == "OUTBREAK":
            dz = ex.get("disease", i["title"]); kw = re.split(r"[\s(,]", dz)[0].lower()
            ctry = [c.strip() for c in re.split(r",|&| and ", i["country"]) if c.strip()]
            ll = COUNTRY_LL.get(ctry[0] if ctry else "", (0, 0))
            short = re.sub(r" disease caused by (.+)", r" (\1)", dz)
            cshort = {"Democratic Republic of the Congo": "DR Congo"}.get(ctry[0], ctry[0]) if ctry else ""
            return {"event_id": f"out-{kw}-{_slug(cshort or 'x')}-{i['published'][:4]}", "type": "OUTBREAK",
                    "name": f"{short} outbreak — {cshort}" if cshort else i["title"], "key": _dkey(i), "disease_kw": kw, "lat": ll[0], "lon": ll[1], "countries": ctry,
                    "members": [i]}
        if i["type"] == "TC" or i["feed"].startswith("nhc"):
            n = _tc_name(i)
            name = i["title"] if i["feed"].startswith("nhc") else f"Tropical Cyclone {n.upper()}"
            return {"event_id": f"tc-{n or _slug(i['id'])}-{(i['published'] or '2026')[:4]}", "type": "TC", "storm": n,
                    "name": name, "lat": i["lat"], "lon": i["lon"], "countries": _ctry(i), "members": [i]}
        if i["feed"] == "usgs":
            return {"event_id": f"eq-{i['id'].split(':')[1]}", "type": "EQ", "name": i["title"], "lat": i["lat"],
                    "lon": i["lon"], "countries": _ctry(i), "members": [i]}
        return {"event_id": f"{i['type'].lower()}-{_slug(i['country'])}-{i['id'].split(':')[1]}", "type": i["type"],
                "name": i["title"], "lat": i["lat"], "lon": i["lon"], "countries": _ctry(i), "members": [i]}

    for _, i in sorted(seeds, key=lambda x: x[0]):
        ev = next((e for e in events if match(e, i)), None)
        if ev:
            ev["members"].append(i)
        else:
            events.append(new_event(i))
    orphans = []
    for i in joiners:
        ev = next((e for e in events if match(e, i)), None)
        if ev:
            ev["members"].append(i)
        elif i["feed"] != "ecdc":
            orphans.append(i)
    # Green GDACS kept only if an independent feed (EONET) corroborates it
    for i in [o for o in orphans if o["feed"] == "gdacs"]:
        pal = [o for o in orphans if o["feed"] == "eonet" and o.get("lat") is not None and
               (("TC" if o["extra"].get("category") == "severeStorms" else o["type"]) == i["type"]) and
               ((_tc_name(o) and _tc_name(o) == _tc_name(i)) or hav(o["lat"], o["lon"], i["lat"], i["lon"]) < 400)]
        if pal:
            ev = new_event(i); ev["members"] += pal[:2]; events.append(ev)
    for ev in events:
        if ev["type"] == "TC" and not any(m["feed"].startswith("nhc") for m in ev["members"]):
            eo = next((m for m in ev["members"] if m["feed"] == "eonet"), None)
            if eo and re.match(r"^(one|two|three|four|five)$", ev.get("storm", "")):
                ev["name"] = f"{eo['title']} ({(ev['members'][0].get('country') or '').split(',')[0]})".replace(" ()", "")
        ev["stale"] = _stale(ev, ref)
        ev["feeds"] = sorted({m["feed"] for m in ev["members"]})
        for m in ev["members"]:
            for c in _ctry(m):
                if c not in ev["countries"]:
                    ev["countries"].append(c)
        ev["why_grouped"] = _why(ev)
        ev["prescore"] = _prescore(ev) - (30 if ev["stale"] else 0)
    events.sort(key=lambda e: -e["prescore"])
    dropped = len(events) - max_events
    events = events[:max_events]
    # optional LLM refinement: may only propose better display names (never severity), validated
    model = "deterministic"
    if llm_on() and events:
        j, model = llm_json("You are the Scout agent of an insurer early-warning system. For each event give a short,"
                            " precise display name (hazard + name + place). Do not add numbers not present in the input."
                            ' Output {"events":[{"event_id":..., "name":...}]}',
                            {"events": [{"event_id": e["event_id"], "name": e["name"], "countries": e["countries"],
                                         "titles": [m["title"] for m in e["members"]][:5]} for e in events]}, 800)
        if j:
            ok = 0
            for x in j.get("events", []):
                e = next((e for e in events if e["event_id"] == x.get("event_id")), None)
                allowed = " ".join([e["name"]] + [m["title"] for m in e["members"]]) if e else ""
                if e and x.get("name") and len(x["name"]) < 90 and numbers_ok(x["name"], allowed):
                    e["name"] = x["name"]; ok += 1
            if not ok:
                model = "deterministic (llm fallback)"
    out = [{"event_id": e["event_id"], "type": e["type"], "name": e["name"], "member_item_ids": [m["id"] for m in e["members"]],
            "why_grouped": e["why_grouped"]} for e in events]
    tr.log("scout", None, [i["id"] for s, i in seeds], {"events": out, "candidates": len(seeds) + len(joiners)},
           f"Scout: {len(seeds)} seed + {len(joiners)} supporting items → {len(events)} events"
           f"{f' (dropped {dropped} lower-priority)' if dropped > 0 else ''}: " + "; ".join(e["name"][:40] for e in events[:5]),
           model, (time.time() - t0) * 1000)
    return events


def _stale(ev, ref):
    """Authority says the event window closed >24h ago (GDACS todate) and no live NHC advisory."""
    if any(m["feed"].startswith("nhc") or m["feed"] == "who_don" for m in ev["members"]):
        return None
    for m in ev["members"]:
        td = (m.get("extra") or {}).get("todate")
        if m["feed"] == "gdacs" and td:
            try:
                d = dt.datetime.strptime(td, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc)
                if ref - d > dt.timedelta(hours=24):
                    return td
            except Exception:
                pass
    return None


def _dkey(i):
    dz = (i.get("extra") or {}).get("disease", i["title"]).lower()
    return re.split(r"[\s(,]", dz)[0] + "|" + (re.split(r",|&| and ", i["country"])[0].strip().lower())


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:30] or "x"


def _ctry(i):
    c = i.get("country") or ""
    if i["feed"] == "usgs":
        return [c] if c and not re.search(r"region|passage|ridge|islands,? ", c, re.I) else []
    return [x.strip() for x in re.split(r",|&", c) if x.strip()][:6]


def _why(ev):
    fs = sorted({AUTH_FEEDS.get(m["feed"], m["feed"]) for m in ev["members"]})
    if len(ev["members"]) == 1:
        return f"single authority item ({fs[0]})"
    if ev["type"] == "TC" and ev.get("storm"):
        return f"storm name '{ev['storm']}' matched across {', '.join(fs)}"
    if ev["type"] == "OUTBREAK":
        return f"same disease+country across {len(ev['members'])} bulletins ({', '.join(fs)})"
    return f"geo proximity (<600 km) and time window across {', '.join(fs)}"


def _prescore(ev):
    s = 0
    for m in ev["members"]:
        v = str((m["issued_severity"] or {}).get("value") or "")
        if m["feed"].startswith("nhc"):
            s = max(s, 40 + (m["extra"]["wind_mph"] or 0) / 4)
        elif m["feed"] == "usgs":
            s = max(s, {"red": 90, "orange": 75, "yellow": 60}.get(m["extra"].get("alert"), 45 + 5 * (m["extra"]["mag"] - 6)))
        elif m["feed"] == "gdacs":
            s = max(s, {"Red": 85, "Orange": 60, "Green": 25}.get(v, 20))
        elif m["feed"] == "who_don":
            s = max(s, 70)
    return s + 3 * len({m["feed"] for m in ev["members"]})


# ======================================================================= 2. CORROBORATOR
def _queries(ev):
    t = ev["type"]; ctry = ev["countries"][0] if ev["countries"] else ""
    langs = ["en"] + [l for l in LANGS.get(ctry, []) if l != "en"]
    for c in ev["countries"][1:3]:
        langs += [l for l in LANGS.get(c, []) if l not in langs]
    if t == "TC" and not ev["countries"]:
        lon = ev["lon"]
        langs += ["es"] if -130 < lon < -80 else ["ja", "zh"] if 110 < lon < 160 else ["fr", "pt"] if -40 < lon < 0 else []
    if t == "OUTBREAK":
        langs += [l for l in ("es", "pt") if l not in langs]
    langs = langs[:4]
    qs = []
    for l in langs:
        if t == "TC":
            nhc = next((m for m in ev["members"] if m["feed"].startswith("nhc")), None)
            kind = "TC" if nhc and "Hurricane" in nhc["extra"]["nhc_type"] else "TS" if nhc else ("TY" if 100 < ev["lon"] < 180 else "CY" if 40 < ev["lon"] < 100 else "TC")
            named = ev.get("storm") and not re.match(r"^(one|two|three|four|\d+[a-z]?)$", ev["storm"])
            word = HAZ[kind].get(l) or HAZ["TC"].get(l, "")
            if named:
                qs.append((l, f"{word} {ev['storm'].capitalize()}" if l not in ("ja", "zh") else ev["storm"].capitalize(), [ev["storm"]]))
            else:
                cn = CNAME.get(l, {}).get(ctry, ctry)
                qs.append((l, f"{word} {cn}", [word.lower()]))
        elif t == "OUTBREAK":
            cn = CNAME.get(l, {}).get(ctry, ctry)
            qs.append((l, f"{ev['disease_kw'].capitalize()} {cn}", [ev["disease_kw"]]))
        else:
            word = HAZ.get(t, HAZ["FL"]).get(l)
            if not word:
                continue
            place = ctry or ((ev["members"][0].get("extra") or {}).get("place") or "").split(" of ")[-1].split(",")[0]
            cn = CNAME.get(l, {}).get(place, place)
            qs.append((l, f"{word} {cn}".strip(), [word.lower().rstrip("s")]))
    return qs


def corroborate(ev, tr, offline):
    t0 = time.time(); ref = dt.datetime.now(dt.timezone.utc)
    win = {"TC": 8, "EQ": 4, "OUTBREAK": 30}.get(ev["type"], 12)
    ev_start = min((feeds.parse_iso(m["published"] or "") for m in ev["members"] if m.get("published")), default=None)
    news, qlog = [], []
    for lang, q, must in _queries(ev):
        got = feeds.gnews(q, lang, offline) + (feeds.gdelt(q, offline) if lang == "en" else [])
        keep = []
        for n in got:
            d = feeds.parse_iso(n.get("published") or "")
            if not d or (ref - d).days > win:
                continue
            if ev["type"] == "EQ" and ev_start and d < ev_start - dt.timedelta(hours=1):
                continue
            if not all(m.lower() in n["title"].lower() for m in must):
                continue
            if ev["type"] == "EQ":
                mags = [float(x) for x in re.findall(r"(?<![\d.])([4-9]\.\d)(?![\d])", n["title"])]
                emag = (ev["members"][0].get("extra") or {}).get("mag") or 0
                if mags and all(abs(x - emag) > 0.25 for x in mags):
                    continue
            keep.append(n)
        qlog.append({"lang": lang, "query": q, "hits": len(got), "kept": len(keep)})
        news += keep[:12]
    # independent sources: one per authority feed + one per distinct news domain
    srcs, seen = [], set()
    for m in sorted(ev["members"], key=lambda m: m.get("published") or "", reverse=True):
        fam = AUTH_FEEDS.get(m["feed"], m["feed"])
        if fam in seen:
            continue
        seen.add(fam); srcs.append(_src(m, ev))
    per_lang = {}
    for n in sorted(news, key=lambda n: n.get("published") or ""):
        dom = n["extra"].get("domain") or n["extra"].get("outlet")
        if dom in seen or per_lang.get(n["lang"], 0) >= 3:
            continue
        seen.add(dom); per_lang[n["lang"]] = per_lang.get(n["lang"], 0) + 1; srcs.append(_src(n, ev))
    ev["all_items"] = {m["id"]: m for m in ev["members"] + news}
    ev["sources"] = srcs
    ev["languages_seen"] = sorted({s["lang"] for s in srcs})
    ts = [s["published"] for s in srcs if s.get("published")]
    ev["first_signal_ts"] = min(ts) if ts else None
    ev["independent"] = len(seen)
    ev["status"] = "alert" if ev["independent"] >= 2 else "watch"
    ev["news_count"] = len(news)
    tr.log("corroborator", ev["event_id"], [s["id"] for s in srcs],
           {"corroboration_count": ev["independent"], "languages_seen": ev["languages_seen"], "earliest_signal_ts": ev["first_signal_ts"],
            "queries": qlog, "status": ev["status"]},
           f"Corroborator: {ev['independent']} independent sources in {len(ev['languages_seen'])} languages "
           f"({', '.join(ev['languages_seen'])}); earliest {(ev['first_signal_ts'] or '?')[:16]}Z → {ev['status'].upper()}",
           "deterministic", (time.time() - t0) * 1000)
    return ev


def _src(item, ev):
    if item["feed"] in ("gnews", "gdelt"):
        q = news_quote(item)
    else:
        q = span(item, _kw(ev["type"], item["feed"])) or item["title"]
    return {"id": item["id"], "feed": item["feed"] if item["feed"] != "gnews" else "news:" + (item["extra"].get("domain") or ""),
            "url": item["url"], "title": item["title"], "lang": item.get("lang", "en"),
            "published": item.get("published"), "quote": q, "verified": False, "_item": item["id"]}


def _kw(t, feed):
    if t == "TC":
        return ["maximum sustained winds", "CATEGORY", "Population affected", "WARNING", "wind speed"]
    if t == "EQ":
        return ["mag=", "Magnitude", "PAGER"]
    if t == "OUTBREAK":
        return ["confirmed cases", "cases", "deaths", "outbreak", "Ebola"]
    return ["alert", "affect", "displaced", "started"]


# ======================================================================= 3. VERIFIER (code, not LLM)
def verify_sources(ev, tr):
    t0 = time.time(); ok = 0
    for s in ev["sources"]:
        s["verified"] = verify_quote(s["quote"], ev["all_items"].get(s.pop("_item", s["id"])))
        ok += s["verified"]
    tr.log("verifier", ev["event_id"], [s["id"] for s in ev["sources"]],
           {"checked": len(ev["sources"]), "verified": ok, "method": "normalized substring match against fetched source text"},
           f"Verifier: {ok}/{len(ev['sources'])} source quotes found verbatim in fetched text (code check, not LLM)",
           "deterministic", (time.time() - t0) * 1000)


def verify_bullets(ev, bullets):
    by_url = {}
    for it in ev["all_items"].values():
        by_url.setdefault(it["url"], it)
    out, dropped, seenq = [], 0, set()
    for b in bullets:
        if not b or normtxt(b.get("quote")) in seenq:
            continue
        seenq.add(normtxt(b.get("quote")))
        if b.get("source_url") == "portfolio://synthetic":
            b["verified"] = True; out.append(b); continue
        b["verified"] = verify_quote(b.get("quote"), by_url.get(b.get("source_url")))
        if b["verified"]:
            out.append(b)
        else:
            dropped += 1
    return out, dropped


# ======================================================================= 4. ASSESSOR
def assess(ev, tr):
    t0 = time.time(); m = {x["feed"]: x for x in ev["members"]}
    nhc = next((x for x in ev["members"] if x["feed"].startswith("nhc")), None)
    gd = next((x for x in ev["members"] if x["feed"] == "gdacs"), None)
    us = m.get("usgs"); who = max((x for x in ev["members"] if x["feed"] == "who_don"), key=lambda x: x["published"], default=None)
    bd = []
    # authority severity (copied, never generated)
    if nhc:
        v = nhc["issued_severity"]["value"]; w = nhc["extra"]["wind_mph"]
        pts = 35 if w >= 157 else 30 if w >= 130 else 25 if w >= 111 else 18 if w >= 74 else 10
        sev = {"scale": "NHC_SSHWS", "value": v, "source_url": nhc["url"]}
        bd.append({"factor": "authority severity", "points": pts, "reason": f"NHC: {nhc['extra']['nhc_type']}, {w} mph → SSHWS {v.split(' (')[0]}", "source_url": nhc["url"]})
    elif us:
        a = us["extra"].get("alert"); mag = us["extra"]["mag"]
        pts = {"red": 35, "orange": 28, "yellow": 20}.get(a, 18 if mag >= 7 else 12 if mag >= 6 else 6)
        sev = {"scale": "USGS_PAGER", "value": us["issued_severity"]["value"], "source_url": us["url"]}
        bd.append({"factor": "authority severity", "points": pts, "reason": f"USGS M{mag}, PAGER {a or 'not issued'}", "source_url": us["url"]})
    elif who:
        risk = re.search(r"risk[^.]{0,80}?\b(very high|high|moderate|low)\b[^.]{0,40}?(national|regional|global)", who["text"], re.I)
        val = f"{who['extra']['don']}" + (f" · risk {risk.group(1).lower()} ({risk.group(2).lower()})" if risk else "")
        pts = 30 if risk and "high" in risk.group(1).lower() else 25
        sev = {"scale": "WHO_DON", "value": val, "source_url": who["url"]}
        bd.append({"factor": "authority severity", "points": pts, "reason": f"WHO Disease Outbreak News {val}", "source_url": who["url"]})
    elif gd:
        v = gd["issued_severity"]["value"]; pts = {"Red": 35, "Orange": 22, "Green": 8}.get(v, 5)
        sev = {"scale": "GDACS", "value": v, "source_url": gd["url"]}
        bd.append({"factor": "authority severity", "points": pts, "reason": f"GDACS alert level {v}", "source_url": gd["url"]})
    else:
        x = ev["members"][0]; sev = {"scale": x["issued_severity"]["scale"] or "EONET", "value": x["issued_severity"]["value"] or "observed", "source_url": x["url"]}
        bd.append({"factor": "authority severity", "points": 5, "reason": "observation only (no authority grade)", "source_url": x["url"]})
    if gd and (nhc or us) and gd["issued_severity"]["value"] in ("Orange", "Red"):
        bd.append({"factor": "authority severity", "points": 5, "reason": f"GDACS concurs: {gd['issued_severity']['value']}", "source_url": gd["url"]})
    n = ev["independent"]
    bd.append({"factor": "corroboration count", "points": min(15, 3 * n), "reason": f"{n} independent sources", "source_url": ev["sources"][0]["url"]})
    L = len(ev["languages_seen"])
    bd.append({"factor": "language diversity", "points": min(10, 4 * (L - 1)), "reason": f"{L} languages: {', '.join(ev['languages_seen'])}", "source_url": ""})
    # velocity/recency
    last = max((x.get("published") or "" for x in ev["members"]), default="")
    age = (dt.datetime.now(dt.timezone.utc) - (feeds.parse_iso(last) or dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc))).total_seconds() / 3600
    vel = 10 if age < 24 else 6 if age < 72 else 3 if age < 24 * 14 else 0
    if ev.get("stale"):
        vel = 0
    if ev["news_count"] >= 15:
        vel = min(10, vel + 2)
    bd.append({"factor": "velocity/recency", "points": vel, "reason": f"latest authority update {age:.0f}h ago; {ev['news_count']} matching news items"
               + (f"; GDACS event window ended {ev['stale'][:16]}" if ev.get("stale") else ""), "source_url": ""})
    # population (authority text)
    pop_pts, pop_reason, pop_url = 0, "no authority population figure", ""
    if gd:
        mm = re.search(r"\(([\d.]+) (million|thousand)? ?in Tropical Storm\)", gd["title"] + gd["text"]) or re.search(r"([\d.]+) (million|thousand) in MMI", gd["text"])
        if mm:
            val = float(mm.group(1)) * (1e6 if mm.group(2) == "million" else 1e3 if mm.group(2) == "thousand" else 1)
            pop_pts = 10 if val >= 5e6 else 7 if val >= 1e6 else 4 if val >= 1e5 else 1 if val > 0 else 0
            pop_reason, pop_url = f"GDACS population figure: {mm.group(0).strip('()')}", gd["url"]
    if who:
        mm = re.search(r"(\d[\d ,]*) confirmed cases", who["text"])
        if mm:
            pop_pts, pop_reason, pop_url = 8, f"WHO: {mm.group(0)}", who["url"]
    bd.append({"factor": "population", "points": pop_pts, "reason": pop_reason, "source_url": pop_url})
    ev["breakdown"] = bd; ev["issued_severity"] = sev
    # geo
    t = ev["type"]
    if t == "TC":
        w = nhc["extra"]["wind_mph"] if nhc else 0
        rad = 350 if w >= 157 else 300 if w >= 130 else 250 if w >= 111 else 200 if w >= 74 else 150
        if not nhc and gd:
            rad = {"Red": 300, "Orange": 250}.get(gd["issued_severity"]["value"], 150)
    elif t == "EQ":
        mag = us["extra"]["mag"] if us else 6
        rad = int(max(50, min(400, 100 * 10 ** (0.5 * (mag - 6)))))
    else:
        rad = {"OUTBREAK": 500, "FL": 150, "WF": 50, "VO": 30}.get(t, 150)
    track = [(ev["lat"], ev["lon"])] + [(p["lat"], p["lon"]) for p in (nhc["extra"]["track"] if nhc else [])]
    ev["track"] = track
    regions = []
    if nhc:
        regions.append({"nhc_at": "North Atlantic", "nhc_ep": "Eastern North Pacific", "nhc_cp": "Central North Pacific"}[nhc["feed"]])
        mh = re.findall(r"INTERESTS IN ([A-Z ]+?) SHOULD", nhc["text"])
        regions += [x.title() for x in mh]
    if us and us["extra"].get("place"):
        regions.append(us["extra"]["place"])
    ev["geo"] = {"lat": round(ev["lat"], 3), "lon": round(ev["lon"], 3), "countries": ev["countries"], "regions": regions, "radius_km": rad}
    ev["time_horizon"] = {"TC": "24-72h (NHC 5-day track)", "EQ": "0-72h (aftershocks, damage reports)", "OUTBREAK": "2-6 weeks",
                          "FL": "24-96h", "WF": "24-72h", "VO": "days-weeks"}.get(t, "24-72h")
    un = {"TC": ["Landfall location/timing beyond the NHC cone", "Storm-surge and rainfall damage footprint", "Insured vs economic loss split"],
          "EQ": ["PAGER loss estimate may be revised in first 24h", "Aftershock sequence", "Tsunami impact if any", "Building-stock damage ratios"],
          "OUTBREAK": ["True case count (under-reporting, testing capacity)", "Cross-border spread and travel restrictions", "Vaccine/therapeutic effectiveness for this strain"],
          }.get(t, ["Extent of damage footprint", "Duration", "Insured loss share"])
    if t == "TC" and nhc and not nhc["extra"]["track"]:
        un.insert(0, "No NHC forecast track parsed this cycle")
    if not ev["countries"]:
        un.insert(0, "No country currently named as affected by authority feeds")
    if ev.get("stale"):
        un.insert(0, f"GDACS event window ended {ev['stale'][:16]}; no fresh authority update — may have dissipated")
    ev["unknowns"] = un
    src_ok = sum(s["verified"] for s in ev["sources"])
    conf = "high" if n >= 4 and L >= 2 and src_ok >= 3 else "med" if n >= 2 else "low"
    ev["confidence"] = conf
    ev["confidence_rationale"] = (f"{n} independent sources ({src_ok} verified quotes) across {L} language(s); severity from {sname(sev['scale'])}"
                                  + ("; single-source, awaiting corroboration" if n < 2 else ""))
    model = "deterministic"
    if llm_on():
        facts = {"name": ev["name"], "issued_severity": sev, "sources": [{"title": s["title"], "quote": s["quote"], "lang": s["lang"]} for s in ev["sources"]],
                 "confidence": conf, "breakdown": bd}
        j, model = llm_json("You are the Assessor agent for an insurer. Given the facts, write a one-line confidence rationale (<=200 chars) "
                            "citing the evidence, and up to 4 'unknowns' (what we cannot say yet). Never state a severity or number that is "
                            'not in the input. Output {"confidence_rationale":..., "unknowns":[...]}', facts, 600)
        allowed = json.dumps(facts, ensure_ascii=False)
        if j and numbers_ok(j.get("confidence_rationale", ""), allowed) and 10 < len(j.get("confidence_rationale", "")) < 260:
            ev["confidence_rationale"] = j["confidence_rationale"]
            if isinstance(j.get("unknowns"), list) and all(numbers_ok(u, allowed) for u in j["unknowns"]):
                ev["unknowns"] = [str(u)[:160] for u in j["unknowns"][:5]] or un
        elif j is not None or model != "deterministic":
            model = "deterministic (llm fallback)"
    return model, t0


def finish_assess(ev, tr, model, t0):
    """Score after exposure (exposure concentration is a factor)."""
    tiv = ev["exposure"]["tiv_usd"] + 0
    pts = 0 if tiv <= 0 else min(20, int(4 * math.log10(max(1, tiv / 1e6)) + 4))
    if ev["type"] == "OUTBREAK":
        lives = ev["exposure"]["insured_travelers"]; pts = min(20, int(lives / 500))
        reason = f"{lives:,} insured travelers/A&H lives in affected countries (synthetic book)"
    else:
        reason = f"{ev['exposure']['policies']} locations, {money(tiv)} TIV within {ev['geo']['radius_km']} km (synthetic book)"
    ev["breakdown"].append({"factor": "exposure concentration", "points": pts, "reason": reason, "source_url": "portfolio://synthetic"})
    score = max(0, min(100, sum(b["points"] for b in ev["breakdown"])))
    tier = "RED" if score >= 70 else "AMBER" if score >= 45 else "WATCH"
    if (ev["status"] == "watch" or ev.get("stale")) and tier == "RED":
        tier = "AMBER"
    if ev.get("stale") and tier == "AMBER" and score < 60:
        tier = "WATCH"
    ev["risk_score"], ev["tier"] = score, tier
    tr.log("assessor", ev["event_id"], [s["id"] for s in ev["sources"]],
           {"issued_severity": ev["issued_severity"], "risk_score": score, "tier": tier, "score_breakdown": ev["breakdown"],
            "confidence": ev["confidence"], "geo": ev["geo"], "time_horizon": ev["time_horizon"], "unknowns": ev["unknowns"]},
           f"Assessor: {sname(ev['issued_severity']['scale'])} {ev['issued_severity']['value']} (copied) → risk {score}/100 {tier}, "
           f"confidence {ev['confidence']}; radius {ev['geo']['radius_km']} km",
           model, (time.time() - t0) * 1000)


# ======================================================================= 5. EXPOSURE
def exposure(ev, book, tr):
    t0 = time.time(); locs, trav = book; rad = ev["geo"]["radius_km"]
    hits = []
    if ev["type"] == "OUTBREAK":
        cs = set(ev["countries"])
        hits = [(l, hav(l["lat"], l["lon"], ev["lat"], ev["lon"])) for l in locs if l["country"] in cs]
        method = (f"SYNTHETIC demo book (seeded generator, not real policies): locations in affected countries {sorted(cs)} "
                  f"+ insured travelers/A&H members from data/travelers.csv")
    else:
        pts = densify(ev["track"]) if len(ev["track"]) > 1 else ev["track"]
        for l in locs:
            if abs(l["lat"] - ev["lat"]) > 25:
                continue
            d = min(hav(l["lat"], l["lon"], a, b) for a, b in pts)
            if d <= rad:
                hits.append((l, d))
        method = (f"SYNTHETIC demo book (seeded generator, not real policies): insured locations within {rad} km of "
                  + ("the NHC current position + forecast track" if len(ev["track"]) > 1 else "the event point") + " (haversine)")
    by = {}
    for l, d in hits:
        b = by.setdefault(l["line"], {"line": l["line"], "policies": 0, "tiv_usd": 0}); b["policies"] += 1; b["tiv_usd"] += l["tiv_usd"]
    top = sorted(hits, key=lambda x: -x[0]["tiv_usd"])[:5]
    countries_hit = sorted({l["country"] for l, _ in hits})
    tv = sum(sum(trav.get(c, (0, 0))) for c in ev["countries"]) if ev["type"] == "OUTBREAK" else sum(trav.get(c, (0, 0))[0] for c in countries_hit)
    ev["exposure"] = {"policies": len(hits), "tiv_usd": sum(l["tiv_usd"] for l, _ in hits),
                      "by_line": sorted(by.values(), key=lambda b: -b["tiv_usd"]),
                      "top_locations": [{"name": l["name"], "lat": l["lat"], "lon": l["lon"], "tiv_usd": l["tiv_usd"],
                                         "distance_km": round(d), "line": l["line"]} for l, d in top],
                      "insured_travelers": tv, "method": method}
    if not ev["countries"] and countries_hit:
        ev["countries"] += countries_hit; ev["geo"]["countries"] = ev["countries"]
    e = ev["exposure"]
    tr.log("exposure", ev["event_id"], ["portfolio://synthetic"], e,
           f"Exposure: {e['policies']} insured locations, {money(e['tiv_usd'])} TIV in footprint"
           + (f"; top line {e['by_line'][0]['line']} {money(e['by_line'][0]['tiv_usd'])}" if e["by_line"] else "")
           + (f"; {e['insured_travelers']:,} travelers/A&H lives" if e["insured_travelers"] else "") + " (synthetic book)",
           "deterministic", (time.time() - t0) * 1000)


# ======================================================================= 6. BRIEFS
def _B(text, item, kws, show=False):
    """show=True puts the verified fact itself into the bullet text (trimmed), so the reader sees the number, not a label."""
    q = span(item, kws) if item else None
    if q and show:
        qq = q if len(q) <= 170 else q[:167].rsplit(" ", 1)[0] + "…"
        text = f"{text.rstrip('.')}: “{qq}”"
    return {"text": text, "source_url": item["url"], "quote": q} if q else None


def _P(text):
    return {"text": text, "source_url": "portfolio://synthetic", "quote": text, "verified": True}


def _news_bullets(ev, k=2, prefix="Local-language press"):
    out = []
    ns = [s for s in ev["sources"] if s["feed"].startswith("news:") and s["verified"]]
    for s in (sorted(ns, key=lambda s: s["lang"] == "en"))[:k]:
        out.append({"text": f"{prefix} ({s['lang']}, {s['feed'][5:]}): “{s['quote'][:170]}”", "source_url": s["url"], "quote": s["quote"]})
    return out


def det_briefs(ev):
    t = ev["type"]; mem = ev["members"]
    nhc = next((x for x in mem if x["feed"].startswith("nhc")), None)
    gd = next((x for x in mem if x["feed"] == "gdacs"), None)
    us = next((x for x in mem if x["feed"] == "usgs"), None)
    who = max((x for x in mem if x["feed"] == "who_don"), key=lambda x: x["published"], default=None)
    ecdc = next((x for x in mem if x["feed"] == "ecdc"), None)
    eo = next((x for x in mem if x["feed"] == "eonet"), None)
    e = ev["exposure"]; tier = ev["tier"]; place = ", ".join(ev["countries"][:3]) or "open ocean / no named country"
    lines = {b["line"]: b for b in e["by_line"]}
    def L(n):
        b = lines.get(n); return f"{b['policies']} policies / {money(b['tiv_usd'])}" if b else "none"
    H, W, I = [], [], []
    posture = "strengthen" if tier == "RED" and e["tiv_usd"] > 0 else "watch" if (tier != "WATCH" or e["tiv_usd"] > 0 or e["insured_travelers"]) else "no action"
    if t == "TC":
        a = nhc or gd or eo
        H += [_B("Authority wind intensity defines the life-safety zone; expect trauma and displacement near the core.", a, ["maximum sustained winds", "wind speed", "kts"], show=True),
              _B("Heavy rain / flash-flood hazard raises waterborne-disease and access-to-care risk.", nhc, ["rainfall", "flash flooding", "flooding"], show=True),
              _B("Storm surge / coastal hazard messaging from NHC.", nhc, ["storm surge", "surf", "swells"], show=True),
              _B("GDACS population exposure estimate for the wind field.", gd, ["Population affected", "population"], show=True)]
        H += _news_bullets(ev, 2, "Local-language press flags community impact")
        W += [_B(f"Regional market read-through for {place}: tourism, ports and infrastructure in the path; watch local equities/FX and sub-sovereign credit.", a, ["CATEGORY", "affects these countries", "Hurricane", "Tropical"]),
              _B("Track and forward speed set the window for supply-chain disruption (ports, shipping lanes).", nhc, ["movement", "moving"])]
        W += _news_bullets(ev, 2, "Market-moving coverage")
        I += [_B(f"Authority severity {ev['issued_severity']['value']} ({sname(ev['issued_severity']['scale'])}) — Property/HNW Homeowners claims direction: UP if the core nears insured coast.", a, ["CATEGORY", "maximum sustained winds", "wind speed"]),
              _P(f"Synthetic book in footprint ({ev['geo']['radius_km']} km of {'NHC forecast track' if len(ev['track']) > 1 else 'current position'}): {e['policies']} locations, {money(e['tiv_usd'])} TIV."),
              _P(f"By line — Commercial Property {L('Commercial Property')}; HNW Homeowners {L('High-Net-Worth Homeowners')}; Marine Cargo {L('Marine Cargo')}; BI {L('Business Interruption')}."),
              _B("Watches/warnings define claims-notification timing; pre-position adjusters and CAT team.", nhc, ["Warning is in effect", "Watch is in effect", "should monitor", "SHOULD MONITOR", "warning"]),
              _B(f"Reserving posture: {posture}. Check cat XoL retention erosion, ILW/parametric cat-bond trigger boxes against the forecast track.", nhc or gd, ["located near", "center of", "Tropical Storm"])]
    elif t == "EQ":
        a = us or gd
        H += [_B("Shaking intensity/population exposure drives casualty and hospital-surge risk.", gd, ["MMI", "potentially affecting"], show=True),
              _B("USGS PAGER alert level indicates the expected fatality/loss band.", us, ["PAGER alert"], show=True),
              _B("USGS tsunami flag for coastal health planning.", us, ["tsunami="]),
              _B("Felt reports indicate population experiencing shaking.", us, ["felt reports"])] + _news_bullets(ev, 2, "Local-language press")
        W += [_B(f"Infrastructure, ports, mining and manufacturing in {place} may see short-term disruption.", a, ["mag=", "Magnitude", "earthquake"])] + _news_bullets(ev, 2, "Coverage")
        I += [_B(f"Authority severity {ev['issued_severity']['value']} — commercial property & BI claims direction depends on proximity to insured sites.", a, ["PAGER alert", "Magnitude"]),
              _P(f"Synthetic book within {ev['geo']['radius_km']} km of epicentre: {e['policies']} locations, {money(e['tiv_usd'])} TIV."),
              _P(f"By line — Commercial Property {L('Commercial Property')}; BI {L('Business Interruption')}; Energy {L('Energy')}."),
              _B(f"Reserving posture: {posture}. EQ sub-limits/deductibles typically absorb moderate events; confirm aftershock hours clause.", us or gd, ["depth_km", "Depth"])]
    elif t == "OUTBREAK":
        H += [_B("WHO case/death count", who, ["confirmed cases", "deaths", "cases"], show=True),
              _B("Spread across health zones signals health-system strain", who, ["health zones", "provinces", "spread"], show=True),
              _B("WHO on onward-spread risk", who, ["assesses the risk", "risk is", "risk of further spread", "risk"], show=True),
              _B("ECDC situational reporting relevant to EU travellers.", ecdc, ["Ebola", ev.get("disease_kw", "")] if ecdc else [])]
        H += _news_bullets(ev, 2, "Multilingual press")
        W += [_B(f"Regional economies ({place}): mining, logistics and cross-border trade face disruption risk from containment measures.", who, ["transmission", "outbreak", "spread"]),
              _B("Travel and aviation demand to affected areas likely to soften; watch airlines/hospitality exposure.", who, ["travel", "border", "international"])]
        W += _news_bullets(ev, 1, "Coverage")
        I += [_B(f"Authority: {ev['issued_severity']['value']} — A&H and Travel medical/evacuation claims direction: UP.", who, ["confirmed cases", "cases", "deaths"]),
              _P(f"Synthetic book: {e['insured_travelers']:,} insured travelers/A&H members in {place}; {e['policies']} insured locations ({money(e['tiv_usd'])} TIV) in-country."),
              _P(f"By line in affected countries — Commercial Property {L('Commercial Property')}; BI {L('Business Interruption')}; A&H {L('Accident & Health')}."),
              _B(f"Reserving posture: {posture}. Review contingent BI (CBI) and event-cancellation communicable-disease exclusions; marine cargo port-delay exposure.", who, ["spread", "health zones", "provinces", "transmission"])]
    else:
        a = gd or eo or mem[0]
        H += [_B("Authority alert describes the affected area and displacement.", a, ["displaced", "deaths", "affect", "started"], show=True)] + _news_bullets(ev, 1)
        W += [_B(f"Local infrastructure and agriculture in {place} may be disrupted.", a, ["alert", "started", "affect"])] + _news_bullets(ev, 1, "Coverage")
        I += [_B(f"Authority alert ({ev['issued_severity']['value']}) — property/BI claims direction depends on insured presence.", a, ["alert", "started", "affect"]),
              _P(f"Synthetic book within {ev['geo']['radius_km']} km: {e['policies']} locations, {money(e['tiv_usd'])} TIV."),
              _B(f"Reserving posture: {posture}.", a, ["alert", "started", "affect", "flood", "fire"])]
    hazard = {"TC": "tropical cyclone", "EQ": "earthquake", "OUTBREAK": "outbreak"}.get(t, "hazard")
    cav = ["Exposure figures use a SYNTHETIC demo book, not real policies.", "Severity is copied from the issuing authority; Sentinel does not forecast intensity."]
    return {
        "health": {"headline": f"{ev['name']}: health impact watch ({tier})", "bullets": H, "caveats": cav[1:]},
        "wealth": {"headline": f"{ev['name']}: market/sector read-through for {place}", "bullets": W, "caveats": ["Not investment advice; directional only."]},
        "insurance": {"headline": f"{ev['name']}: {money(e['tiv_usd'])} TIV / {e['policies']} locations in {hazard} footprint — posture {posture.upper()}",
                      "bullets": I, "caveats": cav, "reserving_posture": posture},
    }


BRIEF_ROLE = {
    "health": "Health brief writer (chief medical officer lens): exposed population, health-system strain, case trajectory.",
    "wealth": "Wealth brief writer (CIO lens): sectors, asset classes, regional markets likely affected; caveated, not advice.",
    "insurance": "Insurance brief writer (underwriter lens): lines of business (HO, commercial property, BI, marine, event cancellation, A&H, travel), claims-exposure direction, reserving posture (watch|strengthen|no action), reinsurance/cat-bond/ILW notes.",
}


def briefs(ev, tr):
    det = det_briefs(ev)
    out = {}
    for k in ("health", "wealth", "insurance"):
        t0 = time.time(); model = "deterministic"; b = det[k]
        if llm_on():
            facts = {"event": ev["name"], "type": ev["type"], "tier": ev["tier"], "issued_severity": ev["issued_severity"],
                     "exposure": {x: ev["exposure"][x] for x in ("policies", "tiv_usd", "by_line", "insured_travelers", "method")},
                     "sources": [{"url": s["url"], "title": s["title"], "lang": s["lang"],
                                  "text": (ev["all_items"].get(s["id"]) or {}).get("text", "")[:2500]} for s in ev["sources"][:8]],
                     "portfolio_lines": [x["quote"] for x in det[k]["bullets"] if x and x["source_url"] == "portfolio://synthetic"]}
            j, model = llm_json(f"You are the {BRIEF_ROLE[k]} Write 3-6 bullets. EVERY bullet must cite source_url from the sources list and a "
                                "'quote' copied VERBATIM (exact substring, <=250 chars) from that source's text or title; portfolio lines may be "
                                "cited with source_url 'portfolio://synthetic' and the line itself as quote. Never invent severity numbers. "
                                'Output {"headline":...,"bullets":[{"text":...,"source_url":...,"quote":...}],"caveats":[...]'
                                + (',"reserving_posture":"watch|strengthen|no action"' if k == "insurance" else "") + "}", facts, 1500)
            if j and isinstance(j.get("bullets"), list):
                cand = [{"text": str(x.get("text", ""))[:400], "source_url": x.get("source_url"), "quote": x.get("quote")} for x in j["bullets"]]
                cand = [c for c in cand if c["source_url"] != "portfolio://synthetic" or c["quote"] in facts["portfolio_lines"]]
                good, _ = verify_bullets(ev, cand)
                if len(good) >= 2:
                    b = {"headline": str(j.get("headline") or b["headline"])[:160], "bullets": cand,
                         "caveats": (j.get("caveats") or [])[:3] + ["Exposure figures use a SYNTHETIC demo book."]}
                    if k == "insurance":
                        b["reserving_posture"] = j.get("reserving_posture") if j.get("reserving_posture") in ("watch", "strengthen", "no action") else det[k]["reserving_posture"]
                else:
                    model = "deterministic (llm fallback: <2 verified bullets)"
        raw = [x for x in b["bullets"] if x]
        b["bullets"], dropped = verify_bullets(ev, raw)
        out[k] = b
        tr.log(f"brief_{k}", ev["event_id"], [x["source_url"] for x in b["bullets"]], b,
               f"Brief {k}: {len(b['bullets'])} cited bullets ({dropped} dropped by verifier)"
               + (f"; posture {b['reserving_posture'].upper()}" if k == "insurance" else "") + f" — {b['headline'][:70]}",
               model, (time.time() - t0) * 1000)
    return out


# ======================================================================= 7. ROUTER
PERSONAS = [("CUO Property", "insurance", "email"), ("Head of Claims", "insurance", "slack"),
            ("Cat Modeling/Accumulation desk", "insurance", "slack"), ("CIO", "wealth", "email"),
            ("Head of A&H/Travel", "health", "sms"), ("Public", "health", "public")]


def route(ev, tr):
    t0 = time.time(); tier, t, e = ev["tier"], ev["type"], ev["exposure"]
    pr = {"RED": "P1", "AMBER": "P2", "WATCH": "P3"}[tier]
    natcat = t != "OUTBREAK"
    cav = f"Early-warning signal ({ev['confidence']} confidence); severity per {sname(ev['issued_severity']['scale'])}; exposure from a synthetic demo book."
    top = e["top_locations"][0]["name"] if e["top_locations"] else "none in footprint"
    rules = {
        "CUO Property": natcat and (e["tiv_usd"] > 0 or tier == "RED"),
        "Head of Claims": natcat and e["policies"] > 0 and tier != "WATCH",
        "Cat Modeling/Accumulation desk": natcat and tier in ("RED", "AMBER"),
        "CIO": tier in ("RED", "AMBER"),
        "Head of A&H/Travel": t == "OUTBREAK" or (e["insured_travelers"] > 0 and tier != "WATCH"),
        "Public": ev["status"] == "alert" and tier in ("RED", "AMBER"),
    }
    sev = f"{sname(ev['issued_severity']['scale'])} {ev['issued_severity']['value']}"
    msgs = {
        "CUO Property": f"[{tier} {pr}] {ev['name']}: {sev}. {e['policies']} insured locations / {money(e['tiv_usd'])} TIV in footprint. Posture: {ev['briefs']['insurance']['reserving_posture']}. Largest: {top}.",
        "Head of Claims": f"[{tier} {pr}] {ev['name']}: {e['policies']} locations in footprint ({money(e['tiv_usd'])} TIV). Pre-position adjusters; FNOL surge likely within {ev['time_horizon']}.",
        "Cat Modeling/Accumulation desk": f"[{tier} {pr}] {ev['name']} ({sev}). Run event footprint vs accumulation zones: {money(e['tiv_usd'])} TIV within {ev['geo']['radius_km']} km. Check XoL retention and ILW/cat-bond triggers.",
        "CIO": f"[{tier} {pr}] {ev['name']} ({sev}) affecting {', '.join(ev['countries'][:3]) or 'open ocean'}. Review regional equity/credit and insurer-sector exposure. Directional only.",
        "Head of A&H/Travel": f"[{tier} {pr}] {ev['name']}: {e['insured_travelers']:,} insured travelers/A&H lives in affected area. Check assistance capacity, evacuation triggers and travel advisories.",
        "Public": f"{ev['name']}: official status {sev}. Follow local authority guidance. (Automated early-warning summary; may change.)",
    }
    model = "deterministic"
    if llm_on():
        j, model = llm_json("You are the Router agent. Rewrite each persona's notification to be crisp and actionable (<=400 chars). Keep all numbers "
                            'exactly; add none. Output {"messages":{"<persona>":"text"}}', {"event": ev["name"], "tier": tier, "messages": {p: m for p, m in msgs.items() if rules[p]}}, 900)
        if j:
            for p, m in (j.get("messages") or {}).items():
                if p in msgs and isinstance(m, str) and len(m) <= 400 and numbers_ok(m, msgs[p]):
                    msgs[p] = m
    routing = [{"persona": p, "brief": b, "channel": c, "priority": pr, "caveat_banner": cav, "message": msgs[p][:400]}
               for p, b, c in PERSONAS if rules[p]]
    ev["routing"] = routing
    tr.log("router", ev["event_id"], [ev["event_id"]], {"routing": routing},
           f"Router: {tier} {pr} → " + (", ".join(r["persona"] for r in routing) or "no persona (below threshold)"),
           model, (time.time() - t0) * 1000)
    return routing
