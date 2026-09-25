# Backtest: Foshan chikungunya outbreak, July 2025

**Headline (strict replay, the number we quote):** First weak signal T−51.2 h · **Sentinel alert T−18.0 h** · Mainstream headline T (SCMP, 2025-07-17 10:00 UTC). That's **~8 days (183 h) before the first global newswire** (Bloomberg, 24 Jul).
The lenient replay also counts the day-precision health-bureau notice, which puts the alert at T−51.2 h, about 9 days before Bloomberg. We treat 51 h as an upper bound and don't headline it (see Caveats).
Reproduce it with `python3 src/backtest.py` (and `--strict`). The input is `data/backtest_foshan_chikungunya_2025.json` and the output goes to `log/backtest.json` and `ui/data/backtest.json`.

## The event
On 15 Jul 2025 the Shunde District Health Bureau (Foshan, Guangdong) announced a local chikungunya outbreak. It had been detected on 8 Jul and had reached 478 confirmed cases, centred on Lecong, Beijiao and Chencun ([chinanews](https://www.chinanews.com.cn/dwq/2025/07-15/10448173.shtml)). By 26 Jul Guangdong had 4,824 confirmed cases, 98.5% of them in Foshan ([China CDC Weekly / PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12361914/)). It was China's largest chikungunya outbreak on record. For about 48 hours it was covered only in Chinese.

## Why an insurer cares
- **Commercial property BI/CBI, a watch item.** Beijiao, one of the epicentre towns, is home to Midea Group's global headquarters ([Wikipedia](https://en.wikipedia.org/wiki/Midea_Group)). Shunde is an appliance and furniture manufacturing hub. Mosquito-control campaigns and absenteeism there are a supply-chain signal.
- **A&H and travel.** The US CDC later issued a Level 2 travel notice for Guangdong ([CBS News](https://www.cbsnews.com/news/us-warns-travelers-chikungunya-virus-mosquitoes-china/); we did not verify the exact date). Hong Kong's CHP alerted clinicians on 16 Jul ([CHP](https://www.chp.gov.hk/files/pdf/letters_to_doctors_20250716.pdf)). Macao recorded imported cases ([info.gov.hk](https://www.info.gov.hk/gia/general/202508/01/P2025080100717.htm)).
- **Honest scale.** All cases were mild and no deaths were reported. There is **no public insured-loss estimate**. This is a frequency, travel and CBI early-warning case, not a severity cat. The value is that an underwriting or travel desk hears about it on 15 Jul instead of 24 Jul.

## Timeline (UTC; T = first English mainstream headline)
| ts (UTC) | vs T | kind | source | lang |
|---|---|---|---|---|
| 2025-07-15 06:49:17 | T−51.2 h | authority | [Shunde District Health Bureau notice (GD CDC repost)](https://cdcp.gd.gov.cn/ywdt/zdzt/yfjkkyr/yqxx/content/post_4747600.html) †day, derived | zh |
| 2025-07-15 06:49:17 | T−51.2 h | weak_signal | [Sina Finance](https://finance.sina.cn/2025-07-15/detail-inffpsmp5615123.d.html) (og:published_time) | zh |
| **2025-07-15 06:49:17** | **T−51.2 h** | **sentinel_alert** | 2 outlets + authority → rule fires | zh |
| 2025-07-15 08:40:58 | T−49.3 h | weak_signal | [China News Service](https://www.chinanews.com.cn/dwq/2025/07-15/10448173.shtml) | zh |
| 2025-07-15 09:58:00 | T−48.0 h | weak_signal | [HK China News Agency](https://www.hkcna.hk/docDetail.jsp?id=101054687&channel=2813) | zh |
| 2025-07-15 10:52:54 | T−47.1 h | weak_signal | [Nandu (Southern Metropolis) Foshan desk](https://m.mp.oeeee.com/a/BAAFRD0000202507151103164.html) | zh |
| 2025-07-15 14:06:00 | T−43.9 h | weak_signal | [Beijing News](https://www.bjnews.com.cn/detail/1752586217129154.html) (topic trending on Weibo) | zh |
| 2025-07-16 15:59:59 | T−18.0 h | authority | [HK CHP letter to doctors](https://www.chp.gov.hk/files/pdf/letters_to_doctors_20250716.pdf) †day, end-of-day | en |
| 2025-07-17 10:00:00 | **T** | mainstream | [South China Morning Post](https://www.scmp.com/news/hong-kong/health-environment/article/3318608/hong-kong-risk-imported-cases-mosquito-borne-chikungunya-fever-experts) | en |
| 2025-07-24 07:00:00 | T+165.0 h | mainstream | [Bloomberg](https://www.bloomberg.com/news/articles/2025-07-24/china-industrial-hub-sees-record-chikungunya-virus-outbreak) †GDELT first-seen | en |
| 2025-07-25 17:30:00 | T+199.5 h | mainstream | [AP (via therecord.com)](https://www.therecord.com/life/health-wellness/southern-china-hit-by-outbreak-of-mosquito-borne-infection-chikungunya/article_3485efd9-5c4d-5b54-b5e0-c0c00d121cf4.html) †GDELT first-seen | en |

Rows without † have hour, minute or second precision, taken from the page's own metadata and converted from UTC+8.

## Method
Each item's timestamp comes from its publisher's page metadata where we could retrieve it. Otherwise it is GDELT DOC 2.0 `seendate`, which is an upper bound with 15-minute resolution. To find the first English and first Chinese coverage we ran GDELT queries for 1–28 Jul 2025 sorted ascending by date. `src/backtest.py` replays the items in timestamp order through the live corroboration rule: at least 2 distinct outlets, plus either an authority item or at least 2 languages. Mainstream items never count toward the alert.

## Caveats
- The lead time is measured from **public disclosure**. Detection happened on 8 Jul, and we found no public, timestamped signal before 15 Jul.
- The Shunde notice has day precision, so its timestamp is bounded by the Sina report that quotes it. Its GD CDC repost URL now returns 404, although the text is quoted verbatim by chinanews. **Strict replay** ignores that derived timestamp. The alert then fires only when the English CHP letter adds an authority and a second language, which gives **T−18.0 h**. Sina's 51.2 h lead is fully verified. The authority's timing is not independently verified.
- The Chinese outlets largely relay the same official notice. They are distinct outlets, not independent investigations.
- "Mainstream" means the first English article by a major outlet in GDELT's index. We did not find an earlier English article, but GDELT's index does not cover every outlet.

## Candidates rejected
- **DRC Ebola (Bundibugyo), May 2026.** WHO was alerted on 5 May, but the first local-language report we could timestamp was [Radio Okapi](https://www.radiookapi.net/2026/05/15/actualite/sante/ituri-une-maladie-non-identifiee-inquiete-mungwalu-plusieurs-deces), published 15 May at 06:26 local time. Africa CDC and English wires followed at about 07:00 UTC (GDELT). That leaves a lead of about 1–2 h from a single source, so the rule would not have fired. The 5 May social-media rumours have no citable URL.
- **Hurricane Melissa 2025.** Not verified within the time box. (Hurricane Otis 2023 was subsequently verified and is the second case below.)
- **Wuhan, Dec 2019.** The case is famous, but English wires reportedly carried it on 31 Dec, within about a day of the ProMED and Weibo signals. We did not verify it this session, and the story is overused.


---

# Backtest 2: Hurricane Otis, Acapulco, October 2023 (nat-cat / property)

**Headline:** First weak signal T−24.2 h · **Sentinel alert T−14.7 h** · Mainstream headline T (CNN "Category 5 'nightmare scenario'", 2023-10-25 03:10 UTC). Measured against landfall (06:25 UTC) the alert is **18.0 h early**; against the first AP damage story (PBS, 14:45 UTC) it is 26.3 h early. Strict replay gives the same numbers.
Reproduce it with `python3 src/backtest.py --input data/backtest_otis_acapulco_2023.json` (and `--strict`). Output goes to `log/backtest_natcat-otis-acapulco-2023.json` and `ui/data/backtest_natcat-otis-acapulco-2023.json`; `ui/data/backtests.json` indexes both cases.

## The event
At 10 PM CDT on Monday 23 Oct the NHC forecast Otis to reach the coast "near hurricane strength" in 36–48 h and wrote that "none of the models show" rapid intensification ([Discussion 7](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.007.shtml)). Over the following 24 h Otis went from a 65-mph tropical storm to a 165-mph Category 5 and made landfall at Acapulco at 06:25 UTC on 25 Oct, the strongest landfall on record on Mexico's Pacific coast ([Discussion 13](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.013.shtml)). NHC's own words as the day went on: "1 in 4 chance of rapid strengthening" (4 AM), "greater than normal probability of RI" (10 AM), "RAPIDLY STRENGTHENS INTO A MAJOR HURRICANE" (4 PM), "potentially catastrophic Category 5" (7 PM), "A nightmare scenario is unfolding" (10 PM). CNN, ten minutes after that last advisory: "Otis was not forecast to become a hurricane until early Tuesday morning, a little more than 24 hours before it would make its unprecedented Category 5 landfall" ([CNN](https://edition.cnn.com/2023/10/24/weather/hurricane-otis-acapulco-mexico/)).

## Why an insurer cares
- **Property cat, high-rise hotel exposure.** Moody's RMS: private-market insured loss **US$2.5–4.5 bn**, "driven by wind damage", largely modern high-rise hotels and apartments on Acapulco Bay ([Moody's RMS, 13 Nov 2023](https://www.moodys.com/web/en/us/insights/announcements/moodys-rms-estimates-us25-billion-to-us45-billion-in-insured-losses-from-hurricane-otis.html); [Insurance Journal, 15 Nov 2023](https://www.insurancejournal.com/news/international/2023/11/15/748359.htm)). Verisk US$3–6 bn; AM Best US$1.8–6.5 bn ([Artemis](https://www.artemis.bm/news/hurricane-otis-insured-loss-estimated-up-to-us-6-5bn-am-best/)); CoreLogic US$10–15 bn insurable wind loss. Economic loss ~US$12–16 bn, the costliest cyclone in Mexican history.
- **Mexican market.** AMIS began loss adjustment on 31 Oct ([Expansión](https://expansion.mx/economia/2023/10/31/amis-plan-atencion-acapulco-otis)) and by 16 Nov reported MXN 11,424 m to be paid on 12,035 claims, 49% property / 51% auto ([Proceso](https://www.proceso.com.mx/economia/2023/11/16/aseguradoras-desembolsaran-unos-11-mil-424-mdp-por-los-danos-que-dejo-otis-en-guerrero-amis-317582.html)); later AMIS updates put insured damage at MXN 37,384 m.
- **The operational gap.** With a tropical-storm forecast on Monday night, nobody restricts binding for Guerrero or pre-positions adjusters. Sentinel's alert at 12:26 UTC Tuesday (07:26 Acapulco) comes while NHC's public product still says "tropical storm", and 8.5 h before NHC first says "major hurricane". That is the window for a bind moratorium, a cat-team stand-up and adjuster staging in Mexico City.

## Timeline (UTC; T = first English mainstream "Category 5" headline)
| ts (UTC) | vs T | kind | source | lang |
|---|---|---|---|---|
| 2023-10-24 03:00:00 | T−24.2 h | authority | [NHC Discussion 7](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.007.shtml): "near hurricane strength at landfall", "none of the models show" RI | en |
| 2023-10-24 09:00:00 | T−18.2 h | authority | [NHC Discussion 8](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.008.shtml): "1 in 4 chance of rapid strengthening" | en |
| 2023-10-24 12:26:00 | T−14.7 h | weak_signal | [MVS Noticias](https://mvsnoticias.com/nacional/2023/10/24/otis-se-intensifica-huracan-categoria-1-sigue-aqui-su-trayectoria-607103.html): "Otis se intensifica a huracán categoría 1" | es |
| **2023-10-24 12:26:00** | **T−14.7 h** | **sentinel_alert** | 2 outlets + authority → rule fires (18.0 h before landfall) | multi |
| 2023-10-24 15:00:00 | T−12.2 h | authority | [NHC Discussion 9](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.009.shtml): "greater than normal probability of RI" | en |
| 2023-10-24 20:54:37 | T−6.3 h | weak_signal | [Telemundo](https://www.telemundo.com/noticias/noticias-telemundo/clima/otis-se-convierte-en-huracan-en-el-pacifico-y-avanza-hacia-acapulco-rcna122001) (page later updated to "categoría 5") | es |
| 2023-10-24 21:00:00 | T−6.2 h | authority | [NHC Advisory 10](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.public.010.shtml): "RAPIDLY STRENGTHENS INTO A MAJOR HURRICANE… CATEGORY 4 AT LANDFALL" | en |
| 2023-10-24 21:27:00 | T−5.7 h | weak_signal | [MVS Noticias live blog](https://mvsnoticias.com/nacional/2023/10/24/huracan-otis-ya-es-categoria-5-sigue-su-trayectoria-en-vivo-607200.html) (created at Cat 3, updated to Cat 5) | es |
| 2023-10-25 00:00:00 | T−3.2 h | authority | [Guerrero Protección Civil](https://www.guerrero.gob.mx/2023/10/huracan-otis-alcanzo-la-categoria-tres-frente-a-las-costas-de-guerrero/): "alcanzó la categoría tres" †day, derived | es |
| 2023-10-25 00:00:00 | T−3.2 h | authority | [NHC Special Advisory 11](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.011.shtml): "potentially catastrophic Category 5" | en |
| 2023-10-25 03:00:00 | T−0.2 h | authority | [NHC Discussion 12](https://www.nhc.noaa.gov/archive/2023/ep18/ep182023.discus.012.shtml): "A nightmare scenario is unfolding" | en |
| 2023-10-25 03:10:19 | **T** | mainstream | [CNN](https://edition.cnn.com/2023/10/24/weather/hurricane-otis-acapulco-mexico/): "strikes Acapulco as Category 5 'nightmare scenario'" | en |
| 2023-10-25 06:25 | T+3.2 h | (landfall) | NHC TCR / Discussion 13 | — |
| 2023-10-25 14:45:20 | T+11.6 h | mainstream | [AP via PBS](https://www.pbs.org/newshour/world/hurricane-otis-weakens-over-southern-mexico-after-battering-acapulco-as-a-category-5-storm): damage story | en |
| 2023-10-31 20:17:04 | T+6.7 d | weak_signal | [Expansión](https://expansion.mx/economia/2023/10/31/amis-plan-atencion-acapulco-otis): AMIS starts loss adjustment | es |
| 2023-11-15 15:08:29 | T+21.5 d | mainstream | [Insurance Journal](https://www.insurancejournal.com/news/international/2023/11/15/748359.htm): insured loss US$2.5–6 bn | en |
| 2023-11-16 15:12:00 | T+22.5 d | weak_signal | [Proceso](https://www.proceso.com.mx/economia/2023/11/16/aseguradoras-desembolsaran-unos-11-mil-424-mdp-por-los-danos-que-dejo-otis-en-guerrero-amis-317582.html): AMIS MXN 11,424 m | es |

NHC times are the issue times printed in the archived product headers (CDT = UTC−5). Press times are `article:published_time` / `datePublished` from each page's metadata. Rows without † are exact.

## Caveats
- **This is a forecast-gap case, not a hidden-event case.** NHC publicly forecast a hurricane 24 h before landfall. What was hidden was the magnitude: tropical storm / Cat 1 in the morning products, Cat 5 at landfall. The corroborator fires on NHC's first rapid-intensification language plus a second (Spanish) outlet; it does not predict Cat 5.
- **Against NHC's own "catastrophic" wording the lead is smaller.** NHC said "potentially catastrophic Category 5" at 00:00 UTC and "nightmare scenario" at 03:00 UTC; CNN followed within 10 minutes. The 14.7 h is against the first English mainstream headline, and 18.0 h against landfall.
- **Earlier English wire copy existed.** An AP running story (NPR, `datePublished` 2023-10-24 22:48 UTC, original slug "tropical storm otis forecast to strengthen to hurricane") was updated in place. Its original headline did not say Category 5, so it is not "mainstream" under our definition; counting it would make the lead 10.4 h.
- **Live-blog headline drift.** The Telemundo and MVS pages carry their creation time but their headlines were updated during the evening; original headlines are inferred from URL slugs.
- **Conagua/SMN press releases** (Aviso087-23, Aviso090-23, Comunicado0784-23) returned an error page on 2026-09-25, so no Conagua item is included. The Guerrero Protección Civil notice has day precision and is placed at its latest possible time (strict replay drops it; the alert time is unchanged).
- **Insured-loss figures are modellers' ranges** (US$1.8–15 bn depending on vendor and scope) and AMIS running totals; we did not reconcile them.
