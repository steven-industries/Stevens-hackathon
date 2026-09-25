# How we win: Sentinel for the Chubb challenge

## The official criteria, and what judges will actually check
| Criterion | What a Chubb judge checks | Our answer |
|---|---|---|
| Real value | Would a real desk at Chubb use it Monday morning? | Tells the accumulation/cat desk **how much of *our* book** is inside the footprint (policies, TIV by line, insured travelers), not just that "a storm exists". |
| Customer fit | Named user, trigger, adoption path | Personas: CUO Property, Head of Claims, Cat/Accumulation desk, Head of A&H/Travel, CIO. Pilot: point it at Chubb's exposure file inside their VPC. It sits on top of the feeds they already buy (Dataminr, cat models). |
| Innovation | Not a thin clone of Dataminr or BlueDot | Detection is a commodity. What's new: **translation + audit**. Each claim has a verbatim quote that code checks. Severity is copied from the issuing authority and never generated. The score has a transparent breakdown. Each event yields three lens-specific briefs routed to the right desk. |
| Execution | Does it run on live data, right now? | Live feeds (GDACS, NHC, USGS, WHO, ECDC, EONET, multilingual news), a run log with timestamped cycles, offline cache, and a deterministic fallback so the demo can't break. |
| Pitch | Believable in 3 minutes | Real story, one live alert, a dollar figure, one verified citation, then the backtest lead time. |

## Our own criteria (tie-breakers we optimize for)
1. **Trust beats cleverness.** An insurer rejects a tool that hallucinates, so every number traces to a source span or to a deterministic computation.
2. **Speak their language.** Use underwriter vocabulary: lines of business, TIV, reserving posture, ILWs and cat bonds, CBI, event cancellation.
3. **Demo can't fail.** It runs from cache and without an API key. The UI is static, so it works from a laptop or a URL.
4. **One number per beat.** Exposed TIV, lead time in hours, and sources/languages corroborated.
5. **Honest about what's synthetic.** The demo portfolio is labelled synthetic, and the backtest timestamps carry URLs and precision notes.

## Scope we deliberately cut
Geopolitics and supply chain are left out. AIS and satellite feeds that need auth are left out. There's no agent framework: a single Python orchestrator with role agents is easier to audit.
