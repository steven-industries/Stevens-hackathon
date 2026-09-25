"""Backtest replay: feed archived, timestamped items through Sentinel's corroboration rule.

Usage (from sentinel/):
    python3 src/backtest.py                       # default event, writes log/ + ui/data/backtest.json
    python3 src/backtest.py --strict              # ignore authority items whose ts is derived from another item
    python3 src/backtest.py --input data/backtest_<event>.json [--no-write]

Rule (same as the live Corroborator): the alert fires at the first non-mainstream item after which
  >= 2 distinct outlets have reported  AND  (an authority item is present  OR  >= 2 languages are present).
Mainstream items never count toward the alert; they only define "T" (first mainstream headline).
Standard library only.
"""
import argparse
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INPUT = os.path.join(ROOT, "data", "backtest_foshan_chikungunya_2025.json")
OUTPUTS = [os.path.join(ROOT, "log", "backtest.json"), os.path.join(ROOT, "ui", "data", "backtest.json")]
CONTRACT_KEYS = ("ts", "kind", "source", "lang", "title", "url", "note")


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hours(a, b):
    return round((b - a).total_seconds() / 3600.0, 1)


def replay(items, strict=False):
    """Return (alert_dt, trigger_item, evidence_outlets, languages) or (None, ...) if the rule never fires."""
    outlets, langs, has_authority = [], set(), False
    for it in sorted(items, key=lambda x: parse_ts(x["ts"])):
        if it["kind"] == "mainstream":
            continue
        if strict and it["kind"] == "authority" and it.get("ts_quality") == "derived_upper_bound":
            continue
        if it["outlet"] not in outlets:
            outlets.append(it["outlet"])
        langs.add(it["lang"].split("-")[0])
        has_authority = has_authority or it["kind"] == "authority"
        if len(outlets) >= 2 and (has_authority or len(langs) >= 2):
            return parse_ts(it["ts"]), it, list(outlets), sorted(langs)
    return None, None, outlets, sorted(langs)


def run(path, strict=False, write=True):
    spec = json.load(open(path, encoding="utf-8"))
    items = spec["items"]
    mainstream = sorted((parse_ts(i["ts"]) for i in items if i["kind"] == "mainstream"))
    signals = [i for i in items if i["kind"] in ("weak_signal", "authority")]
    if strict:
        signals = [i for i in signals if i.get("ts_quality") != "derived_upper_bound"]
    if not mainstream or not signals:
        raise SystemExit("need at least one mainstream item and one signal item")
    t0 = mainstream[0]
    first_signal = min(parse_ts(i["ts"]) for i in signals)
    alert_dt, trigger, outlets, langs = replay(items, strict)
    if alert_dt is None:
        raise SystemExit("corroboration rule never fired before mainstream coverage")

    lead = hours(alert_dt, t0)
    line = (f"First weak signal T−{hours(first_signal, t0)} h · "
            f"Sentinel alert T−{lead} h · Mainstream headline T ({iso(t0)})")

    alert_entry = {
        "ts": iso(alert_dt), "kind": "sentinel_alert", "source": "Sentinel corroborator (backtest replay)",
        "lang": "multi" if len(langs) > 1 else langs[0], "title": f"ALERT: {spec['event']}",
        "url": trigger["url"],
        "note": (f"Rule fired on '{trigger['source']}': {len(outlets)} distinct outlets ({', '.join(outlets)}), "
                 f"languages {langs}, authority={'yes' if any(i['kind']=='authority' for i in signals if parse_ts(i['ts'])<=alert_dt) else 'no'}"
                 + (" [strict mode]" if strict else "")),
    }
    timeline = [{k: i[k] for k in CONTRACT_KEYS} for i in items]
    if strict:
        timeline = [t for t, i in zip(timeline, items) if i.get("ts_quality") != "derived_upper_bound"]
    timeline.append(alert_entry)
    order = {"authority": 0, "weak_signal": 1, "sentinel_alert": 2, "mainstream": 3}
    timeline.sort(key=lambda t: (parse_ts(t["ts"]), order[t["kind"]]))

    wire = [m for m in mainstream if m > t0]
    summary = (f"{line}. Sentinel would have alerted {lead} h before the first English mainstream headline"
               + (f" and {hours(alert_dt, wire[0])} h (~{round(hours(alert_dt, wire[0]) / 24)} days) before the first global newswire"
                  if wire else "") + ".")
    out = {"event": spec["event"], "summary": summary, "lead_time_hours": lead, "timeline": timeline,
           "method": spec["method"], "caveats": spec["caveats"]}
    print(line)
    if write:
        for p in OUTPUTS:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print("wrote", os.path.relpath(p, ROOT))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--strict", action="store_true", help="drop authority items whose timestamp is derived from another item")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    run(a.input, strict=a.strict, write=not a.no_write)
