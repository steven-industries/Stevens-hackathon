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


# LLM backend: "api" (ANTHROPIC_API_KEY) or "cli" (the local, logged-in Claude Code CLI in headless mode:
# `claude -p`, which works with a Claude Pro/Max subscription - no API key needed). Auto-detected.
import shutil, subprocess, tempfile
CLI_MODEL = os.environ.get("SENTINEL_CLI_MODEL", "sonnet")


def backend():
    b = os.environ.get("SENTINEL_LLM", "").lower()
    if b in ("off", "none", "deterministic"):
        return None
    if b == "cli" or (not b and not os.environ.get("ANTHROPIC_API_KEY") and shutil.which("claude")):
        return "cli" if shutil.which("claude") else None
    return "api" if os.environ.get("ANTHROPIC_API_KEY") else None


def model_label():
    return f"claude-code-cli ({CLI_MODEL})" if backend() == "cli" else MODEL


def llm_on():
    return backend() is not None and _FAILS["n"] < 3  # circuit breaker per process/cycle


def _call_cli(system, user_text):
    """One headless Claude Code call: no tools, no MCP, no session saved, run from a temp dir (no CLAUDE.md)."""
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # use the subscription login
    cmd = ["claude", "-p", "--output-format", "json", "--model", CLI_MODEL, "--system-prompt", system,
           "--tools", "", "--strict-mcp-config", "--no-session-persistence"]
    r = subprocess.run(cmd, input=user_text, capture_output=True, text=True, timeout=180,
                       cwd=tempfile.gettempdir(), env=env)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p exit {r.returncode}: {(r.stderr or r.stdout)[:200]}")
    out = json.loads(r.stdout)
    if out.get("is_error"):
        raise RuntimeError(f"claude -p error: {str(out.get('result'))[:200]}")
    return out.get("result") or ""


_CACHE_P = os.path.join("log", "llm_cache.json")
_CACHE_LOCK = threading.Lock()
try:
    _CACHE = json.load(open(_CACHE_P))
except Exception:
    _CACHE = {}


def llm_json(system, payload, max_tokens=1800):
    """Returns (obj|None, model_label). Never raises.
    Cost control: responses are cached by a hash of (model, prompt, evidence) - an unchanged event is not re-briefed."""
    if not llm_on():
        return None, "deterministic"
    import hashlib
    label = model_label()
    key = hashlib.sha1((label + system + json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)).encode()).hexdigest()
    if key in _CACHE:
        return _CACHE[key], label + " (cached)"
    try:
        sysp = system + "\nReply with ONE JSON object only, no prose, no code fences."
        user_text = json.dumps(payload, ensure_ascii=False, default=str)[:60000]
        if backend() == "cli":
            txt = _call_cli(sysp, user_text)
        else:
            import anthropic
            c = anthropic.Anthropic(timeout=60)
            m = c.messages.create(model=MODEL, max_tokens=max_tokens, system=sysp,
                                  messages=[{"role": "user", "content": user_text}])
            txt = "".join(b.text for b in m.content if getattr(b, "type", "") == "text")
        j = json.loads(txt[txt.index("{"): txt.rindex("}") + 1])
        _FAILS["n"] = 0; USED.add(label)
        with _CACHE_LOCK:
            _CACHE[key] = j
            try:
                os.makedirs("log", exist_ok=True); json.dump(_CACHE, open(_CACHE_P, "w"))
            except Exception:
                pass
        return j, label
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


# centroids of provinces named in WHO text (only matched names are used), ~200 km screen each
PROVINCES = {"Democratic Republic of the Congo": {
    "Ituri": (1.6, 29.6, [r"Ituri"]), "North Kivu": (-0.8, 29.0, [r"North Kivu", r"Nord-Kivu"]),
    "South Kivu": (-3.0, 28.3, [r"South Kivu", r"Sud-Kivu"]), "Haut-Uélé": (3.5, 28.5, [r"Haut[- ]U[ée]l[ée]"]),
    "Bas-Uélé": (3.4, 24.4, [r"Bas[- ]U[ée]l[ée]"]), "Tshopo": (0.6, 25.2, [r"Tshopo"]), "Kinshasa": (-4.44, 15.27, [r"Kinshasa"]),
    "Équateur": (0.0, 19.0, [r"[ÉE]quateur"]), "Kasai": (-5.0, 21.5, [r"Kasa[iï](?![- ](?:Oriental|Central))"]),
    "Kasai-Oriental": (-6.1, 23.6, [r"Kasa[iï][- ]Oriental"]), "Kasai-Central": (-5.9, 22.4, [r"Kasa[iï][- ]Central"]),
    "Maniema": (-3.0, 26.0, [r"Maniema"]), "Tanganyika": (-6.3, 27.5, [r"Tanganyika"]), "Haut-Katanga": (-10.5, 27.5, [r"Haut[- ]Katanga"])},
    "Uganda": {"Kampala": (0.35, 32.58, [r"Kampala"]), "Kasese": (0.18, 30.08, [r"Kasese"]), "Bundibugyo": (0.71, 30.06, [r"Bundibugyo district"])}}
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
            r["lat"], r["lon"], r["tiv_usd"] = float(r["lat"]), float(r["lon"]), int(r["tiv_usd"])
            r["bi_tiv_usd"] = int(r.get("bi_tiv_usd") or 0); locs.append(r)
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
    ss = [x for x in sentences(item.get("text", "")) if not re.search(r"KNHC|BULLETIN|\bWT[A-Z]{2}\d|INCHES|Issued at|\bNNNN\b|-{3,}", x)
          and not BOILER.search(x) and len(x) >= 25]
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


BOILER = re.compile(r"please see|graphic|available at|hurricanes\.gov|for more information|shtml|https?://", re.I)


def good_quote(q, ev):
    """Reject quotes that are too short or merely the event/storm name (e.g. JTWC title 'Hurricane Polo')."""
    if not q or len(q.strip()) < 25:
        return False
    nq = normtxt(q)
    return nq not in (normtxt(ev.get("name")), normtxt(ev.get("storm"))) and not re.fullmatch(
        r"(hurricane|typhoon|tropical (storm|cyclone|depression)|cyclone|super typhoon) [\w-]+( \(\w+\))?", nq)


def reg_domain(host):
    """Publisher = registered domain (cnnespanol.cnn.com -> cnn.com; timesofindia.indiatimes.com -> indiatimes.com)."""
    host = (host or "").lower().split("://")[-1].split("/")[0].split(":")[0]
    host = host[4:] if host.startswith("www.") else host
    p = host.split(".")
    if len(p) >= 3 and len(p[-1]) == 2 and p[-2] in ("co", "com", "org", "net", "gov", "ac", "edu", "gob", "go", "or", "ne"):
        return ".".join(p[-3:])
    return ".".join(p[-2:])


def publisher(item):
    if item["feed"] in ("gnews", "gdelt"):
        return reg_domain((item.get("extra") or {}).get("domain") or (item.get("extra") or {}).get("outlet") or item.get("url"))
    return reg_domain(item.get("url")) or AUTH_FEEDS.get(item["feed"], item["feed"])


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
    # independent sources = distinct PUBLISHERS (registered domain of the source URL; for Google-News redirect items the
    # outlet's own domain). EONET items that point at nhc.noaa.gov collapse into NHC; afro.who.int collapses into WHO.
    srcs, seen = [], set()
    for m in sorted(ev["members"], key=lambda m: m.get("published") or "", reverse=True):
        fam = AUTH_FEEDS.get(m["feed"], m["feed"]); pub = publisher(m)
        if fam in seen or pub in seen:
            continue
        seen.update({fam, pub}); x = _src(m, ev); x["publisher"] = pub; srcs.append(x)
    per_lang = {}
    for n in sorted(news, key=lambda n: n.get("published") or ""):
        pub = publisher(n)
        if pub in seen or per_lang.get(n["lang"], 0) >= 3:
            continue
        seen.add(pub); per_lang[n["lang"]] = per_lang.get(n["lang"], 0) + 1; x = _src(n, ev); x["publisher"] = pub; srcs.append(x)
    ev["all_items"] = {m["id"]: m for m in ev["members"] + news}
    ev["sources"] = srcs
    ev["languages_seen"] = sorted({s["lang"] for s in srcs})  # re-derived from VERIFIED sources in verify_sources()
    ts = [s["published"] for s in srcs if s.get("published")]
    ev["first_signal_ts"] = min(ts) if ts else None
    ev["independent"] = len({s["publisher"] for s in srcs})
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
    if not good_quote(q, ev):
        q = ""  # too short / just the event name -> no quote, source stays unverified
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
    ev["languages_seen"] = sorted({s["lang"] for s in ev["sources"] if s["verified"]}) or ["en"]
    tr.log("verifier", ev["event_id"], [s["id"] for s in ev["sources"]],
           {"checked": len(ev["sources"]), "verified": ok, "method": "normalized substring match against fetched source text"},
           f"Verifier: {ok}/{len(ev['sources'])} source quotes found verbatim in fetched text (code check, not LLM); "
           f"languages of verified sources: {', '.join(ev['languages_seen'])}",
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
        risk = re.search(r"risk (?:in|for|at) (?:the )?([A-Z][\w' -]{2,60}?|national level|regional level|global level) "
                         r"(?:was |is |remains )(?:again |still )?(?:assessed |considered )?as (very high|high|moderate|low)", who["text"])
        if risk:
            area = risk.group(1).replace("Democratic Republic of the Congo", "DR Congo")
            val = f"Risk {risk.group(2)} ({'national' if 'level' not in area else area.split()[0]}{'' if 'level' in area else ' — ' + area})"
        else:
            val = f"DON published {who['published'][:10]}"
        pts = 30 if risk and "high" in risk.group(2).lower() else 25
        sev = {"scale": "WHO_DON", "value": val, "ref": who["extra"].get("don"), "source_url": who["url"]}
        ev["who_risk_quote"] = risk.group(0) if risk else None
        bd.append({"factor": "authority severity", "points": pts, "reason": f"WHO Disease Outbreak News {sev['ref']}: {val}", "source_url": who["url"]})
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
        rad = {"OUTBREAK": 200, "FL": 150, "WF": 50, "VO": 30}.get(t, 150)
    track = [(ev["lat"], ev["lon"])] + [(p["lat"], p["lon"]) for p in (nhc["extra"]["track"] if nhc else [])]
    ev["track"] = track
    areas = []
    if t == "OUTBREAK":
        txt = " ".join(x.get("text", "") for x in ev["members"] if x["feed"] == "who_don")
        if who:
            txt = who.get("text", "")
        for c in ev["countries"]:
            for nm, (la, lo, pats) in PROVINCES.get(c, {}).items():
                if any(re.search(pt, txt) for pt in pats):
                    areas.append({"name": nm, "country": c, "lat": la, "lon": lo, "radius_km": 200})
        if areas:
            ev["lat"], ev["lon"] = sum(a["lat"] for a in areas) / len(areas), sum(a["lon"] for a in areas) / len(areas)
        else:
            rad = 0  # country-level screen
    ev["areas"] = areas
    # hurricane-force inner core (NHC advisory text) for TC exposure split
    core = None
    if t == "TC":
        mm = re.search(r"Hurricane-force winds extend outward up to (\d+) miles \((\d+) km\)", (nhc or {}).get("text", ""))
        if mm:
            core = {"radius_km": int(mm.group(2)), "basis": f"NHC advisory: hurricane-force winds extend up to {mm.group(1)} miles ({mm.group(2)} km)"}
        elif (nhc and nhc["extra"]["wind_mph"] >= 74) or (not nhc and gd and gd["issued_severity"]["value"] in ("Orange", "Red")):
            core = {"radius_km": 60, "basis": "assumed ~60 km hurricane-force core (radius not stated by authority)"}
    ev["core"] = core
    regions = []
    if nhc:
        regions.append({"nhc_at": "North Atlantic", "nhc_ep": "Eastern North Pacific", "nhc_cp": "Central North Pacific"}[nhc["feed"]])
        mh = re.findall(r"INTERESTS IN ([A-Z ]+?) SHOULD", nhc["text"])
        regions += [x.title() for x in mh]
    if us and us["extra"].get("place"):
        regions.append(us["extra"]["place"])
    if t == "OUTBREAK":
        regions += [f"{a['name']} ({a['country']})" for a in areas]
    geo_track = [[round(a, 2), round(b, 2)] for a, b in track] if (t == "TC" and len(track) > 1) else []
    ev["geo"] = {"lat": round(ev["lat"], 3), "lon": round(ev["lon"], 3), "countries": ev["countries"], "regions": regions, "radius_km": rad,
                 "radius_kind": "screening buffer" if t == "TC" else "affected-province screen" if areas else "country-level screen" if t == "OUTBREAK" else "screening radius",
                 "track": geo_track, "areas": areas,
                 "core_radius_km": core["radius_km"] if core else None}
    ev["time_horizon"] = {"TC": "24-72h (NHC 5-day track)" if nhc else "24-72h (GDACS/JTWC forecast)", "EQ": "0-72h (aftershocks, damage reports)", "OUTBREAK": "2-6 weeks",
                          "FL": "24-96h", "WF": "24-72h", "VO": "days-weeks"}.get(t, "24-72h")
    un = {"TC": ["Landfall location/timing beyond the " + ("NHC cone" if nhc else "GDACS/JTWC forecast track"), "Storm-surge and rainfall damage extent", "Insured vs economic loss split"],
          "EQ": ["PAGER loss estimate may be revised in first 24h", "Aftershock sequence", "Tsunami impact if any", "Building-stock damage ratios"],
          "OUTBREAK": ["True case count (under-reporting, testing capacity)", "Cross-border spread and travel restrictions", "Vaccine/therapeutic effectiveness for this strain"],
          }.get(t, ["Extent of damage area", "Duration", "Insured loss share"])
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
        reason = f"{lives:,} insured lives (Travel + A&H) in affected countries (synthetic book)"
    else:
        reason = (f"{ev['exposure']['policies']} sites, {money(tiv)} TIV within {ev['geo']['radius_km']} km "
                  f"{'screening buffer' if ev['type'] == 'TC' else 'radius'} (synthetic book)")
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
           f"confidence {ev['confidence']}; {ev['geo'].get('radius_kind', 'radius')} {ev['geo']['radius_km']} km",
           model, (time.time() - t0) * 1000)


# ======================================================================= 5. EXPOSURE
def exposure(ev, book, tr):
    t0 = time.time(); locs, trav = book; rad = ev["geo"]["radius_km"]; t = ev["type"]
    hits, core_hits = [], []
    if t == "OUTBREAK":
        cs = set(ev["countries"]); areas = ev.get("areas") or []
        if areas:
            for l in locs:
                d = min(hav(l["lat"], l["lon"], x["lat"], x["lon"]) for x in areas)
                if d <= 200:
                    hits.append((l, d))
            method = (f"SYNTHETIC demo book (seeded generator, not real policies): property sites within ~200 km of the centroids of "
                      f"provinces named in the WHO DON ({', '.join(x['name'] for x in areas)}); insured lives (Travel + A&H) from "
                      f"data/travelers.csv for {', '.join(sorted(cs))} (country-level)")
        else:
            hits = [(l, hav(l["lat"], l["lon"], ev["lat"], ev["lon"])) for l in locs if l["country"] in cs]
            method = (f"SYNTHETIC demo book (seeded generator, not real policies): country-level screen of {sorted(cs)} (no province named "
                      f"in WHO text); insured lives (Travel + A&H) from data/travelers.csv")
    else:
        pts = densify(ev["track"]) if len(ev["track"]) > 1 else ev["track"]
        core = ev.get("core")
        for l in locs:
            if abs(l["lat"] - ev["lat"]) > 25:
                continue
            d = min(hav(l["lat"], l["lon"], a, b) for a, b in pts)
            if d <= rad:
                hits.append((l, d))
                if core and d <= core["radius_km"]:
                    core_hits.append((l, d))
        if t == "TC":
            src = "NHC current position + forecast track" if len(ev["track"]) > 1 else "current GDACS/JTWC position (no forecast track parsed)"
            method = (f"SYNTHETIC demo book (seeded generator, not real policies): property sites within a {rad} km screening buffer of the "
                      f"{src} polyline (haversine); inner core = sites within the hurricane-force wind radius; TIV = property damage + BI")
        else:
            method = (f"SYNTHETIC demo book (seeded generator, not real policies): property sites within {rad} km of the event point "
                      f"(haversine); TIV = property damage + BI")
    by = {}
    for l, d in hits:
        b = by.setdefault(l["line"], {"line": l["line"], "policies": 0, "tiv_usd": 0}); b["policies"] += 1; b["tiv_usd"] += l["tiv_usd"]
    bi = [(l, d) for l, d in hits if l.get("bi_tiv_usd")]
    by_line = sorted(by.values(), key=lambda b: -b["tiv_usd"])
    if bi:
        by_line.append({"line": "Commercial Property — BI (time element)", "policies": len(bi), "tiv_usd": sum(l["bi_tiv_usd"] for l, _ in bi)})
    tiv = lambda hs: sum(l["tiv_usd"] + l.get("bi_tiv_usd", 0) for l, _ in hs)
    top = sorted(hits, key=lambda x: -x[0]["tiv_usd"])[:5]
    countries_hit = sorted({l["country"] for l, _ in hits})
    # insured LIVES (Travel + A&H): outbreaks -> whole affected countries; nat-cat -> country lives pro-rated by the share of
    # that country's book sites inside the screening buffer (proxy for lives in the affected area)
    trv = ah = 0
    if t == "OUTBREAK":
        for c in ev["countries"]:
            x = trav.get(c, (0, 0)); trv += x[0]; ah += x[1]
    else:
        for c in countries_hit:
            n_c = sum(1 for l in locs if l["country"] == c) or 1; share = sum(1 for l, _ in hits if l["country"] == c) / n_c
            x = trav.get(c, (0, 0)); trv += int(x[0] * share); ah += int(x[1] * share)
    if trv:
        by_line.append({"line": "Travel", "lives": trv})
    if ah:
        by_line.append({"line": "Accident & Health", "lives": ah})
    ev["exposure"] = {"policies": len(hits), "tiv_usd": tiv(hits), "pd_tiv_usd": sum(l["tiv_usd"] for l, _ in hits),
                      "bi_tiv_usd": sum(l["bi_tiv_usd"] for l, _ in bi),
                      "by_line": by_line,
                      "top_locations": [{"name": l["name"], "lat": l["lat"], "lon": l["lon"], "tiv_usd": l["tiv_usd"] + l.get("bi_tiv_usd", 0),
                                         "distance_km": round(d), "line": l["line"]} for l, d in top],
                      "insured_travelers": trv + ah, "insured_lives": {"travel": trv, "ah": ah, "total": trv + ah},
                      "screen": ev["geo"].get("radius_kind"), "method": method}
    if ev.get("core"):
        ev["exposure"]["inner_core"] = {"policies": len(core_hits), "tiv_usd": tiv(core_hits),
                                        "radius_km": ev["core"]["radius_km"], "basis": ev["core"]["basis"]}
    if not ev["countries"] and countries_hit:
        ev["countries"] += countries_hit; ev["geo"]["countries"] = ev["countries"]
    e = ev["exposure"]
    tr.log("exposure", ev["event_id"], ["portfolio://synthetic"], e,
           f"Exposure: {e['policies']} insured sites, {money(e['tiv_usd'])} TIV in {e['screen']}"
           + (f"; {e['inner_core']['policies']} sites / {money(e['inner_core']['tiv_usd'])} in ~{e['inner_core']['radius_km']} km core" if e.get("inner_core") else "")
           + (f"; {e['insured_travelers']:,} insured lives (Travel+A&H)" if e["insured_travelers"] else "") + " (synthetic book)",
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


ACCUM = {"ELEVATED": "ELEVATED — consider binding restrictions / moratorium for new business in the watch area; run accumulation check",
         "MONITOR": "MONITOR — run accumulation check against the screening area; no binding restriction yet",
         "NONE": "NONE — no insured exposure in the screening area"}


def posture_accum(ev):
    """Reserving posture follows occurrence: forecast hazards (TCs pre-landfall) are 'watch' — nobody strengthens reserves
    before landfall. 'strengthen' only for events that HAVE occurred with exposure (EQ PAGER orange/red; ongoing FL/WF)."""
    t, tier, e = ev["type"], ev["tier"], ev["exposure"]
    has = e["tiv_usd"] > 0 or (t == "OUTBREAK" and e["insured_travelers"] > 0)
    pager = str(ev["issued_severity"].get("value", "")).lower()
    if t == "EQ" and has and ("orange" in pager or "red" in pager):
        posture = "strengthen"
    elif t in ("FL", "WF") and has and not ev.get("stale") and tier != "WATCH":
        posture = "strengthen"
    elif t == "TC" or has or tier != "WATCH":
        posture = "watch"
    else:
        posture = "no action"
    if not has:
        accum = ACCUM["NONE"]
    elif tier == "RED":
        accum = ACCUM["ELEVATED"]
    else:
        accum = ACCUM["MONITOR"]
    if t == "OUTBREAK" and has:
        accum = ("ELEVATED — consider restricting new Travel/A&H business to affected provinces; review assistance & evacuation capacity"
                 if tier == "RED" else "MONITOR — track Travel/A&H bookings to affected provinces; no binding restriction yet")
    return posture, accum


def ins_headline(ev, accum):
    e, t = ev["exposure"], ev["type"]; lvl = accum.split(" — ")[0]
    if t == "OUTBREAK":
        lv = e["insured_lives"]
        return (f"{ev['name']}: {lv['total']:,} insured lives ({lv['travel']:,} Travel + {lv['ah']:,} A&H) in affected area — "
                f"accumulation {lvl}; property TIV {money(e['tiv_usd'])} (contingent BI only)")
    if t == "TC":
        core = e.get("inner_core")
        return (f"{ev['name']}: {e['policies']} sites / {money(e['tiv_usd'])} within {ev['geo']['radius_km']} km screening buffer"
                + (f"; {core['policies']} / {money(core['tiv_usd'])} in ~{core['radius_km']} km hurricane-force core" if core else "")
                + f" — accumulation {lvl}")
    return f"{ev['name']}: {e['policies']} sites / {money(e['tiv_usd'])} TIV within {ev['geo']['radius_km']} km — accumulation {lvl}"


def det_briefs(ev):
    t = ev["type"]; mem = ev["members"]
    nhc = next((x for x in mem if x["feed"].startswith("nhc")), None)
    gd = next((x for x in mem if x["feed"] == "gdacs"), None)
    us = next((x for x in mem if x["feed"] == "usgs"), None)
    who = max((x for x in mem if x["feed"] == "who_don"), key=lambda x: x["published"], default=None)
    ecdc = next((x for x in mem if x["feed"] == "ecdc"), None)
    eo = next((x for x in mem if x["feed"] == "eonet"), None)
    e = ev["exposure"]; tier = ev["tier"]; place = ", ".join(ev["countries"][:3]) or "no named country (at sea)"
    lines = {b["line"]: b for b in e["by_line"]}
    def L(n):
        b = lines.get(n); return f"{b['policies']} policies / {money(b['tiv_usd'])}" if b else "none"
    H, W, I = [], [], []
    posture, accum = posture_accum(ev)
    core = e.get("inner_core"); buf = ev["geo"]["radius_km"]
    track_src = "NHC forecast track" if (nhc and len(ev["track"]) > 1) else "GDACS/JTWC position"
    if t == "TC":
        a = nhc or gd or eo
        H += [_B("Authority wind intensity defines the life-safety zone; expect trauma and displacement near the core.", a, ["maximum sustained winds", "wind speed", "kts"], show=True),
              _B("Heavy rain / flash-flood hazard raises waterborne-disease and access-to-care risk.", nhc, ["rainfall", "flash flooding", "flooding"], show=True),
              _B("Storm surge / surf hazard (NHC)", nhc, ["storm surge will", "life-threatening storm surge", "life-threatening surf", "swells are likely", "dangerous storm surge"], show=True),
              _B("GDACS population exposure estimate for the wind field.", gd, ["Population affected", "population"], show=True)]
        H += _news_bullets(ev, 2, "Local-language press flags community impact")
        W += [_B(f"Regional market read-through for {place}: tourism, ports and infrastructure in the path; watch local equities/FX and sub-sovereign credit.", a, ["CATEGORY", "affects these countries", "Hurricane", "Tropical"]),
              _B("Track and forward speed set the window for supply-chain disruption (ports, shipping lanes).", nhc, ["movement", "moving"])]
        W += _news_bullets(ev, 2, "Market-moving coverage")
        I += [_B(f"Authority severity {ev['issued_severity']['value']} ({sname(ev['issued_severity']['scale'])}) — Property/HNW Homeowners claims direction: UP if the core nears insured coast.", a, ["CATEGORY", "maximum sustained winds", "wind speed"]),
              _P(f"Synthetic book: {e['policies']} sites / {money(e['tiv_usd'])} TIV within {buf} km screening buffer of the {track_src}"
                 + (f"; {core['policies']} sites / {money(core['tiv_usd'])} within ~{core['radius_km']} km hurricane-force core" if core else "") + "."),
              _P(f"By line — Commercial Property {L('Commercial Property')} (incl. BI time element {money(e['bi_tiv_usd'])}); HNW Homeowners {L('High-Net-Worth Homeowners')}; Marine Cargo {L('Marine Cargo')}; Energy {L('Energy')}."
                 + (f" Insured lives in area (pro-rated): {e['insured_travelers']:,} Travel/A&H." if e["insured_travelers"] else "")),
              _P(f"Accumulation action: {accum}. Reserving posture: {posture} (pre-landfall — reserves are not strengthened before the event occurs)."),
              _B("Watches/warnings define claims-notification timing; pre-position adjusters and CAT team.", nhc, ["Warning is in effect", "Watch is in effect", "should monitor", "SHOULD MONITOR", "warning"]),
              _B("Check cat XoL retention erosion and ILW/parametric cat-bond trigger boxes against the forecast track.", nhc or gd, ["located near", "center of", "Tropical Storm"])]
    elif t == "EQ":
        a = us or gd
        H += [_B("Shaking intensity/population exposure drives casualty and hospital-surge risk.", gd, ["MMI", "potentially affecting"], show=True),
              _B("USGS PAGER alert level indicates the expected fatality/loss band.", us, ["PAGER alert"], show=True),
              _B("USGS tsunami flag for coastal health planning.", us, ["tsunami="]),
              _B("Felt reports indicate population experiencing shaking.", us, ["felt reports"])] + _news_bullets(ev, 2, "Local-language press")
        W += [_B(f"Infrastructure, ports, mining and manufacturing in {place} may see short-term disruption.", a, ["mag=", "Magnitude", "earthquake"])] + _news_bullets(ev, 2, "Coverage")
        I += [_B(f"Authority severity {ev['issued_severity']['value']} — commercial property & BI claims direction depends on proximity to insured sites.", a, ["PAGER alert", "Magnitude"]),
              _P(f"Synthetic book within {ev['geo']['radius_km']} km of epicentre: {e['policies']} sites, {money(e['tiv_usd'])} TIV."),
              _P(f"By line — Commercial Property {L('Commercial Property')} (incl. BI time element {money(e['bi_tiv_usd'])}); Energy {L('Energy')}."),
              _P(f"Accumulation action: {accum}. Reserving posture: {posture}."),
              _B("EQ sub-limits/deductibles typically absorb moderate events; confirm aftershock hours clause.", us or gd, ["depth_km", "Depth"])]
    elif t == "OUTBREAK":
        H += [_B("WHO case/death count", who, ["confirmed cases", "deaths", "cases"], show=True),
              _B("Spread across health zones signals health-system strain", who, ["health zones", "provinces", "spread"], show=True),
              _B("WHO on onward-spread risk", who, ["assesses the risk", "risk is", "risk of further spread", "risk"], show=True),
              _B("ECDC situational reporting relevant to EU travellers.", ecdc, ["Ebola", ev.get("disease_kw", "")] if ecdc else [])]
        H += _news_bullets(ev, 2, "Multilingual press")
        W += [_B(f"Regional economies ({place}): mining, logistics and cross-border trade face disruption risk from containment measures.", who, ["transmission", "outbreak", "spread"]),
              _B("Travel and aviation demand to affected areas likely to soften; watch airlines/hospitality exposure.", who, ["travel", "border", "international"])]
        W += _news_bullets(ev, 1, "Coverage")
        lv = e["insured_lives"]; areas = ev.get("areas") or []
        I += [_B(f"Authority: WHO {ev['issued_severity']['value']} — A&H and Travel medical/evacuation claims direction: UP.", who, ["was assessed as very high", "assessed as", "confirmed cases", "cases"]),
              _P(f"Insured lives: {lv['total']:,} ({lv['travel']:,} Travel + {lv['ah']:,} A&H members) in {place} (synthetic book)."),
              _P(f"Property screen ({'~200 km of ' + ', '.join(a['name'] for a in areas) if areas else 'country-level screen'}): {e['policies']} sites / {money(e['tiv_usd'])} TIV — "
                 "physical damage not expected; relevant only for contingent BI / supply-chain."),
              _P(f"Accumulation action: {accum}. Reserving posture: {posture}."),
              _B("Review contingent BI (CBI) and event-cancellation communicable-disease exclusions; marine cargo port-delay exposure.", who, ["spread", "health zones", "provinces", "transmission"])]
    else:
        a = gd or eo or mem[0]
        H += [_B("Authority alert describes the affected area and displacement.", a, ["displaced", "deaths", "affect", "started"], show=True)] + _news_bullets(ev, 1)
        W += [_B(f"Local infrastructure and agriculture in {place} may be disrupted.", a, ["alert", "started", "affect"])] + _news_bullets(ev, 1, "Coverage")
        I += [_B(f"Authority alert ({ev['issued_severity']['value']}) — property/BI claims direction depends on insured presence.", a, ["alert", "started", "affect"]),
              _P(f"Synthetic book within {ev['geo']['radius_km']} km: {e['policies']} sites, {money(e['tiv_usd'])} TIV."),
              _P(f"Accumulation action: {accum}. Reserving posture: {posture}.")]
    hazard = {"TC": "tropical cyclone", "EQ": "earthquake", "OUTBREAK": "outbreak"}.get(t, "hazard")
    cav = ["Exposure figures use a SYNTHETIC demo book, not real policies.", "Severity is copied from the issuing authority; Sentinel does not forecast intensity."]
    return {
        "health": {"headline": f"{ev['name']}: health impact watch ({tier})", "bullets": H, "caveats": cav[1:]},
        "wealth": {"headline": f"{ev['name']}: market/sector read-through for {place}", "bullets": W, "caveats": ["Not investment advice; directional only."]},
        "insurance": {"headline": ins_headline(ev, accum),
                      "bullets": I, "caveats": cav, "reserving_posture": posture, "accumulation_action": accum},
    }


BRIEF_ROLE = {
    "health": "Health brief writer (chief medical officer lens): exposed population, health-system strain, case trajectory.",
    "wealth": "Wealth brief writer (CIO lens): sectors, asset classes, regional markets likely affected; caveated, not advice.",
    "insurance": "Insurance brief writer (underwriter lens): lines of business (commercial property incl. BI time element, HNW homeowners, marine cargo, energy; A&H and travel are insured LIVES not TIV), claims-exposure direction, accumulation/binding actions, reinsurance/cat-bond/ILW notes. Never recommend strengthening reserves for a forecast (pre-landfall) hazard. Say 'screening buffer', never 'footprint'.",
}


def briefs(ev, tr):
    det = det_briefs(ev)
    out = {}
    for k in ("health", "wealth", "insurance"):
        t0 = time.time(); model = "deterministic"; b = det[k]
        if llm_on():
            facts = {"event": ev["name"], "type": ev["type"], "tier": ev["tier"], "issued_severity": ev["issued_severity"],
                     "exposure": {x: ev["exposure"].get(x) for x in ("policies", "tiv_usd", "by_line", "insured_lives", "inner_core", "screen", "method")},
                     "sources": [{"url": s["url"], "title": s["title"], "lang": s["lang"],
                                  "text": (ev["all_items"].get(s["id"]) or {}).get("text", "")[:2500]} for s in ev["sources"][:8]],
                     "portfolio_lines": [x["quote"] for x in det[k]["bullets"] if x and x["source_url"] == "portfolio://synthetic"]}
            j, model = llm_json(f"You are the {BRIEF_ROLE[k]} Write 3-6 bullets. EVERY bullet must cite source_url from the sources list and a "
                                "'quote' copied VERBATIM (exact substring, <=250 chars) from that source's text or title; portfolio lines may be "
                                "cited with source_url 'portfolio://synthetic' and the line itself as quote. Never invent severity numbers. "
                                'Output {"headline":...,"bullets":[{"text":...,"source_url":...,"quote":...}],"caveats":[...]'
                                + "}", facts, 1500)
            if j and isinstance(j.get("bullets"), list):
                cand = [{"text": str(x.get("text", ""))[:400], "source_url": x.get("source_url"), "quote": x.get("quote")} for x in j["bullets"]]
                cand = [c for c in cand if c["source_url"] != "portfolio://synthetic" or c["quote"] in facts["portfolio_lines"]]
                good, _ = verify_bullets(ev, cand)
                if len(good) >= 2:
                    b = {"headline": str(j.get("headline") or b["headline"])[:160], "bullets": cand,
                         "caveats": (j.get("caveats") or [])[:3] + ["Exposure figures use a SYNTHETIC demo book."]}
                    if k == "insurance":  # posture/accumulation/headline are rule-based, never LLM-chosen
                        b["reserving_posture"] = det[k]["reserving_posture"]
                        b["accumulation_action"] = det[k]["accumulation_action"]
                        b["headline"] = det[k]["headline"]
                        acc = [x for x in det[k]["bullets"] if x and x["quote"].startswith("Accumulation action")]
                        b["bullets"] = acc + [c for c in cand if not re.search(r"strengthen", c["text"] or "", re.I)]
                else:
                    model = "deterministic (llm fallback: <2 verified bullets)"
        raw = [x for x in b["bullets"] if x]
        for x in raw:
            x["text"] = re.sub(r"\bfootprint\b", "screening buffer" if ev["type"] == "TC" else "screening area", x["text"] or "")
        b["headline"] = re.sub(r"\bfootprint\b", "screening buffer", b["headline"])
        b["bullets"], dropped = verify_bullets(ev, raw)
        out[k] = b
        tr.log(f"brief_{k}", ev["event_id"], [x["source_url"] for x in b["bullets"]], b,
               f"Brief {k}: {len(b['bullets'])} cited bullets ({dropped} dropped by verifier)"
               + (f"; posture {b['reserving_posture']}; accumulation {b['accumulation_action'].split(' — ')[0]}" if k == "insurance" else "") + f" — {b['headline'][:70]}",
               model, (time.time() - t0) * 1000)
    return out


# ======================================================================= 7. ROUTER
PERSONAS = [("CUO Property", "insurance", "email"), ("Head of Claims", "insurance", "slack"),
            ("Cat Modeling/Accumulation desk", "insurance", "slack"), ("CIO", "wealth", "email"),
            ("Head of A&H/Travel", "health", "sms"), ("Public", "health", "public")]


def route(ev, tr):
    """Routing rules (per CUO review): Public only for RED; CIO only with exposure (TIV or lives) at RED/AMBER; A&H/Travel by
    insured lives (outbreak >=1,000 lives -> P1 SMS+email; nat-cat lives>0 -> P2); nat-cat desks silent on $0-exposure
    storms except the Cat desk at P3 'monitor'."""
    t0 = time.time(); tier, t, e = ev["tier"], ev["type"], ev["exposure"]
    pr = {"RED": "P1", "AMBER": "P2", "WATCH": "P3"}[tier]
    natcat = t != "OUTBREAK"
    ins = ev["briefs"]["insurance"]; accum = ins.get("accumulation_action", ""); lvl = accum.split(" — ")[0]
    lives = e["insured_travelers"]; tiv = e["tiv_usd"]
    cav = f"Early-warning signal ({ev['confidence']} confidence); severity per {sname(ev['issued_severity']['scale'])}; exposure from a synthetic demo book."
    top = e["top_locations"][0]["name"] if e["top_locations"] else "none"
    sev = f"{sname(ev['issued_severity']['scale'])} {ev['issued_severity']['value']}"
    area = f"{ev['geo']['radius_km']} km screening buffer" if t == "TC" else (ev["geo"].get("radius_kind") or "screening area")
    core = e.get("inner_core")
    core_txt = f"; {core['policies']} sites / {money(core['tiv_usd'])} in ~{core['radius_km']} km hurricane-force core" if core else ""
    where = ", ".join(ev["countries"][:3])
    R = []  # (persona, brief, channel, priority, message)
    if natcat:
        if tiv > 0:
            if tier in ("RED", "AMBER"):
                R.append(("CUO Property", "insurance", "email", pr,
                          f"[{tier} {pr}] {ev['name']}: {sev}. {e['policies']} sites / {money(tiv)} TIV within {area}{core_txt}. Accumulation {lvl}"
                          + (": consider binding restrictions/moratorium on new business in the watch area" if lvl == "ELEVATED" else ": run accumulation check")
                          + f". Reserving: {ins['reserving_posture']}. Largest: {top}."))
            if e["policies"] > 0 and tier != "WATCH":
                R.append(("Head of Claims", "insurance", "slack", pr,
                          f"[{tier} {pr}] {ev['name']}: {e['policies']} insured sites in {area} ({money(tiv)} TIV){core_txt}. Pre-position adjusters; FNOL surge possible within {ev['time_horizon']}."))
            R.append(("Cat Modeling/Accumulation desk", "insurance", "slack", pr,
                      f"[{tier} {pr}] {ev['name']} ({sev}). Accumulation {lvl}: {money(tiv)} TIV within {area}{core_txt}. Run accumulation check vs zones; check XoL retention and ILW/cat-bond triggers."))
        else:
            R.append(("Cat Modeling/Accumulation desk", "insurance", "slack", "P3",
                      f"[{tier} P3 monitor] {ev['name']} ({sev}). No insured sites in the {area} this cycle; keep monitoring the forecast for track shifts toward insured coast."))
    if (tiv > 0 or lives > 0) and tier in ("RED", "AMBER"):
        R.append(("CIO", "wealth", "email", pr,
                  f"[{tier} {pr}] {ev['name']} ({sev}){' in ' + where if where else ''}. Book exposure: {money(tiv)} TIV, {lives:,} insured lives. Review regional equity/credit and insurer-sector read-through. Directional only."))
    if t == "OUTBREAK" and lives > 0:
        p = "P1" if lives >= 1000 else "P2"
        msg = (f"[{tier} {p}] {ev['name']}: {lives:,} insured lives ({e['insured_lives']['travel']:,} Travel + {e['insured_lives']['ah']:,} A&H) in affected area. "
               f"Accumulation {lvl}: {accum.split(' — ')[-1]}. Confirm evacuation triggers and travel advisories.")
        R += [("Head of A&H/Travel", "health", "sms", p, msg), ("Head of A&H/Travel", "health", "email", p, msg)] if p == "P1" else [("Head of A&H/Travel", "health", "email", p, msg)]
    elif natcat and lives > 0:
        R.append(("Head of A&H/Travel", "health", "email", "P2",
                  f"[{tier} P2] {ev['name']}: ~{lives:,} insured Travel/A&H lives in the {area} (pro-rated, synthetic). Check assistance capacity and evacuation readiness."))
    if tier == "RED" and ev["status"] == "alert":
        R.append(("Public", "health", "public", pr, f"{ev['name']}: official status {sev}. Follow local authority guidance. (Automated early-warning summary; may change.)"))
    model = "deterministic"
    if llm_on() and R:
        j, model = llm_json("You are the Router agent. Rewrite each numbered notification to be crisp and actionable (<=400 chars). Keep all numbers "
                            "exactly; add none. Keep the accumulation level word (ELEVATED/MONITOR/NONE) if present. Never write 'footprint', "
                            "'strengthen' or 'open ocean'. " 'Output {"messages":{"<index>":"text"}}',
                            {"event": ev["name"], "tier": tier, "messages": {str(i): r[4] for i, r in enumerate(R)}}, 900)
        if j:
            for k2, m in (j.get("messages") or {}).items():
                if k2.isdigit() and int(k2) < len(R) and isinstance(m, str) and len(m) <= 400 and numbers_ok(m, R[int(k2)][4]) \
                        and not re.search(r"footprint|strengthen|open ocean", m, re.I) and (lvl not in R[int(k2)][4] or lvl in m):
                    x = R[int(k2)]; R[int(k2)] = (x[0], x[1], x[2], x[3], m)
    routing = [{"persona": p, "brief": b, "channel": c, "priority": q, "caveat_banner": cav, "message": m[:400]} for p, b, c, q, m in R]
    ev["routing"] = routing
    tr.log("router", ev["event_id"], [ev["event_id"]], {"routing": routing},
           f"Router: {tier} → " + (", ".join(f"{r['persona']} {r['priority']}/{r['channel']}" for r in routing) or "no persona (below threshold)"),
           model, (time.time() - t0) * 1000)
    return routing
