# Sentinel: early warning → auditable Health · Wealth · Insurance alerts
**Stevens Business + AI Hackathon, Chubb challenge (Sep 25, 2026)**

**Live demo:** https://sentinel-chubb.vercel.app, a snapshot of a real run today. **Deck:** https://sentinel-chubb.vercel.app/deck/

Sentinel is an always-on team of agents that watches public, multilingual hazard and health feeds. It corroborates weak signals across independent sources and overlays each event on the insurer's own book. It then writes three briefs per event (Health, Wealth, Insurance) and routes each one to the desk that acts on it. Every claim carries a verbatim quote that code has checked against the source.

```
Fetch ─▶ Scout ─▶ Corroborator ─▶ Verifier ─▶ Assessor ─▶ Exposure ─▶ Brief ×3 ─▶ Router ─▶ Notifier
GDACS    cluster   ≥2 independent   quote found   severity COPIED   footprint ×    Health     CUO, Claims,   Slack/email,
NHC      signals   sources, any     verbatim in   from authority;   insurer book   Wealth     Cat desk, CIO, dedup +
USGS     into      language         source (code, 0–100 score +     (policies,     Insurance  A&H, Public    escalation
WHO DON  events    (Google News     not LLM)      breakdown,        TIV by line,
ECDC               en/es/fr/pt/hi…)               unknowns          travelers)
EONET
```

## Design rules
1. **Severity is never generated.** It's copied from NHC, USGS PAGER, GDACS or WHO.
2. **No quote, no claim.** The Verifier checks every bullet's quote verbatim against the fetched source text, and unverified bullets are dropped.
3. **Always on and can't break.** It runs on a 5–10 min loop, writes a run log, falls back to the feed cache, and runs offline. Claude (`ANTHROPIC_API_KEY`) writes the reasoning and briefs. On any error it falls back to a deterministic path per stage, and responses are cached by evidence hash.
4. **Honest about what's synthetic.** Feeds, events, quotes and severity are real. The insurance book behind the exposure overlay is a seeded **synthetic** portfolio.

## Repo map
| Path | What |
|---|---|
| `sentinel/src/` | `feeds.py` (fetch + cache), `agents.py` (all agent stages), `run.py` (orchestrator/loop), `backtest.py`, `make_portfolio.py` |
| `sentinel/ui/index.html` | Static single-file desk UI; reads `ui/data/*` |
| `sentinel/CONTRACT.md` | Data contract (alerts, agent trace, run log, backtest) |
| `sentinel/BACKTEST.md` | Foshan chikungunya 2025 replay: alert **18 h before the first English headline, ~8 days before Bloomberg** |
| `pitch/` | 3-min script, Q&A, submission text, deck |
| `STRATEGY.md` | Judging criteria → our design choices |

## Run it
```bash
cd sentinel
pip install -r requirements.txt
# LLM: uses the logged-in `claude` CLI (Pro/Max subscription) or ANTHROPIC_API_KEY; else deterministic
python -m src.run --once            # one cycle, live feeds
python -m src.run --loop 300 &      # always-on
python -m http.server 8000          # open http://localhost:8000/ui/
python src/backtest.py --strict     # reproduce the backtest
```
