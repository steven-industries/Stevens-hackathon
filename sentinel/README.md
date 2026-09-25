# Sentinel
Multi-agent early-warning pipeline: public multilingual signals → auditable Health / Wealth / Insurance alerts.

```bash
pip install -r requirements.txt
python -m src.make_portfolio          # (once) seeded SYNTHETIC demo book -> data/portfolio.csv, data/travelers.csv
python -m src.run --once              # one cycle (~10 s deterministic)
python -m src.run --loop 300          # always-on: a cycle every 5 min (appends log/runs.jsonl)
python -m src.run --once --offline    # demo from cache/ only, no network
python -m http.server 8000            # open http://localhost:8000/ui/
```

Env (optional): `ANTHROPIC_API_KEY` → LLM stages (scout naming, assessor rationale, 3 brief writers, router messages) use Claude
(`SENTINEL_MODEL`, default `claude-sonnet-5`); any LLM error / bad JSON / unverified quote / invented number → deterministic fallback.
Without a key everything runs deterministically (`mode: "deterministic"`). `SLACK_WEBHOOK_URL` → RED/AMBER P1 posts.
`SENTINEL_GDELT=1` → best-effort GDELT corroboration (often rate-limited).

Outputs: `log/alerts.json`, `log/events.jsonl` (agent trace), `log/runs.jsonl`, `log/outbox/*.md` (notifications),
`log/state.json` (dedup/escalation), mirrored to `ui/data/` each cycle (see CONTRACT.md).
Feeds: GDACS, NHC (AT/EP/CP), USGS, WHO DON API, ECDC, NASA EONET, Google News RSS (en/es/fr/pt/hi/ja/zh/…).
Every quote is checked verbatim against fetched source text by code (`verified`). Exposure numbers come from a synthetic book, not real policies.
