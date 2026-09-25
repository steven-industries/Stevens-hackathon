# Local setup for the 3 PM demo (for a local Claude Code session)

Paste this into your local Claude Code session, run from the repo root:

> Read LOCAL_SETUP.md and do every step. Stop and tell me if any check fails.

## Steps
1. `git fetch origin claude/festive-thompson-0dehkl && git checkout claude/festive-thompson-0dehkl && git pull`
2. `cd sentinel && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
3. **LLM backend: no API key needed.** The pipeline auto-detects the logged-in **Claude Code CLI** (`claude -p`, headless) and uses your Pro/Max subscription. Run `claude -p "say ok" --output-format json` once. It must print JSON with `"is_error": false`. If it doesn't, run `claude` and log in first.
   - Auto-detect order: `SENTINEL_LLM=cli` (forced), then `ANTHROPIC_API_KEY` (API), then `claude` on PATH (CLI). `SENTINEL_LLM=off` forces deterministic.
   - Optional: `SENTINEL_CLI_MODEL` (default `sonnet`).
4. **First live cycle:** `python -m src.run --once`. With the CLI backend it takes **~3–4 minutes** (about 40 Claude calls, 4 in parallel).
   - Check: `python3 -c "import json;print(json.load(open('ui/data/alerts.json'))['mode'])"` prints `claude`.
   - Check: `grep -c '"model": "claude-code-cli' log/events.jsonl` is greater than 0.
   - If it prints `deterministic`, read the `LLM fallback:` lines in the output. They usually mean the CLI isn't logged in.
   - Spot-check the top 2 alerts' insurance bullets: `python3 -c "import json;[print(a['name'],'\n ', '\n  '.join(b['text'] for b in a['briefs']['insurance']['bullets'])) for a in json.load(open('ui/data/alerts.json'))['alerts'][:2]]"`.
5. **Start the always-on loop** in its own terminal and leave it running: `python -m src.run --loop 300`. The first cycle takes ~3.5 min. Later cycles are faster, because unchanged events come from the Claude response cache. Claude responses are cached by an evidence hash, so an unchanged event isn't re-billed.
6. **Serve the UI:** `python -m http.server 8000` in another terminal, then open http://localhost:8000/ui/
   - Check: the header chip says **Claude agents**, the feeds chip shows about 8 live feeds, and the run-log strip is filling up.
   - Press `B` for the backtest, `R` for route & notify, and `1`–`4` for the tabs.
7. **Offline fallback (Wi-Fi dies):** stop the loop and run `python -m src.run --once --offline`. The UI keeps working from `cache/`.
8. **Before pitching:** check the Hurricane Polo category on https://www.nhc.noaa.gov. If it has changed, update the numbers in `pitch/PITCH.md` demo beats 1–2 to match the UI.

## If Claude mode works
Optionally refresh the public snapshot so https://sentinel-chubb.vercel.app shows Claude-written briefs:
`git add sentinel/ui/data && git commit -m "Refresh snapshot (Claude mode)" && git push`.
Then either redeploy the `sentinel-chubb` Vercel project (production, root `sentinel/ui`) or ask the cloud session to do it.

## Don't
- Don't commit `.env`, `log/`, or `cache/`. They're already gitignored.
- Don't change `CONTRACT.md` field names. The UI depends on them.
