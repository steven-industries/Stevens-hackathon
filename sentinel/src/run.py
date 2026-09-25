"""Orchestrator: python -m src.run --once | --loop 600 | --offline"""
import json, sys, time, uuid, pathlib, datetime as dt
from . import feeds, agents

LOG = pathlib.Path("log"); LOG.mkdir(exist_ok=True)

def cycle(offline=False, max_events=3):
    run_id = uuid.uuid4().hex[:8]; ts = dt.datetime.now(dt.timezone.utc).isoformat()
    items = feeds.fetch_all(offline)
    # TODO: add GDELT corroboration per top event name (feeds.fetch_gdelt(name, lang="spa"))
    scout = agents.call("scout", {"items": items, "input_refs": [i["id"] for i in items]}, run_id)
    alerts = []
    for ev in scout["events"][:max_events]:
        members = [i for i in items if i["id"] in ev["member_item_ids"]]
        pay = {"event": ev, "items": members, "input_refs": ev["member_item_ids"]}
        corr = agents.call("corroborator", pay, run_id, ev["event_id"])
        ass = agents.call("assessor", pay | {"corroboration": corr}, run_id, ev["event_id"])
        briefs = {k.split("_")[1]: agents.call(k, pay | {"assessment": ass}, run_id, ev["event_id"])
                  for k in ("brief_health", "brief_wealth", "brief_insurance")}
        route = agents.call("router", {"event": ev, "assessment": ass}, run_id, ev["event_id"])
        alerts.append({"event_id": ev["event_id"], "name": ev["name"], "type": ev["type"], "status": corr["status"],
                       "issued_severity": ass["issued_severity"], "confidence": ass["confidence"],
                       "geo_spread": ass["geo_spread"], "time_horizon": ass["time_horizon"], "unknowns": ass["unknowns"],
                       "briefs": briefs, "routing": route["routing"], "sources": corr["sources"],
                       "first_signal_ts": corr.get("earliest_signal_ts"), "alert_ts": ts})
    (LOG / "alerts.json").write_text(json.dumps(alerts, indent=1))
    with (LOG / "runs.jsonl").open("a") as f:
        f.write(json.dumps({"ts": ts, "run_id": run_id, "items_fetched": len(items),
                            "events": len(scout["events"]), "alerts": sum(a["status"] == "alert" for a in alerts)}) + "\n")
    print(f"[{ts}] run {run_id}: {len(items)} items → {len(scout['events'])} events → {len(alerts)} processed")
    return alerts

if __name__ == "__main__":
    offline = "--offline" in sys.argv
    if "--loop" in sys.argv:
        every = int(sys.argv[sys.argv.index("--loop") + 1])
        while True:
            try: cycle(offline)
            except Exception as e: print("cycle failed:", e)
            time.sleep(every)
    else:
        cycle(offline)
