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
- **Hurricane Otis 2023 and Hurricane Melissa 2025.** The authority products (NHC advisories) were themselves the headline source, so any lead is a matter of hours. We did not verify these timelines within the time box.
- **Wuhan, Dec 2019.** The case is famous, but English wires reportedly carried it on 31 Dec, within about a day of the ProMED and Weibo signals. We did not verify it this session, and the story is overused.
