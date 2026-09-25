# SPEC — Sentinel: signal → three-lens insurance alert

## What it is (one sentence)
An always-on agent pipeline that watches public nat-cat and health feeds, corroborates weak signals across sources, and turns each event into an auditable alert with three audience-specific briefs (Health / Wealth / Insurance) routed to the right desk.

## Whitespace / pitch line
Dataminr, BlueDot, GDACS already *detect*. Nobody ships "one signal → Health / Wealth / Insurance briefs, every number traced to a quoted source span, routed to the CUO / CIO / claims." We are the last mile an insurer assembles by hand every morning.

## Feeds (all free, no auth). Fetch → normalize → cache/<name>.json
| name | url | parse |
|---|---|---|
| gdacs | https://www.gdacs.org/xml/rss.xml | RSS; fields: title, gdacs:alertlevel (Green/Orange/Red), gdacs:eventtype (TC/EQ/FL/VO/DR), gdacs:country, gdacs:severity, link, pubDate |
| nhc_atl | https://www.nhc.noaa.gov/index-at.xml | RSS; nhc:Cyclone blocks: name, wallet, atcf, datetime, movement, pressure, wind, headline |
| nhc_epac | https://www.nhc.noaa.gov/index-ep.xml | same |
| usgs | https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson | GeoJSON; mag, place, time, url, alert (PAGER green/yellow/orange/red) |
| reliefweb | https://api.reliefweb.int/v1/disasters?appname=sentinel&limit=30&sort[]=date:desc&fields[include][]=name&fields[include][]=status&fields[include][]=primary_type.name&fields[include][]=country.name&fields[include][]=url&fields[include][]=date.created | JSON |
| who_don | https://www.who.int/emergencies/disease-outbreak-news | HTML list; item links like /emergencies/disease-outbreak-news/item/2026-DON617 ; fetch each item page for text |
| gdelt | https://api.gdeltproject.org/api/v2/doc/doc?query=<terms>&mode=artlist&format=json&maxrecords=30&timespan=3d[&sourcelang:spa] | JSON articles; use `sourcelang:` to demonstrate multilingual corroboration |

Normalize every item to:
```json
{"id": "...", "feed": "gdacs", "type": "TC|EQ|FL|VO|OUTBREAK", "title": "...", "country": "...", "lat": 0, "lon": 0,
 "issued_severity": {"scale": "GDACS|NHC_SSHWS|USGS_PAGER|WHO_GRADE", "value": "Red|Cat 5|orange|Grade 3"},
 "published": "ISO", "url": "...", "text": "raw text/summary", "retrieved": "ISO"}
```

## Agents (each = one Claude call with a role prompt; each appends a record to log/events.jsonl)
Record shape: `{"ts": ISO, "run_id": ..., "agent": name, "event_id": ..., "input_refs": [...], "output": {...}, "model": ..., "latency_ms": n}`

1. **Scout** — input: all normalized items from this run. Output: candidate events, clustering items that refer to the same real-world event (e.g., NHC + GDACS + GDELT on the same cyclone). Emits `{event_id, type, name, member_item_ids[], why_grouped}`.
2. **Corroborator** — per event: finds ≥2 independent sources; for each source extracts `{source_url, quote}` (verbatim). Emits `corroboration_count`, `languages_seen[]`, `earliest_signal_ts`, `quotes[]`. If <2 sources → status `watch`, not `alert`.
3. **Assessor** — per event: copies `issued_severity` from the authoritative feed (never invents), sets `geo_spread` (countries/regions from quotes), `time_horizon` (hours/days), `confidence` ∈ {low, med, high} with a one-line rationale citing quotes. Emits `unknowns[]` (what we can't yet say).
4. **Brief writers ×3** — same input, three role prompts:
   - *Health*: exposed population, health-system strain, likely case trajectory — each bullet cites a quote.
   - *Wealth*: sectors, asset classes, regional markets likely affected; caveated.
   - *Insurance*: lines of business (HO, commercial property, BI, marine, event cancellation, A&H, travel), claims exposure direction, reserving posture, reinsurance/cat-bond notes. Use insurer vocabulary. Each bullet cites a quote.
5. **Router** — maps briefs to personas: CUO Property → Insurance; Head of Claims → Insurance; CIO → Wealth; CMO/A&H → Health; Public → caveated one-liner. Emits `{persona, brief_key, channel, caveat_banner}`.

Final `log/alerts.json`: list of `{event_id, name, type, status: watch|alert, issued_severity, confidence, geo_spread, time_horizon, unknowns[], briefs:{health,wealth,insurance}, routing[], sources[{url,quote,lang,retrieved}], first_signal_ts, alert_ts}`.

## Orchestrator (src/run.py)
`python -m src.run --once` runs one cycle; `python -m src.run --loop 600` runs every 10 min and appends `{"ts","run_id","items_fetched","events","alerts"}` to `log/runs.jsonl` (this is the "always-on" proof shown in the UI). `--offline` reads cache only.

## UI (ui/index.html, no build)
Left pane: agent trace — one row per events.jsonl record, streaming order, showing agent name, event, and the quote(s) it used. Right pane: alert card for the selected event — headline, issued severity chip (with scale), confidence, geo, horizon; tabs Health / Wealth / Insurance, each bullet with a citation chip that opens the source; "What we don't know yet" block; **Route** button that reveals persona → brief mapping with the caveat banner. Bottom strip: run log (timestamped cycles). Dark, calm, insurer-desk aesthetic; content first.

## Backtest (src/backtest.py) — 30 min, one event
Pick one past event with archived timestamps (e.g., the 2026 DRC Ebola DON, or a 2025 hurricane). Feed items with their original `published` timestamps in order; record when Corroborator hits ≥2 sources (our alert time) vs. first mainstream headline (GDELT query by date). Output one line: "First weak signal T−X h · Sentinel alert T−Y h · Headline T". Put it on a slide.

## Demo script (what's on screen at 3 PM)
1. Live alert card for the current headline hurricane (verify on nhc.noaa.gov: agents reported Hurricane Polo Cat 5 EPac and Hurricane Nolo toward Hawaii; confirm names before saying them).
2. Click Health → Wealth → Insurance; read one insurance bullet with its citation.
3. Route → show CUO Property receives Insurance brief with caveat banner.
4. Run-log strip: 3+ cycles this afternoon.
5. Backtest slide.

## Q&A answers
- Not Dataminr? They detect; we translate + audit. We sit on top of GDACS/WHO/Dataminr.
- Trust the severity? We don't generate it; the authority issues it; we reason only about impact with a quoted source for every claim.
- Always-on? Here's the run log and the 20-line scheduler.
- Who pays? Cat-risk/underwriting desks already pay for Verisk, Dataminr, BlueDot; this is the last mile.
