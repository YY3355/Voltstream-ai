# Store-seam continuity (belt-and-suspenders before Task 3)

The window rides `archive_cache/NP6-905` (RT) + `dart_cache/DAY_AHEAD_HOURLY` (DA); the deep
`locational/` (RT) + `dam_decade/` (DA) end ~2026-07-01. Do the window stores agree with their decade
siblings across the seam?

## RT — PROVEN to the cent ✓
`locational/HB_HOUSTON` vs `archive_cache/NP6-905` hourly mean, 3 overlapping June days:

| day | hours | max abs err | mean |
|---|---|---|---|
| 2026-06-15 | 24 | **0.0000** | 0.0000 |
| 2026-06-20 | 24 | **0.0000** | 0.0000 |
| 2026-06-25 | 24 | **0.0000** | 0.0000 |

RT convention is identical across the store seam.

## DA — same-day cent-match structurally impossible; validated another way
The two DA stores are **adjacent but non-overlapping** (dam_decade `≤ 2026-07-01`, dart_cache
`≥ 2026-07-02`), and **ERCOT's MIS no longer serves June DAM** (NP4-190 docs expire ~30 days;
gridstatus refetch of 2026-06-30 → `NoDataFoundException`, doc `ExpiredDate 2026-08-02`). So no shared
day exists to match, and June DAM can't be re-fetched. Instead:

1. **The DA used for window scoring is independently cent-proven.** `dart_cache/DAY_AHEAD_HOURLY` == ERCOT
   DAM settlement to **0.0000** — this is exactly what the sign gate showed (our_DA == their_da, 26/26
   hours). The realized truth the scoring rests on is validated.
2. **`dam_decade` is convention-continuous at the seam** (it feeds ONLY the deep climatology baseline, not
   the window realized values). Both stores are naive-indexed **CDT hour-beginning**; the seam is smooth:
   dam_decade 07-01 23:00 = 31.40 → dart_cache 07-02 00:00 = 27.76 (normal overnight decline, no offset
   jump); dam_decade shows the expected evening DA peak (06-30 peak 20:00 CDT).

**Bottom line:** RT continuity is cent-proven; the window realized DA is cent-proven (sign gate);
`dam_decade`'s absolute values can't be cent-matched (data expired) but are convention-continuous and
only affect the climatology baseline. This limitation is carried into NOTE.md.
