# Sentinel — Chubb early-warning challenge (Stevens Business + AI Hackathon, Sep 25 2026)

HARD DEADLINE: submit by 3:00 PM ET at https://ailab.stevens.edu/hackathon/submit/ . Pitch 5 min + Q&A at 3:00.
Read SPEC.md first. It is the whole plan. Do not expand scope beyond it.

## Non-negotiables
1. Scope = nat-cat + health ONLY. No geopolitics, no supply chain, no AIS/FIRMS/anything with auth.
2. The LLM NEVER generates a magnitude/severity number. Severity comes from GDACS/NHC/USGS/WHO fields. The LLM reasons about impact, with a confidence band.
3. Every claim in an alert carries `source_url` + `quote` (verbatim span from the source). A claim without a quote is a bug; drop it.
4. Every feed fetch writes to `cache/<feed>.json` first. If a live fetch fails, read the cache. The demo must run 100% offline from cache.
5. Multi-agent = one Python orchestrator + role-prompted Claude calls that each append a JSON record to `log/events.jsonl`. No LangGraph, no CrewAI.
6. UI renders `log/events.jsonl`. Content > chrome. If the UI is behind at 1:30 PM, render Markdown.

## Stack
Python 3.11, `anthropic`, `httpx`, `feedparser`. UI: single `ui/index.html` reading `log/events.jsonl` + `log/alerts.json` (serve with `python -m http.server`). No build step.

## Time boxes (ET)
11:35–12:40 pipeline · 12:40–1:40 UI · 1:40–2:10 backtest · 2:10–2:40 deck+rehearse · 2:40 submit.
Start the 10-minute scheduler loop as soon as the pipeline runs once, so the run log has 3+ timestamped cycles by 3 PM.
