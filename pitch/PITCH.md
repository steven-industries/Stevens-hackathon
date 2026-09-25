# Sentinel: 3-minute pitch script

Speaker notes. About 430 spoken words at a calm pace. Bracketed text is a stage direction. Every number has a source in the table at the bottom. Before you say any storm name, check it on nhc.noaa.gov.

---

## 0:00–0:20 · Hook (slide 1 → 2)

"January 7th, 2025. A fire starts in the Pacific Palisades. Within days it's one of the costliest wildfire losses on record: about **$40 billion insured**.
For Chubb it came to **$1.47 billion pre-tax** in a single quarter.
The fire was public from the first hour. What didn't exist was an answer to one question: *how much of our book is inside that perimeter, right now?*"

## 0:20–0:45 · Problem (slide 2)

"That's not a one-off. Insured nat-cat losses were **$137 billion in 2024**, and in 2025 they topped $100 billion for the sixth year running. Helene and Milton together cost Chubb about **$700 million**.
The signals are all public: GDACS, the Hurricane Center, USGS, WHO outbreak notices, local news in Spanish, French, Portuguese, Hindi, Chinese. They arrive as noise, in ten formats and many languages. A person still has to stitch them together by hand."

## 0:45–1:05 · Who (slide 3)

"Here's who we built this for: **the accumulation manager on Chubb's cat desk, at 6 a.m.** Before the 8 o'clock call, they have to answer three things. What happened overnight? What do we have in the footprint? Who needs to know? Today that takes a dozen browser tabs, a cat-model run, and a spreadsheet emailed to the CUO."

## 1:05–2:10 · Live demo (slides 4–5, then switch to the UI)

"Sentinel is a team of agents that runs every ten minutes. [Show the architecture slide for 5 seconds, then switch to the live UI.]

1. **Morning brief.** [UI open on Property.] "This is the cat desk at 6 a.m. Not a news feed: *$3.5 billion at stake, four decisions.*"
2. **Top decision: Hurricane Polo.** "Category 5, 180 mph. That's *issued by NHC*: we copy severity, the AI never makes it up. Nine independent publishers in two languages. *62 of our sites and $1.52 billion* are inside the 350 km screening buffer, and nothing is in the hurricane-force core yet. So the recommended action is *restrict new binding in the watch area*, not *touch reserves*." [Point at the map: track, buffer, our sites.]
3. **Trust.** [Click a sentence in the brief to reveal its quote.] "Every sentence carries a verbatim quote, and **code** checks it against the source. No quote, no claim."
4. **Switch lens.** [Click A&H at the top.] "Same data, different desk. The head of A&H sees *insured lives*: 3,728 in the Ebola provinces, where WHO rates the risk very high." [••• → Route.] "And each desk has already been notified on its own channel, with a caveat banner."
5. **Always on.** [••• → Run log.] Every cycle this afternoon is logged."

## 2:10–2:30 · Backtest (slide 7)

"Does it work before the headlines? We replayed **the July 2025 Foshan chikungunya outbreak**, China's largest ever, using the original timestamps. For two days it existed **only in Chinese**: a district health-bureau notice, then Sina and China News. Under our strict rule (two independent sources, including an authority, in two languages) Sentinel fires **18 hours before the first English headline** and **about a week before Bloomberg**. The first Chinese signal came 51 hours before the English headline. For a travel or A&H desk, or anyone watching CBI on a manufacturing hub, that's the whole decision window."

## 2:30–2:50 · Why now + adoption (slide 8)

"Why now? Chubb's own shareholder letter says it's putting money into data and AI to get faster in underwriting and claims. Language models can finally read a Portuguese health bulletin and a USGS feed in the same pass, and cheaply.
We don't replace Dataminr or Moody's RMS. **They detect. We turn a detection into what it means for Chubb's book, with an audit trail and a brief routed to the right desk.** It runs inside Chubb's own cloud, so exposure data never leaves. The pilot is one peril and one region on Chubb's real exposure file, for 90 days, measured on hours of lead time and analyst hours saved."

## 2:50–3:00 · Close (slide 9)

"Every morning, someone at Chubb puts this together by hand. Sentinel has it done before they sit down, and every claim traces back to a quote. We're asking for a 90-day pilot with the cat desk. Thank you."

---

## 60-second fallback version (demo broken or time cut)

"In January 2025 the LA wildfires cost Chubb **$1.47 billion pre-tax** in one quarter. The signals were public from the first hour. What was missing was a fast answer to *how much of our book is exposed, and who needs to know?*
Sentinel is an always-on team of agents. It reads GDACS, the Hurricane Center, USGS, WHO and multilingual local news every ten minutes, and it only raises an alert once independent sources agree. It copies severity from the issuing authority and never invents it. Then it overlays the event on the insurer's book, as policies and TIV by line, and writes three briefs: Health, Wealth, and Insurance. Every bullet quotes its source, and code checks each quote word-for-word. Each brief goes to the right desk (the CUO, Claims, the CIO, A&H) with a caveat banner.
When we replayed the 2025 Foshan chikungunya outbreak, Sentinel alerted 18 hours before the first English headline and about a week before Bloomberg, because the early signals were only in Chinese.
Dataminr detects. Sentinel translates detection into Chubb's exposure, with an audit trail. It runs in Chubb's cloud. We're asking for a 90-day pilot on one peril with the cat desk."

---

## Demo checklist (30 seconds before going on)
- [ ] `python -m src.run --loop 600` has been running, with 3 or more cycles in the run log
- [ ] UI open at `http://localhost:8000/ui/`, top alert pre-selected
- [ ] Storm name and category checked on nhc.noaa.gov
- [ ] Offline cache warm (`--offline`) in case the Wi-Fi drops
- [ ] Say "synthetic book" out loud. Judges will respect it.

## Sources for every number in the script
| Claim | Source |
|---|---|
| LA wildfires about $40B insured losses | Munich Re H1 2025: https://www.munichre.com/en/company/media-relations/media-information-and-corporate-news/media-information/2025/natural-disaster-figures-first-half-2025.html ; https://www.artemis.bm/news/munich-re-pegs-h1-global-insured-catastrophe-losses-at-80bn-95-higher-than-10-yr-avg/ |
| Chubb Q1 2025: $1.64B pre-tax cat losses, $1.47B from California wildfires | Chubb Q1 2025 release: https://news.chubb.com/2025-04-22-Chubb-Reports-First-Quarter-Per-Share-Net-Income-and-Core-Operating-Income-of-3-29-and-3-68,-Respectively-Consolidated-Net-Premiums-Written-of-12-6-Billion,-Up-5-7-in-Constant-Dollars,-with-P-C-and-Life-Insurance-Up-5-0-and-10-3-P-C-Combined-Ra |
| $137B global insured nat-cat 2024 | Swiss Re sigma 1/2025: https://www.swissre.com/institute/research/sigma-research/sigma-2025-01-natural-catastrophes-trend.html |
| 2025 sixth year above $100B | Swiss Re press release: https://www.swissre.com/press-release/2025-marks-sixth-year-insured-natural-catastrophe-losses-exceed-USD-100-billion-finds-Swiss-Re-Institute/f710c271-58c8-4c48-9004-05203634d1e0 |
| Chubb: Helene $390M + Milton $309M (2024) | Chubb 10-K FY2024: https://www.sec.gov/Archives/edgar/data/896159/000089615925000004/cb-20241231.htm |
| Binding moratoriums 24–48h before impact | https://www.policygenius.com/homeowners-insurance/insurance-moratorium/ |
| Chubb investing in data/AI for speed in underwriting & claims | 2025 Letter to Shareholders: https://about.chubb.com/stories/2025-chubb-letter-to-shareholders.html |
