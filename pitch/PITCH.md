# Sentinel: the 3-minute pitch

Spoken script, matched to `pitch/deck.html` slide by slide. About 460 words at a calm pace, which is 3:00 with the demo beats. [Brackets] are stage directions. Every number is sourced in the table at the bottom and in the footer of the slide it appears on. Before you say a storm name, check it on nhc.noaa.gov.

Open the deck at slide 1 in fullscreen (press F). Have the live UI open in a second tab at https://sentinel-chubb.vercel.app on the Property lens with nothing selected.

---

## 0:00 – 0:25 · Slide 1 · Cold open

[Silence for one beat. Look at the judges, not the screen.]

"Tuesday, July 15th, 2025. 2:49 in the afternoon in Foshan, China. A district health bureau posts a notice. Four hundred and seventy-eight cases of chikungunya. It's in Chinese. Nobody outside China reads it.

Fifty-one hours later, the first English headline. Nine days later, Bloomberg.

And every insurer with travel, A&H or supply-chain exposure in Guangdong found out from Bloomberg."

## 0:25 – 0:45 · Slide 2 · The pattern

"That is always how it goes. The LA wildfires were public from the first hour; Chubb took $1.47 billion in one quarter. Helene and Milton sat in Hurricane Center advisories for days; about $700 million. $137 billion of insured cat losses worldwide in 2024.

The signal is always public. The problem is that nobody connects it to *our book* in time."

## 0:45 – 1:05 · Slide 3 · The insight

"Here's the thing we figured out. Detection is a solved problem. Dataminr, BlueDot, GDACS. Chubb already pays for it.

What nobody ships is the last mile. Signal, to *our* exposure, to a *decision*, to the *right desk*, with an audit trail an underwriter will actually trust.

So we built that."

## 1:05 – 1:15 · Slide 4 · Sentinel

"This is Sentinel. Live, today, a real storm. One screen: three-point-four-eight billion at stake, four decisions. Let me show you."

[Switch to the live UI tab.]

## 1:15 – 2:00 · Live demo

[UI on Property lens. Point at the big number.]
"Not a news feed. A number and a list of decisions."

[Click **Hurricane Polo**.]
"Top decision: Hurricane Polo. Category 5, 180 miles an hour, and that's *issued by the Hurricane Center*. We copy severity; the model never invents it. 62 of our sites and $1.52 billion sit inside the 350-kilometre screening buffer. Nothing in the hurricane-force core yet. So the action is: restrict new binding in Baja California Sur. Not touch reserves. That's the sentence the cat desk needs at 6 a.m."

[Click any sentence in the brief to reveal its quote.]
"Every sentence carries a verbatim quote, and code, not a model, checks it against the source. No quote, no claim."

[Click **A&H** in the lens bar.]
"Same event data, a different desk. The head of A&H sees insured lives: 3,728 in the Ebola provinces, where WHO rates the risk very high."

[Click **•••** → **Route**.]
"And each desk has already been notified on its own channel, with a caveat banner."

[Click **•••** → **Run log**.]
"It's been running every ten minutes all afternoon."

[Switch back to the deck, slide 5.]

## 2:00 – 2:15 · Slide 5 · Trust

"Three rules the model never gets to break. Severity is copied from the authority. No quote, no claim. And the score shows its math."

[Advance to slide 6, hold for four seconds, don't narrate the boxes.]
"Nine agents. The language model reads and writes prose. Plain code holds every gate."

## 2:15 – 2:35 · Slide 7 · Proof

"Does it beat the headlines? We replayed Foshan with the original timestamps. Under our strict rule, two independent outlets plus an authority or a second language, Sentinel fires 18 hours before the first English headline and about eight days before Bloomberg. The first Chinese signal was on the watch list 51 hours out. One replay, fully sourced, reproducible from the repo."

[If time is short, press **B** in the UI instead of narrating this slide: the backtest modal shows the same timeline.]

## 2:35 – 2:50 · Slide 8 · Why now, why Chubb

"Why now? Chubb's own shareholder letter says it's investing in data and AI to get faster in underwriting and claims. And a language model can now read a Chinese bulletin and an NHC advisory in one pass, for cents. Sentinel sits on top of the feeds Chubb already buys, inside Chubb's own cloud. Exposure data never leaves."

## 2:50 – 3:00 · Slides 9 → 10 · The ask, the close

"The ask: a 90-day pilot with the cat desk. One peril, Chubb's real exposure file, measured in hours of lead time."

[Advance to slide 10. Pause.]

"Next time a health bureau posts a notice at 2:49 on a Tuesday, Chubb will know by 3. Thank you."

---

## 90-second version (time cut, or demo unavailable)

Slides 1 → 3 → 4 → 7 → 10.

"July 15th, 2025, 2:49 p.m. A health bureau in Foshan posts a notice in Chinese: 478 cases of chikungunya. The first English headline came 51 hours later. Bloomberg, nine days later. That's when insurers found out. [slide 3] Detection is solved; Dataminr and GDACS do it. The unsolved part is the last mile: signal, to our exposure, to a decision, to the right desk, with an audit trail. [slide 4] Sentinel is that last mile, live today: $3.48 billion at stake, four decisions. Top one, Hurricane Polo, Category 5 issued by NHC, 62 sites and $1.52 billion of our book in the screening buffer, action: restrict new binding in Baja California Sur. Severity is copied from the authority, every sentence carries a quote that code verifies, the score shows its math. [slide 7] Replayed on Foshan, it fires 18 hours before the first English headline and about eight days before Bloomberg. [slide 10] We're asking for a 90-day pilot with the cat desk on one peril. Next time a health bureau posts at 2:49 on a Tuesday, Chubb knows by 3."

---

## Sources for every number in the script and deck

| Claim | Source |
|---|---|
| Foshan: 478 cases announced 15 Jul 2025 by Shunde District Health Bureau; notice quoted in Chinese press 2025-07-15 (06:49 UTC Sina, 08:40 UTC chinanews) | https://www.chinanews.com.cn/dwq/2025/07-15/10448173.shtml ; https://finance.sina.cn/2025-07-15/detail-inffpsmp5615123.d.html ; sentinel/BACKTEST.md |
| 2:49 p.m. local = 06:49:17 UTC, 15 Jul 2025 (UTC+8); 15 Jul 2025 was a Tuesday | sentinel/BACKTEST.md timeline |
| First English mainstream headline: SCMP, 2025-07-17 10:00 UTC (T); first Chinese signal T−51.2 h | sentinel/BACKTEST.md |
| Bloomberg 2025-07-24 (T+165 h, ~9 days after the notice, ~8 days / 183 h after Sentinel's strict alert) | https://www.bloomberg.com/news/articles/2025-07-24/china-industrial-hub-sees-record-chikungunya-virus-outbreak ; sentinel/BACKTEST.md |
| Sentinel strict-rule alert at T−18.0 h (HK CHP letter 2025-07-16 + 2 outlets, 2 languages) | https://www.chp.gov.hk/files/pdf/letters_to_doctors_20250716.pdf ; `python3 src/backtest.py --strict` |
| 4,824 confirmed cases in Guangdong by 26 Jul 2025, 98.5% in Foshan | https://pmc.ncbi.nlm.nih.gov/articles/PMC12361914/ |
| Chubb Q1 2025: $1.47B pre-tax from California wildfires ($1.64B total cat) | https://news.chubb.com/2025-04-22-Chubb-Reports-First-Quarter-Per-Share-Net-Income-and-Core-Operating-Income-of-3-29-and-3-68,-Respectively-Consolidated-Net-Premiums-Written-of-12-6-Billion,-Up-5-7-in-Constant-Dollars,-with-P-C-and-Life-Insurance-Up-5-0-and-10-3-P-C-Combined-Ra |
| Chubb: Helene $390M + Milton $309M (2024) ≈ $700M | Chubb 10-K FY2024: https://www.sec.gov/Archives/edgar/data/896159/000089615925000004/cb-20241231.htm |
| $137B global insured nat-cat losses 2024 | Swiss Re sigma 1/2025: https://www.swissre.com/institute/research/sigma-research/sigma-2025-01-natural-catastrophes-trend.html |
| 2025: sixth year above $100B | https://www.swissre.com/press-release/2025-marks-sixth-year-insured-natural-catastrophe-losses-exceed-USD-100-billion-finds-Swiss-Re-Institute/f710c271-58c8-4c48-9004-05203634d1e0 |
| Dataminr: 1M+ public sources, 150+ languages | https://www.dataminr.com/use-cases/insurance/ |
| WHO EIOS; GDACS | https://www.who.int/initiatives/eios ; https://www.gdacs.org |
| Moody's RMS Event Response: HWind footprints every 6 h | https://www.moodys.com/web/en/us/capabilities/catastrophe-modeling/event-response-services.html |
| Chubb investing in data/AI for speed in underwriting and claims | 2025 Letter to Shareholders: https://about.chubb.com/stories/2025-chubb-letter-to-shareholders.html |
| Binding moratoriums typically 24–48 h before impact | https://www.policygenius.com/homeowners-insurance/insurance-moratorium/ |
| Live UI numbers today: $3.48B at stake, 4 decisions; Polo Cat 5 / 180 mph (NHC); 62 sites / $1.52B in 350 km buffer, none in core; Ebola DRC WHO risk "very high", 3,728 insured lives | https://sentinel-chubb.vercel.app (synthetic book; feeds, severity and quotes real) |
| Cycle cost under $1; a few dollars a day at 10-min cadence | pitch/QA.md Q5 |
