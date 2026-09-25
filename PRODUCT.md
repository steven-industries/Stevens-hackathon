# PRODUCT.md: Sentinel

## What it is
An always-on multi-agent system that watches public hazard and health feeds (NHC, GDACS, USGS, WHO, ECDC, NASA EONET, multilingual news). It turns each emerging event into **a decision about the insurer's own book**, with every claim traced to a verified quote. Built for Chubb, the world's largest publicly traded P&C insurer.

## Who uses the dashboard (primary)
**The Cat / Accumulation Manager on Chubb's property desk, at 6:00 a.m.** The CUO Property reads the same screen before the 8:00 a.m. call.
- Job to be done: "Before the call, tell me which events touch **our** book, how much is at risk, what I should do about it today, and whether I can trust it."
- They are experts. They speak TIV, PML, accumulation, binding moratorium, CBI, ILW, cat bond, reserving, and they distrust anything that looks like a black box.
- They scan in about 60 seconds, then drill into one or two events. The screen is used on a desk monitor and projected in the morning call.

## Secondary lenses (same data, different first question)
- **Head of A&H / Travel:** insured lives in affected areas, evacuation and assistance capacity, WHO risk level.
- **Head of Claims:** sites in the damage core, and when to pre-stage adjusters.
- **CIO:** sector and asset read-through (directional only).
- Not a CFO tool. Not a public-facing site.

## What they care about, in order
1. **What needs a decision today?** Actions, not events: e.g. "Restrict new binding in Baja California Sur watch area", "Review evacuation capacity for 3.7k insured lives in DRC".
2. **Our exposure:** $TIV and sites (and lives) in the screening buffer versus the damage core, by line. This is exposure, not headcount of news articles.
3. **Severity from the authority**, never from the model (NHC category, WHO risk level, USGS PAGER).
4. **Trust:** corroborated by N independent publishers in M languages. Every sentence has a verbatim, code-verified quote one click away.
5. **Time:** first signal → corroborated → now; horizon (e.g. landfall 24–72 h).
6. **Who has been told** (routing, priority, channel), and what we don't know yet.
7. Always-on proof (run log, agent trace). This is secondary and belongs in a drawer, not on the main stage.

## Differentiator vs Dataminr / BlueDot
They detect and stream events. Sentinel converts an event into **our exposure + a recommended action + an audit trail**, routed to the person who owns the decision. The UI must make this obvious in 5 seconds: lead with actions and dollars and lives, not with a feed.

## Tone
Calm, precise, trustworthy: a risk desk, not a sci-fi command center. Density is fine for experts, noise is not. Colour means something (severity/action), nothing decorative. Numbers are the heroes.

## Constraints
Single static file `sentinel/ui/index.html` (vanilla JS/CSS, no build), reading `ui/data/alerts.json`, `events.jsonl`, `runs.jsonl`, `backtest.json` per `sentinel/CONTRACT.md`. Leaflet from cdnjs is allowed. It must work offline from fixtures and at 1920×1080 and 1440×900 projected. Exposure numbers come from a synthetic demo book and must be labelled as such.
