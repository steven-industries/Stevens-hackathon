# Sentinel
1. `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
2. `cp .env.example .env` and set ANTHROPIC_API_KEY (export it, or `python-dotenv`).
3. `python -m src.feeds` → verify feeds parse from THIS laptop; this also fills cache/.
4. `python -m src.run --once` → log/events.jsonl, log/alerts.json, log/runs.jsonl
5. `python -m src.run --loop 600 &` → keep it running all afternoon (run-log proof).
6. `python -m http.server 8000` → open http://localhost:8000/ui/ (UI reads ../log/*.json)
Open Claude Code here and say: "Read CLAUDE.md and SPEC.md, then build ui/index.html and finish the WHO DON + GDELT fetchers."
