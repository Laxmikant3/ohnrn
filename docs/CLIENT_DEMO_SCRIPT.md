# WindIQ — Client Demo Script

**Audience:** day-ahead procurement leads, trading analysts, risk.
**Duration:** 15 minutes (10-minute version noted inline).
**Goal:** show that WindIQ answers one question well — *how good was the wind forecast we actually had when we had to decide?* — and that the answer is auditable.

**Before you start**

- Backend: `cd backend && .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`
- Frontend: `cd frontend && npm run dev` → open `http://localhost:5173`
- Confirm the Overview loads and the top bar shows **Historical analysis**, **Cutoff 11:00 Europe/London · D−1**.
- Keep the browser zoom at 100% and the window at least 1280 px wide for the dense tables.
- Do **not** claim a hosted URL. Say "running locally against the verified Elexon cache."

---

## 0. Framing (1 minute)

> "You buy wind day-ahead. The only forecast that matters for that decision is the one published before your cutoff — not the one that was right with hindsight.
>
> WindIQ takes Elexon's published wind forecast and Elexon's actual wind outturn for January 2026, and evaluates every half hour using **only the latest forecast available at 11:00 the day before**. Later publications are kept for context but never used in the decision numbers.
>
> Two data sources, nothing else: FUELHH wind actuals and WINDFOR forecasts. No prices, no demand, no weather."

Set the expectation: "This is a diagnostic, not a trading system. It tells you how wrong the forecast was, in which direction, and when — it does not tell you what to trade."

---

## 1. Overview — the headline (3 minutes)

**Open `/`.**

Point at the KPI row, left to right:

1. **MAE 2,126 MW** — "On a typical half hour, the decision forecast missed actual wind by about 2.1 GW."
2. **RMSE 2,621 MW** — "A bit above MAE, so the misses are not all small; there are some large ones."
3. **Bias +1,840 MW** — "This is the one that matters commercially. Positive means overforecast. The forecast ran **high by 1.8 GW on average** across the month."
4. **MAPE 22.1%** and **WAPE 18.4%** — "Percentage views. WAPE is the volume-weighted one; it is the fairer aggregate because wind output goes near zero."
5. **Coverage 100%** — "1,488 of 1,488 expected half hours had both a forecast available at the cutoff and an actual. No gaps dressed up as results."

Then the chart: forecast line versus actual line across January.

> "You can see the character of the month: the forecast tracks shape but sits persistently above outturn, and the gap widens in the high-wind periods."

Scroll to the daily error panel:

> "Every bar is a London delivery day. The worst days are where the forecast over-committed. If you were buying against this forecast, those are the days that cost you."

**If short on time:** do only KPIs + bias sentence, then move on.

---

## 2. Forecast Explorer — the audit trail (3 minutes)

**Open `/forecasts`.**

> "Every half hour in the month is a row. This is the receipt for the headline numbers."

- Point at the header badges: **1,488 rows**, **1,488 matched**, **Cutoff compliant: 100.0%**.
- Read one row aloud: 1 Jan, SP 1, forecast 19,466 MW published 31 Dec 09:30, actual 13,756 MW, error +5,710 MW.
- **Click the row.** The drawer opens.

> "Here is the full publication history for that single half hour: 16 publications. Twelve of them were on or before the 11:00 cutoff and were eligible. The four after are greyed out as retrospective — we can see them, but they are not in the decision number."

- Point at **Decision forecast 19,466** vs **Actual 13,756**.
- Close with **Escape**.

Now demonstrate filtering:

- Set **Lead time → 12–18 h**. Header becomes **217 rows**.
  > "This is the slice that was published 12 to 18 hours before delivery — the freshest information a D−1 11:00 cutoff can give you for the early hours."
- Reset, then type `2026-01-12` in search → 48 rows.
  > "Search is interval-level, so you can go straight to a date that mattered."
- Click **Export filtered CSV**.
  > "The export carries the same filters, plus provenance: publish time, lead time, cutoff instant, eligibility and a synthetic-data flag. Your analyst can reconcile it in Excel."

Open the downloaded file if the audience is analytical: 49 lines, header + 48 rows, `synthetic=False`.

---

## 3. Accuracy Analysis — where and when it breaks (3 minutes)

**Open `/accuracy`.**

> "Same data, decomposed so you can act on it."

- **Daily error trend** — "Which days were bad."
- **Error distribution** — "Most half hours sit in the overforecast bins. This is not noise around zero; it is a shifted distribution."
- **Hour-of-day profile** — "Error is not flat across the day. [Read the highest and lowest hour from the panel.] That matters if your exposure is concentrated in particular settlement periods."
- **Heatmap** — "Date by hour. Darker is better, amber is worse. You can see persistent bands rather than random speckle."
- **Accuracy by lead time** — flag the honesty here:
  > "Only four buckets are populated: 12–18, 18–24, 24–36 and 36–48 hours. Under a fixed 11:00 D−1 cutoff, nothing can be published less than 12 hours ahead for the following day, so the shorter buckets are empty. We show them as empty, not as zero error."
- **Population accounting** — "Expected, selected, matched, missing forecast, missing actual, excluded by lead time. Every metric count reconciles."

If asked "is this good or bad?": "MAE of 2.1 GW against a mean forecast level around 13 GW is a material miss for procurement. The bias is the bigger issue — it is systematic, not random."

Use the **First half / Second half** preset to show the window narrowing to 720 paired intervals, then reset.

---

## 4. Forecast Revisions — the cost of waiting (2 minutes)

**Open `/revisions`.**

> "This page answers: how much did the forecast move between your decision and delivery?"

- **Intervals with vintages: 1,488** — every interval had a later publication.
- **Mean absolute revision: 978 MW** — "On a typical half hour, the forecast moved by about 1 GW after your cutoff."
- **Largest revision: 5,033 MW** — "One interval moved 5 GW."
- Point at the top row: **28 Jan, SP 36** — decision 10,839 MW → latest 5,806 MW, revision **−5,033 MW**, actual 5,540 MW.
  > "Your decision vintage said 10.8 GW. By delivery the forecast was 5.8 GW. Actual was 5.5 GW. If you had procured on the decision number, you were 5.3 GW long."
- **Click the row** to show the 22-vintage path; close it.

Read the amber notice aloud, because it protects credibility:

> "Vintages after the cutoff are shown for retrospective evaluation only. They were not available at decision time."

- **Revision curve** — "Movement shrinks as you get closer to delivery. That is the value of a later cutoff — but it is a different decision, and this page lets you price that trade-off rather than assume it."

---

## 5. Data Quality — why you can trust the numbers (2 minutes)

**Open `/data-quality`.**

> "Every figure on the previous screens traces back to this page."

- **Upstream connectivity** — live probe against Elexon, with latency. Say clearly: "The analysis is served from a verified cache, so a transient Elexon outage does not change the numbers you just saw."
- **Cache integrity** — two files, byte sizes, record counts, SHA-256 hashes. Click a hash to copy it.
- **Dataset composition** — 1,488 FUELHH actuals, 19,487 hourly WINDFOR source records from 1,051 source delivery intervals (2,102 expanded 30-minute rows), 336 distinct publication vintages.
- **Record accounting** — point at **Invalid 0**, **Duplicates 0**, **Missing actual 0**, **Missing forecast 0**.
  > "Post-delivery publications are excluded and counted separately — 5,041 of them. That is the cutoff rule doing its job, not a data error."
- **Coverage by delivery day** — 31 of 31 days complete.
- **Retrieval audit trail** — timestamp, endpoint, parameters, records, attempts, duration, status.
- **Re-probe** live with **Re-check upstream** if the client wants to see it.

Close this section with the governance line:

> "No synthetic rows. The page exposes `is_synthetic: false` and every record's provenance. If someone asks where a number came from, the answer is on this screen."

---

## 6. Methodology — the rules, in writing (1 minute)

**Open `/methodology`.**

Do not read it all. Click three anchors in the left-hand contents:

1. **Decision cutoff** — show the pseudocode and the inclusive boundary.
2. **Metric definitions** — "MAE and RMSE are MW, not accuracy percentages. MAPE excludes actuals below 1 MW, and we report how many were excluded."
3. **Limitations** — read the last line: "Not a trading system."

> "This is the page your risk and audit functions will want. It is generated from the same metadata the backend serves, so it cannot drift from the implementation."

---

## 7. Close (1 minute)

Summarise in three sentences:

1. "Using only information available at 11:00 D−1, Elexon's wind forecast missed actual outturn by **2.1 GW MAE** in January 2026, and it was **systematically high by 1.8 GW**."
2. "The error is not uniform — it clusters by day, by hour and by lead time, and the forecast moved by **~1 GW on average** after the decision point."
3. "Every number is traceable to a hashed Elexon cache, the cutoff is enforced in code and proven by tests, and the whole thing runs as two containers."

Then the honest caveats, stated proactively:

- "The 11:00 D−1 cutoff is our pilot assumption. Tell us your real deadline and it becomes a configuration change, not a rebuild."
- "This is January 2026 only. Extending the window is an ingestion job, not a redesign."
- "It is a diagnostic. It does not size trades."

**Ask for the next step:** confirm the real cutoff, confirm the decision cadence, and agree the next analysis window.

---

## Appendix A — Numbers to quote (default selection)

| Item | Value |
| --- | --- |
| Analysis period | 1–31 January 2026, Europe/London |
| Cutoff | 11:00 Europe/London, D−1 (pilot assumption) |
| Expected / matched intervals | 1,488 / 1,488 |
| Coverage | 100.0% |
| MAE | 2,126.12 MW |
| RMSE | 2,620.80 MW |
| Bias | +1,840.30 MW (overforecast) |
| MAPE | 22.13% (0 excluded at 1.0 MW threshold) |
| WAPE | 18.36% |
| Mean absolute revision | 977.92 MW |
| Largest revision | 5,033 MW (28 Jan SP 36) |
| Forecast vintages | 336 |

## Appendix B — Questions to expect

**"Why is coverage 100%? Real data is never complete."**
> "Coverage here means every expected settlement period has both an eligible forecast and an actual. January 2026 happened to be complete after post-delivery publications were excluded. The accounting still exposes missing and invalid counts, and the Data Quality page recomputes coverage per day so a partial day would be obvious."

**"Why are some lead-time buckets empty?"**
> "A fixed 11:00 D−1 cutoff cannot see a publication less than ~12 hours before delivery. The buckets are structurally empty, and we deliberately do not render them as zero error."

**"Is 22% MAPE bad?"**
> "MAPE is unstable for wind because output approaches zero. WAPE at 18.4% is the fairer aggregate. The more actionable number is the +1.8 GW bias — that is a systematic directional miss, not just dispersion."

**"Can we change the cutoff?"**
> "Yes — per request, and it is exposed in the filter bar. The default is a labelled assumption, not a hard-coded belief."

**"Where does the data come from?"**
> "Elexon BMRS FUELHH `fuelType=WIND` and WINDFOR, retrieved once, hashed with SHA-256, and served from cache. The retrieval audit trail is on the Data Quality page."

**"Is this live?"**
> "The analysis is historical. The only live element is the upstream reachability probe. We do not silently refresh data behind your back."
