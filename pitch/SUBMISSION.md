# Sentinel

**One-liner:** An always-on team of AI agents that turns public disaster and outbreak signals into briefs tied to an insurer's own exposure, every one of them auditable, delivered to the right desk before the morning call.

## Description (150 words)
When a hurricane forms or an outbreak surfaces, the signals are public within hours, but they're scattered across GDACS, NOAA, USGS, WHO and local news in a dozen languages. Insurers still stitch them together by hand. Sentinel runs every ten minutes. Fetch agents pull authoritative and multilingual feeds. A Scout clusters them into events, and a Corroborator requires independent sources before anything becomes an alert. A code-based Verifier checks every quote word-for-word against its source, and severity is copied from the issuing authority, never generated. An Exposure agent overlays the event on the insurer's book (policies and TIV by line). Three writers then produce Health, Wealth and Insurance briefs in underwriter vocabulary, and a Router notifies the CUO, Claims, the Cat desk, the CIO or A&H with caveat banners, deduplication and escalation. A backtest on a real past event measures lead time before the headlines.

## What's novel
- **No quote, no claim.** An LLM writes every sentence, but deterministic code verifies each one against a verbatim source quote. Severity always comes from the authority (NHC, USGS PAGER, GDACS, WHO).
- **Detection → exposure → decision.** Other tools stop at "something happened." Sentinel answers "what's in the footprint of *our* book, and who needs to act."
- **Briefs for each audience.** One event yields three briefs (Health / Wealth / Insurance), each routed to the person who acts on it, with caveats and a "what we don't know yet" section.
- **Multilingual corroboration.** A Spanish local report and an NHC advisory count as independent sources.
- **Measured, not claimed.** The run log proves it's always on, and the backtest measures lead time on a real past event.

## Tech stack
Python orchestrator (scheduled loop, offline cache) · Claude (Anthropic) for the reasoning and writing agents, with a deterministic fallback · public feeds: GDACS, NOAA NHC, USGS, NASA EONET, WHO DON, ECDC, Google News (en/es/fr/pt) · JSONL event and run logs · static HTML/JS UI · Slack/email notifier.

## What's real vs synthetic
Real: feeds, events, quotes, severity, run log, backtest timestamps. Synthetic: the insurance book used for the exposure overlay.

## Team
- [Name]: orchestration & agents
- [Name]: feeds & verification
- [Name]: UI & notifier
- [Name]: pitch & strategy

## Links
- Repo: [TODO]
- Demo video: [TODO]
- Deck: `pitch/deck.html`
- Backtest: `sentinel/BACKTEST.md`
