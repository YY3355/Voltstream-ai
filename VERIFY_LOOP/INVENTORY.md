# Task 1 — ERCOT forecast/outage product inventory (probed, not guessed)

Source: `ercot_catalog.py` SQLite (`data_archive/ercot.db`, 107 products) + live EMIL archive-listing
probes via `ercot_archiver.list_archive_docs` (creds from `~/.zshenv`). Retention = empirical (queried
the `/archive/{emil}` endpoint at date offsets; a day returning docs ⇒ retention reaches that far).
Vintage source: each archive doc carries `postDatetime` (ERCOT's publish/post time); the file's rows
carry the forecast TARGET period; capture adds our UTC timestamp — all three vintage parts available.
Format: CSV inside a per-doc zip (archiver's `download_doc` unzips + parses, adds `_postDatetime`/`_docId`).

## Inventory table

| Family | Product | ID | Cadence (post) | Retention (probed) | Avail @ 15:00 CT | Priority |
|---|---|---|---|---|---|---|
| **Wind** | Wind Power Prod — hourly actual+fcst (system) | **NP4-732-CD** | hourly (:55) | **≥2yr** (t-730 ✓) | yes (14:55 post) | HIGH |
| | Wind — by geographical region | NP4-742-CD | hourly (:55) | ≥2yr | yes | HIGH |
| | Wind forecasts by model | NP4-442-CD | hourly | ~2yr (assumed, sib.) | yes | MED |
| | Wind intra-hour by region | NP4-751-CD | ~5-min | **<1yr** (t-365=0) ⚡ | yes | LOW/opt |
| **Solar/PVGR** | Solar Power Prod — hourly actual+fcst (system) | **NP4-737-CD** | hourly (:55) | ≥2yr | yes | HIGH |
| | Solar — by geographical region | NP4-745-CD | hourly (:55) | ≥2yr | yes | HIGH |
| | Solar forecasts by model (168h future) | NP4-443-CD | hourly | ~2yr (assumed) | yes | MED |
| | Solar intra-hour by region | NP4-752-CD | ~5-min | <1yr ⚡ (sib. of 751) | yes | LOW/opt |
| **Load** | 7-Day Load Forecast by Forecast Zone (+system) | **NP3-560-CD** | hourly (:30) | ≥2yr | yes | HIGH |
| | 7-Day Load Forecast by Weather Zone | NP3-561-CD | hourly | ≥2yr (assumed) | yes | MED |
| | 7-Day Load Forecast by Model (which in use) | NP3-565-CD | hourly | ≥2yr (assumed) | yes | MED |
| | 7-Day Load Forecast by Study Area | NP3-566-CD | hourly | ≥2yr (assumed) | yes | MED |
| | Intra-Hour Load Forecast by Weather Zone | NP3-562-CD | ~5-min | <1yr ⚡ (assumed) | yes | LOW/opt |
| **Outages** | Hourly Resource Outage Capacity (HRUC) | **NP3-233-CD** | hourly (:00) | ≥2yr (t-730 ✓) | yes | HIGH |
| | Unplanned Resource Outages Report | **NP1-346-ER** | daily (~05:01, 1/day) | ≥2yr | **lagged t-3** | HIGH |
| | Planned Outage Capacity Margin 7-Day-Plus | NP3-161-CD | daily | ~2yr (assumed) | yes | MED |
| | Planned Outage Capacity Margin 7-Day | NP3-162-CD | hourly | ~2yr (assumed) | yes | MED |

Probed empirically: NP4-732/742, NP4-737, NP3-560, NP3-233 → docs at t-730d (≥2yr). NP1-346 → 1 doc/day
at t-730 (≥2yr). NP4-751 (intra-hour) → 0 docs at t-365 & t-730 (**<1yr — fastest-expiring**). Others
marked "assumed" inherit their sibling's retention pending a finer probe if we capture them.

## Flags / findings
- **Fastest-expiring = the intra-hour 5-min products** (NP4-751 confirmed <1yr; NP4-752 / NP3-562 the
  same family). The main HOURLY forecast + outage products have **≥2-year** archive retention — NOT
  expiring in days. So urgency is: (a) intra-hour races the clock; (b) the hourly products give a
  comfortable ~2yr backfill window AND ongoing capture preserves them past ERCOT's eventual drop.
- **NP1-346 has a 3-day LAG** (snapshot of unplanned outages active 3 days before posting) — a lagged
  input at decision time, not a forward forecast. Store it, but its features are decision-time-clean
  only for target days ≥ 3 days after the outage snapshot.
- All HIGH products post hourly at :30/:55/:00 ⇒ the pre-15:00-CT posting is available at the 15:00 CT
  decision, and each hourly forecast covers the forward window (7-day load, wind/solar forward incl.
  D+1). Decision-time-clean.

## Recommended capture set (for Mike to confirm before Task 2 builds)
- **HIGH (the decision-time feature ingredients):** NP4-732, NP4-742 (wind) · NP4-737, NP4-745 (solar) ·
  NP3-560, NP3-565 (load) · NP3-233 (HRUC), NP1-346 (unplanned outages). = 8 products.
- **MED (add if cheap):** NP4-442/443 (by-model wind/solar), NP3-561/566 (load zone/study), NP3-161/162
  (planned margin).
- **LOW/optional (fastest-expiring, high-frequency, big disk):** intra-hour NP4-751/752, NP3-562 — only
  if 5-min granularity is wanted; these are the ones truly racing retention.
