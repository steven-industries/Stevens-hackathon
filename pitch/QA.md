# Sentinel: likely judge questions and answers

Rule: answer in two sentences, then stop. Offer to show the proof on screen, because the UI has it.

**1. How do you stop the LLM from hallucinating?**
We split the work into steps that don't trust each other. Severity is copied from the issuing authority (NHC category, USGS PAGER, GDACS alert level, WHO grade), and the model never generates it. Every claim in a brief has to carry a verbatim quote. The Verifier is plain code, not an LLM: it string-matches each quote against the fetched source text and drops any claim whose quote isn't there. The risk score is a transparent formula with its breakdown shown, and "What we don't know yet" is a required field.

**2. What about false positives? Alert fatigue is the real killer.**
One feed on its own only gets you to "watch." An "alert" needs at least two *independent* sources, and those can be in different languages. The Router sends an alert only when an event touches the book (exposure > 0) or when the authority's severity crosses a threshold. It suppresses duplicates across cycles and escalates only when severity or exposure goes *up*. In practice the CUO gets a handful of messages, not a firehose.

**3. Why not just buy Dataminr (or BlueDot, or Moody's RMS Event Response)?**
Those are good at *detection* and *hazard modeling*. Dataminr covers 1M+ sources in 150+ languages, and RMS publishes HWind footprints every six hours. Sentinel is the last mile none of them sells: detection → *your* exposure → a brief in underwriter vocabulary, with every sentence traceable to a quote, routed to the right person. Their feeds can be inputs to Sentinel. We complement them, not replace them.

**4. Data licensing: can you actually use these sources?**
The demo uses only free, public feeds: GDACS, NOAA/NHC and USGS (US government, public domain), NASA EONET, WHO Disease Outbreak News, ECDC, and news headlines and links. We store the quote, the URL and the retrieval time, not full copyrighted articles. In production, licensed feeds Chubb already pays for (Dataminr, cat-model vendors) plug in as extra Fetch agents under Chubb's existing contracts.

**5. What does a run cost?**
Most of the pipeline is deterministic code: fetching, clustering pre-filters, quote verification, scoring and exposure overlay. We only call Claude for events that pass the corroboration gate, which is a few events per cycle. We log tokens per run. *Fill in from the run log:* ~$[TODO] per cycle, so ~$[TODO]/day at a 10-minute cadence. That's a small fraction of one analyst hour. If the API is down, a deterministic template fallback still produces the alert.

**6. Will it scale to Chubb's size?**
Chubb writes in 54+ countries. Each agent is stateless and works on one event at a time, so it parallelizes by event and by region. The exposure overlay is a spatial join (footprint polygon × geocoded locations) that cat teams already run on millions of locations. Scaling means adding Fetch agents, not rewriting the pipeline.

**7. You're asking for Chubb's exposure data. How is it secured?**
It never leaves Chubb. Sentinel deploys in Chubb's own cloud account/VPC. The exposure file stays in Chubb's store, and the overlay runs locally. The LLM only sees event text and *aggregated* results (e.g., "N policies, $X TIV in the cone"), never policyholder details. LLM access can go through Chubb's approved enterprise endpoint (e.g., Claude through AWS Bedrock in their account).

**8. How is it multilingual?**
We query news in en/es/fr/pt (and more) and pull in non-English local sources. Local press often reports first: the first public reports of COVID were Chinese-language articles about a Wuhan pneumonia cluster, which BlueDot flagged on Dec 31, 2019, nine days before WHO's public notice. The Corroborator counts a Spanish local report and an NHC advisory as *independent* sources. Quotes are kept in the original language, with a translation shown next to them, so the Verifier checks the original text.

**9. What does "always-on" mean here?**
An orchestrator loop runs every 5–10 minutes and appends to a run log (`log/runs.jsonl`) with timestamps, item counts, events and alerts. The UI shows that log. It has been running all afternoon. It also runs offline from cache, so it survives a feed outage. In production it's a scheduled container job with health alerts.

**10. What's real and what's synthetic?**
Real: every feed, every event, every quote and source URL, severity levels, the run log, the backtest timestamps. Synthetic: the insurance book (policies, TIV, travelers). We don't have Chubb's data, and we won't pretend to. The first pilot deliverable is swapping in Chubb's real exposure file.

**11. Go-to-market: how does Chubb adopt this?**
Land with one desk: a 90-day pilot with the cat/accumulation team, one peril (Atlantic hurricane) and one region, on Chubb's real exposure file. Success metrics: hours of lead time before the moratorium decision, analyst hours saved on the morning event report, and the precision of alerts that touch the book. Then expand to A&H/Travel (outbreaks, and alerts about insured travelers) and to Claims (pre-staging adjusters). Pricing is an annual platform license per carrier, which sits next to the cat-model and Dataminr line items.

**12. What are the next steps after today?**
(1) Put Chubb's real exposure schema in place of the synthetic book. (2) Add Dataminr / Moody's RMS HWind footprints as Fetch inputs. (3) Add alert feedback ("useful / noise") to tune the thresholds. (4) Extend the backtest to 10+ past events, so we report a lead-time distribution and not a single anecdote.

---

### Backup facts to keep in your pocket (sourced)
- Chubb: largest publicly traded P&C insurer; $55.4B P&C gross written premiums in 2024; operates in 55 countries and territories. https://about.chubb.com/stories/2024-shareholder-letter.html
- Chubb 2025 full-year pre-tax cat losses $2.92B (vs $2.39B in 2024). https://news.chubb.com/2026-02-03-Chubb-Reports-Fourth-Quarter-Net-Income-of-3-21-Billion,-Up-24-7-,-and-Core-Operating-Income-of-2-98-Billion,-Up-21-7-Consolidated-Net-Premiums-Written-of-13-1-Billion,-Up-8-9-,-with-P-C-and-Life-Insurance-Up-7-7-and-16-9-Record-P-C-Combined-Ra
- COVID: Lloyd's estimated $203B of industry-wide losses (underwriting plus investments). Event cancellation was 31% of Lloyd's COVID payouts. https://www.lloyds.com/insights/media-centre/press-releases/covid19-will-see-historic-losses-across-the-global-insurance-industry ; https://www.insurancebusinessmag.com/us/news/breaking-news/lloyds-coronavirus-payouts-focusing-on-three-areas-of-insurance-225596.aspx
- BlueDot flagged Wuhan on Dec 31, 2019: 6 days before CDC, 9 days before WHO. https://www.cnbc.com/2020/03/03/bluedot-used-artificial-intelligence-to-predict-coronavirus-spread.html
- Dataminr: 1M+ public sources, 150+ languages; has an insurance use case (underwriting, FNOL). https://www.dataminr.com/use-cases/insurance/
- Moody's RMS Event Response: HWind footprints every 6 hours. https://www.moodys.com/web/en/us/capabilities/catastrophe-modeling/event-response-services.html
- WHO EIOS: open-source epidemic intelligence used by 120 countries (public-health audience, not insurers). https://www.who.int/initiatives/eios
- Everstream: supply-chain risk alerts on a customer's supplier network (shippers, not insurance books). https://www.everstream.ai/platform/global-monitoring/
- Munich Re: H1 2025 insured nat-cat losses of $80B, 95% above the 10-year average. https://www.artemis.bm/news/munich-re-pegs-h1-global-insured-catastrophe-losses-at-80bn-95-higher-than-10-yr-avg/
