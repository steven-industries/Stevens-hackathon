"""Role-prompted Claude calls. Each call appends one record to log/events.jsonl."""
import json, time, pathlib, uuid, datetime as dt
import anthropic

LOG = pathlib.Path("log"); LOG.mkdir(exist_ok=True)
EVENTS = LOG / "events.jsonl"
client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-5"  # fast enough for a live demo; swap if needed

COMMON = """You are one agent in Sentinel, an insurer's early-warning pipeline.
Rules you must never break:
- Never invent a severity/magnitude number. Copy `issued_severity` from the authoritative feed item verbatim.
- Every factual claim must carry {"source_url": ..., "quote": "<verbatim span from that source's text>"}.
- If you cannot support a claim with a quote, put it under "unknowns" instead.
- Output ONLY the JSON object requested. No prose."""

ROLES = {
 "scout": """Cluster the input items into real-world events. Items from different feeds (NHC, GDACS, GDELT, USGS, ReliefWeb) about the same cyclone/quake/outbreak belong to one event.
Return {"events":[{"event_id":"slug","type":"TC|EQ|FL|VO|OUTBREAK","name":"...","member_item_ids":[...],"why_grouped":"..."}]}""",
 "corroborator": """For the given event, list independent sources (different feeds/outlets). For each: {"source_url","quote","lang","published"}.
Return {"event_id","corroboration_count":n,"languages_seen":[],"earliest_signal_ts":"ISO","sources":[...],"status":"alert" if count>=2 else "watch"}""",
 "assessor": """Assess the event. Copy issued_severity from the authoritative feed item (NHC for cyclones, USGS for quakes, GDACS otherwise, WHO for outbreaks).
Return {"event_id","issued_severity":{"scale","value","source_url"},"geo_spread":{"countries":[],"regions":[]},"time_horizon":"e.g. 24-72h","confidence":"low|med|high","rationale":[{"source_url","quote"}],"unknowns":[...]}""",
 "brief_health": """Write the HEALTH brief: exposed population, health-system strain, likely trajectory. 3-5 bullets, each {"text","source_url","quote"}.
Return {"event_id","lens":"health","bullets":[...],"caveats":[...]}""",
 "brief_wealth": """Write the WEALTH brief: sectors, asset classes, regional markets likely affected; direction and rough horizon; be explicit about uncertainty. 3-5 bullets, each {"text","source_url","quote"}.
Return {"event_id","lens":"wealth","bullets":[...],"caveats":[...]}""",
 "brief_insurance": """Write the INSURANCE brief in underwriter vocabulary: lines of business affected (HO, commercial property, BI/CBI, marine/cargo, A&H, travel, event cancellation), claims-exposure direction, reserving posture (watch / strengthen / no action), reinsurance and cat-bond notes. 4-6 bullets, each {"text","source_url","quote"}.
Return {"event_id","lens":"insurance","bullets":[...],"reserving_posture":"...","caveats":[...]}""",
 "router": """Route briefs to personas. Personas: CUO Property, Head of Claims, CIO, Head of A&H, Public.
Return {"event_id","routing":[{"persona","brief":"health|wealth|insurance","channel":"email|slack|sms|public","caveat_banner":"one sentence"}]}""",
}

def call(agent, payload, run_id, event_id=None):
    t0 = time.time()
    msg = client.messages.create(model=MODEL, max_tokens=2000, system=COMMON + "\n\n" + ROLES[agent],
                                 messages=[{"role": "user", "content": json.dumps(payload)}])
    text = msg.content[0].text.strip()
    if text.startswith("```"): text = text.strip("`").split("\n", 1)[1]
    out = json.loads(text)
    rec = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(), "run_id": run_id, "agent": agent,
           "event_id": event_id or out.get("event_id"), "input_refs": payload.get("input_refs", []),
           "output": out, "model": MODEL, "latency_ms": int((time.time() - t0) * 1000)}
    with EVENTS.open("a") as f: f.write(json.dumps(rec) + "\n")
    return out
