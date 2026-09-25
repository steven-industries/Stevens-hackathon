# Local setup for the 3 PM demo (for a local Claude Code session)

Paste this into your local Claude Code session, run from the repo root:

> Read LOCAL_SETUP.md and do every step. Stop and tell me if any check fails.

## Steps
1. `git fetch origin claude/festive-thompson-0dehkl && git checkout claude/festive-thompson-0dehkl && git pull`
2. `cd sentinel && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
3. **API key.** Check that `ANTHROPIC_API_KEY` is set in the shell. If it isn't, ask the user to export it. Never print it, and never write it to a tracked file (`.env` is gitignored).
4. **First live cycle:** `python -m src.run --once`. It should take under 3 minutes.
   - Check: `python3 -c "import json;print(json.load(open('ui/data/alerts.json'))['mode'])"` prints `claude`.
   - If it prints `deterministic`, look at the `LLM fallback:` lines in the output:
     - An unknown model error means you should try `export SENTINEL_MODEL=claude-sonnet-4-5` (or another model the key can use) and rerun.
     - A 401 means the key is wrong.
   - Also check: `grep -c '"model": "claude' log/events.jsonl` is greater than 0.
   - Spot-check the top 2 alerts' insurance brief bullets for sense: `python3 -c "import json;[print(a['name'],'\n ', '\n  '.join(b['text'] for b in a['briefs']['insurance']['bullets'])) for a in json.load(open('ui/data/alerts.json'))['alerts'][:2]]"`. Every bullet must still carry a quote. The verifier drops any that don't match.
5. **Start the always-on loop** in its own terminal and leave it running: `python -m src.run --loop 300`. Claude responses are cached by an evidence hash, so an unchanged event isn't re-billed.
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
