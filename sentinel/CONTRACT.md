# Data contract (shared by pipeline, UI, backtest). Do not change field names without telling the orchestrator.

The pipeline writes `log/*` and mirrors a snapshot into `ui/data/` (UI is static; it loads `./data/...` relative to ui/index.html).

## ui/data/alerts.json
```json
{
 "generated_at": "ISO", "run_id": "ab12cd34", "mode": "claude | deterministic",
 "feeds": [{"name": "gdacs", "items": 42, "status": "live | cache | error", "retrieved": "ISO"}],
 "alerts": [{
   "event_id": "tc-humberto-2026", "name": "Hurricane X", "type": "TC|EQ|FL|VO|WF|DR|OUTBREAK",
   "status": "alert | watch",
   "tier": "RED | AMBER | WATCH",
   "risk_score": 0-100,
   "score_breakdown": [{"factor": "authority severity", "points": 30, "reason": "GDACS Red", "source_url": "..."}],
   "issued_severity": {"scale": "GDACS|NHC_SSHWS|USGS_PAGER|WHO_DON", "value": "Red", "source_url": "..."},
   "confidence": "low | med | high", "confidence_rationale": "one line",
   "geo": {"lat": 0, "lon": 0, "countries": [], "regions": [], "radius_km": 300},
   "time_horizon": "24-72h",
   "first_signal_ts": "ISO", "alert_ts": "ISO",
   "languages_seen": ["en", "es"],
   "sources": [{"id": "gdacs:123", "feed": "gdacs", "url": "...", "title": "...", "lang": "en", "published": "ISO", "quote": "verbatim span", "verified": true}],
   "exposure": {"policies": 0, "tiv_usd": 0, "by_line": [{"line": "Commercial Property", "policies": 0, "tiv_usd": 0}],
                "top_locations": [{"name": "...", "lat": 0, "lon": 0, "tiv_usd": 0, "distance_km": 0, "line": "..."}],
                "insured_travelers": 0, "method": "one line: how computed; synthetic demo book"},
   "briefs": {
     "health":    {"headline": "...", "bullets": [{"text": "...", "source_url": "...", "quote": "...", "verified": true}], "caveats": []},
     "wealth":    {"headline": "...", "bullets": [...], "caveats": []},
     "insurance": {"headline": "...", "bullets": [...], "caveats": [], "reserving_posture": "watch | strengthen | no action"}
   },
   "unknowns": ["..."],
   "routing": [{"persona": "CUO Property", "brief": "insurance", "channel": "email|slack|sms|public", "priority": "P1|P2|P3",
                "caveat_banner": "one sentence", "message": "the actual notification text, <= 400 chars"}]
 }]
}
```
Alerts sorted by risk_score desc. `verified` = the quote was found verbatim (whitespace/case-normalised) in the fetched source text by code, not by the LLM.

## ui/data/events.jsonl  (agent trace, one JSON per line, append order)
`{"ts","run_id","agent","event_id","input_refs":[],"output":{...},"summary":"one human line","model":"claude-... | deterministic","latency_ms":n}`
Agents: fetch, scout, corroborator, verifier, assessor, exposure, brief_health, brief_wealth, brief_insurance, router, notifier.

## ui/data/runs.jsonl  (always-on proof)
`{"ts","run_id","items_fetched","feeds_ok","events","alerts","mode","duration_s"}`

## ui/data/backtest.json
```json
{"event": "name", "summary": "one line", "lead_time_hours": 0,
 "timeline": [{"ts": "ISO", "kind": "weak_signal | authority | sentinel_alert | mainstream", "source": "...", "lang": "fr", "title": "...", "url": "...", "note": "..."}],
 "method": "how timestamps were obtained", "caveats": []}
```
