"""Orchestrator: python -m src.run --once | --loop 300 | --offline
Writes log/alerts.json, log/events.jsonl, log/runs.jsonl, log/outbox/*.md and mirrors them into ui/data/."""
import datetime as dt, json, os, pathlib, shutil, sys, time, uuid
from concurrent.futures import ThreadPoolExecutor
import httpx
from . import agents, feeds

LOG = pathlib.Path("log"); LOG.mkdir(exist_ok=True)
UI = pathlib.Path("ui/data")
TIER_RANK = {"WATCH": 0, "AMBER": 1, "RED": 2}


def notifier(alerts, tr):
    t0 = time.time(); sp = LOG / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() else {}
    out = LOG / "outbox"; out.mkdir(exist_ok=True)
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    for a in alerts:
        prev = state.get(a["event_id"], {}).get("tier")
        if prev == a["tier"] or (prev and TIER_RANK[a["tier"]] < TIER_RANK[prev]):
            tr.log("notifier", a["event_id"], [], {"action": "suppressed", "tier": a["tier"], "previously": prev},
                   f"Notifier: {a['tier']} already notified (dedup) — no re-send")
            continue
        action = "escalated" if prev else "new"
        files, slack = [], 0
        for r in a["routing"]:
            p = out / f"{a['event_id']}__{r['persona'].replace('/', '-').replace(' ', '_').replace('&', 'and')}.md"
            p.write_text(f"# [{r['priority']}] {a['name']} — {a['tier']} ({action})\n\nTo: {r['persona']} via {r['channel']}\n\n"
                         f"> {r['caveat_banner']}\n\n{r['message']}\n\nBrief: {r['brief']} · risk {a['risk_score']}/100 · alert_ts {a['alert_ts']}\n")
            files.append(p.name)
            if hook and r["priority"] == "P1" and a["tier"] in ("RED", "AMBER") and r["channel"] != "public":
                try:
                    httpx.post(hook, json={"text": f"*{r['persona']}* — {r['message']}\n_{r['caveat_banner']}_"}, timeout=5); slack += 1
                except Exception:
                    pass
        state[a["event_id"]] = {"tier": a["tier"], "ts": a["alert_ts"]}
        tr.log("notifier", a["event_id"], files, {"action": action, "files": files, "slack_posts": slack, "previously": prev},
               f"Notifier: {action}{' from ' + prev if prev else ''} {a['tier']} → {len(files)} outbox notes"
               + (f", {slack} Slack posts" if slack else ""))
    sp.write_text(json.dumps(state, indent=1))


def process(ev, book, tr, offline, ts):
    agents.corroborate(ev, tr, offline)
    agents.verify_sources(ev, tr)
    model, t0 = agents.assess(ev, tr)
    agents.exposure(ev, book, tr)
    agents.finish_assess(ev, tr, model, t0)
    ev["briefs"] = agents.briefs(ev, tr)
    agents.route(ev, tr)
    return {"event_id": ev["event_id"], "name": ev["name"], "type": ev["type"], "status": ev["status"], "tier": ev["tier"],
            "risk_score": ev["risk_score"], "score_breakdown": ev["breakdown"], "issued_severity": ev["issued_severity"],
            "confidence": ev["confidence"], "confidence_rationale": ev["confidence_rationale"], "geo": ev["geo"],
            "time_horizon": ev["time_horizon"], "first_signal_ts": ev["first_signal_ts"], "alert_ts": ts,
            "languages_seen": ev["languages_seen"], "sources": ev["sources"], "exposure": ev["exposure"],
            "briefs": ev["briefs"], "unknowns": ev["unknowns"], "routing": ev["routing"]}


def mirror():
    UI.mkdir(parents=True, exist_ok=True)
    for n in ("alerts.json", "runs.jsonl", "backtest.json"):
        if (LOG / n).exists():
            shutil.copy(LOG / n, UI / n)
    if (LOG / "events.jsonl").exists():
        lines = (LOG / "events.jsonl").read_text().splitlines()[-400:]
        (UI / "events.jsonl").write_text("\n".join(lines) + "\n")


def cycle(offline=False, max_events=8):
    t_start = time.time(); run_id = uuid.uuid4().hex[:8]; ts = feeds.now_iso()
    agents._FAILS["n"] = 0; agents.USED.clear()
    mode = "claude" if agents.llm_on() else "deterministic"
    tr = agents.Tracer(LOG / "events.jsonl", run_id)
    print(f"[{ts}] run {run_id} ({mode}{', offline' if offline else ''})")
    t0 = time.time()
    items, fstat = feeds.fetch_all(offline)
    tr.log("fetch", None, [f["name"] for f in fstat], {"feeds": fstat, "items": len(items)},
           f"Fetch: {len(items)} items from {sum(f['status'] == 'live' for f in fstat)}/{len(fstat)} live feeds — "
           + ", ".join(f"{f['name']} {f['items']}{'' if f['status'] == 'live' else ' (' + f['status'] + ')'}" for f in fstat),
           "deterministic", (time.time() - t0) * 1000)
    events = agents.scout(items, tr, max_events)
    book = agents.load_book()
    with ThreadPoolExecutor(max_workers=4 if mode == "claude" else 8) as ex:
        futs = [ex.submit(process, ev, book, tr, offline, ts) for ev in events]
        alerts = []
        for f, ev in zip(futs, events):
            try:
                alerts.append(f.result())
            except Exception as e:
                import traceback; traceback.print_exc()
                print("  event failed:", ev["event_id"], e)
    alerts.sort(key=lambda a: -a["risk_score"])
    notifier(alerts, tr)
    if mode == "claude" and not any(m.startswith("claude") for m in tr.models):
        mode = "deterministic"  # key present but every LLM call fell back
    doc = {"generated_at": feeds.now_iso(), "run_id": run_id, "mode": mode, "feeds": fstat, "alerts": alerts}
    (LOG / "alerts.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False))
    run = {"ts": ts, "run_id": run_id, "items_fetched": len(items), "feeds_ok": sum(f["status"] == "live" for f in fstat),
           "events": len(events), "alerts": sum(a["status"] == "alert" for a in alerts), "mode": mode,
           "duration_s": round(time.time() - t_start, 1)}
    with (LOG / "runs.jsonl").open("a") as f:
        f.write(json.dumps(run) + "\n")
    mirror()
    print(f"[{feeds.now_iso()}] run {run_id}: {len(items)} items → {len(events)} events → "
          f"{run['alerts']} alerts in {run['duration_s']}s")
    for a in alerts:
        print(f"   {a['tier']:<5} {a['risk_score']:>3} {a['name'][:50]:<50} TIV {agents.money(a['exposure']['tiv_usd'])}")
    return doc


if __name__ == "__main__":
    try:
        from dotenv import load_dotenv; load_dotenv()
    except Exception:
        pass
    offline = "--offline" in sys.argv
    if "--loop" in sys.argv:
        every = int(sys.argv[sys.argv.index("--loop") + 1])
        while True:
            try:
                cycle(offline)
            except Exception as e:
                print("cycle failed:", e)
            time.sleep(every)
    else:
        cycle(offline)
