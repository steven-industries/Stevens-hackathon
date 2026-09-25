# DESIGN.md: Sentinel dashboard (v2 "Morning brief")

Mode: Operate. Surface: `sentinel/ui/index.html`. Product truth lives in PRODUCT.md.

## Theme: light, warm paper
The screen is projected on the 8:00 a.m. call in a lit room and read on a desk monitor at 6:00 a.m. Dark UIs wash out on projectors and read as "command centre / feed" (the Dataminr look the user rejected). A light, warm-neutral surface with near-black ink holds contrast when projected and reads like a risk memo, not a terminal.

## Tokens (defined on `:root` in index.html)
- **Neutrals:** bg `#f3f2ee`, surface `#fff`, surface-2 `#f8f7f4`, sunk `#ecebe6`, line `#e2e0d9`/`#cfccc3`, ink `#15181d`, ink-2 `#3d434c`, muted `#646b75`.
- **Colour means something:** red `#b42318` (RED tier, ELEVATED action, damage core, P1), amber `#a15c07` (AMBER, MONITOR, P2, unknowns), watch slate `#5b6573`, ok green `#1d7a4f` (verified by code, backtest lead). Our book is navy `#1f4e8c` (sites, bars, citations); insured lives are violet `#6b4fa0`. Nothing is decorative.
- **Type:** IBM Plex Sans for all UI and prose, IBM Plex Mono only for figures ($, lives, sites, times, ids), tabular numerals throughout. Scale is about 1.2: 11.5 / 12.5 / 14 / 15.5 / 18 / 22 / 28 / 36 px. Numbers are the heroes (36px mono exposure, 22px mono on cards). The recommended action is the largest text (28px).
- **Spacing:** 4px base (4, 8, 12, 16, 20, 24, 32).
- **Radius:** 4 (chips), 6 (controls), 10 (panels, cards).
- **Depth:** one hairline shadow for panels, one soft offset shadow for drawers and the modal. No glows.

## Information architecture
1. Header: date/time, **N decisions need you today**, TIV / insured lives / core sites across active decisions, freshness (feeds live, last cycle, Claude agents or deterministic fallback), a backtest chip, and trace.
2. Lens bar (keys 1 to 4): Accumulation/CUO, Claims, A&H & Travel, CIO. Each lens changes the ranking, the hero metric, the default brief tab, and highlights "to you" in routing.
3. Left: **Decisions for our book**. Each card leads with the action, then exposure, authority severity, horizon, corroboration and who was notified. Events with no exposure collapse to "Monitoring, no book exposure".
4. Right: the selected event. Action headline, issued severity ("issued by NHC · not generated"), map (track, buffer, core, our sites) beside the exposure panel, then the lens brief with inline citation markers (these open the evidence drawer), what we don't know yet, who has been told, and why this score.
5. Tucked away: evidence, route & notify, and trace/run log sit in a right drawer. The backtest is a modal.

"Synthetic demo book" appears in the lens bar, on the exposure panel, and in the method note.
