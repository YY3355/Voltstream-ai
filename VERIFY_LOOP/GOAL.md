# GOAL — recover constraint-arc coverage via a curated ERCOT station crosswalk (before shelving)

Guardrail: MEASURED only, no invented locations. GATE unchanged: build UI only when COMPLETE
ARC-ROW placement >= 25%. Prior gate result: 33% station / 6.1% arc-row / 14.1% unique-constraint
/ 0 live arcs -> stopped. Now attempt recovery per the user's plan.

## Recovery plan (no UI until the gate clears)
1. **Frequency-ranked unmatched-code report** over a 90-day SCED window. Per unmatched code:
   (1) # constraint rows affected, (2) # unique counterpart stations, (3) voltage levels,
   (4) most common overloaded-element (ConstraintName), (5) most common contingency names,
   (6) likely duplicate aliases, (7) estimated complete-arc coverage gain if resolved.
2. **Alias normalization** — collapse LEONCRK/LEON_CRK/LEON CRK, strip bus/equip suffixes
   (MV_HBRG4, W_BATESV, S_MISSIN) where they denote one physical station.
3. **Curated crosswalk** (crosswalk.json), schema per code: station_code, canonical_name, lat,
   lon, voltage_kv, utility, county, source, confidence, review_status, aliases[]. Authoritative
   layer that takes PRECEDENCE over fuzzy matching in match_stations.
4. **Research the smallest set** of top-frequency codes to lift complete arc-row placement >=25%.
   Accept a coordinate ONLY with an ERCOT doc / utility|PUCT filing / two corroborating
   independent sources. Store provenance + confidence. NO city-name guesses. Do NOT loosen fuzzy
   matching.
5. **Re-run the gate after every batch** (station match, arc-row %, unique-constraint %, live).
   Build UI only after complete arc-row placement clears 25%.

## Assets
- substation_registry.py — HIFLD+OSM = 9,472 TX subs (committed b429160). data_archive/registry/
  (gitignored). data_archive/constraints/sced_90d.pkl — cached 90d NP6-86-CD (gitignored).
- constraint_arcs.py (staged, fixture-tested): parse_constraints / match_stations / build_arcs.

## Tasks
- **R1** constraint_report.py: 90d frequency-ranked unmatched-code report (the 7 fields) +
  alias-normalization candidates + estimated coverage gain. Verify: top-N codes ranked, coverage
  math checks out.
- **R2** crosswalk.json + wire it as an authoritative pre-match into the matching path
  (precedence over fuzzy; measured provenance/confidence). Verify: a curated code places its arc.
- **R3** Research + curate the smallest top-N set with verified coords (provenance/confidence);
  re-run gate after each batch. STOP-or-GO strictly on complete arc-row >=25%.
- **UI (T2/T3/T4)** only if the gate clears.

## Guardrails
- Max 12 iterations. Supervised. One task = one commit. Green commits only. NEVER a guessed
  coordinate; both-ends-or-no-arc; provenance+confidence on every crosswalk row.
