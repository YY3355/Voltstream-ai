# GOAL — county-outlined weather layer (replace county-heat fill), honest zone-at-county-resolution

Replace the map's county-heat (battery-MW) FILL with real Texas county polygons OUTLINED and
shaded by each county's ERCOT weather ZONE live temp + rain. No fake per-county weather — it's
8 zone readings mapped to counties, labeled as such. Sidebar battery-MW bar stays EXACTLY as-is.

## APIs / facts
- county_weather.build_county_weather(weather_result, county_zone=None) -> {counties[{county,
  zone,temp_f,precip_mm,raining,fill}], zones[], n_counties, label}; temp_color(f)->[r,g,b].
  COUNTY_ZONE currently ~64 counties — extend to all 254 (T2).
- weather_data.parse_openmeteo currently carries temp+wind; needs precip (T1). fetch params at
  weather_data.py:126-128 (current/hourly "temperature_2m,wind_speed_10m").
- Map: the REG 'county' layer (dashboard_live.html:1588) is a ScatterplotLayer of allCounties
  (battery MW), default ON. Its ⓘ caveat @1567. Sidebar #county-panel (battery MW list) reads
  allCounties from /api/countyheat — KEEP UNTOUCHED. geo cache: data_archive/geo/.

## Tasks (commit each)
- **T1 PRECIP**: add "precipitation" to Open-Meteo current+hourly params in weather_data.py;
  carry precip_mm into each zone record in parse_openmeteo. Keep everything else identical.
  Verify: weather_data fixture passes; run_weather zones have precip_mm.
- **T2 POLYGONS + ZONES**: fetch real TX county boundaries (US Census cartographic county
  GeoJSON, state FIPS 48) -> cache data_archive/geo/tx_counties.geojson. Extend county_weather.
  COUNTY_ZONE to all 254 TX counties from ERCOT's authoritative weather-zone-to-county list.
  Ambiguous counties: leave UNCOLORED (out of COUNTY_ZONE), report which. Verify: geojson has
  ~254 TX county features; COUNTY_ZONE covers ~254 (report any omitted).
- **T3 /api/countyweather**: run_weather() -> build_county_weather(); serve counties+zones+
  label. Honest error passthrough. Verify: 200, ~254 counties, label present.
- **T4 MAP**: replace the county-heat fill with a deck.gl GeoJsonLayer of county polygons —
  every county OUTLINED (thin stroke), filled by build_county_weather fill (temp ramp; blue
  where raining), ~50-60% opacity so the basemap reads through. KEEP the sidebar county-MW bar
  exactly as-is (do not touch #county-panel / allCounties). Replace the old county ⓘ caveat with
  the new label verbatim. Legend: temp ramp + rain swatch, noted "zone weather at county
  resolution". Verify: counties outlined+shaded, rain blue, hotter zones redder, sidebar
  MW-bar unchanged, label present.
- **T5 REVEAL**: keep in the progressive-reveal system (default-on or one toggle, matching the
  calm-default redesign). Verify default view still calm; screenshots.

## Definition of done
- /api/countyweather 200 with ~254 counties + label.
- Map: TX counties outlined + zone-weather shaded (rain blue, hotter redder), basemap reads
  through; sidebar battery-MW bar identical to before; new label verbatim; legend has temp+rain.
- Other tabs untouched. Pushed when green; redeploy Fly.

## Verify (CDP + SCREENSHOTS — visual)
- weather/county_weather fixtures pass. curl /api/countyweather 200 ~254.
- CDP /#map: GeoJsonLayer 'county' present with ~254 polygon features; a hot county redder than
  a cool one; raining county blue; #county-panel MW list unchanged (same rows); caveat==label.
- Screenshot the shaded county map. Other tabs render.

## Guardrails
- Max 15 iterations. Supervised. One task = one commit. Green commits only.
- NO fabricated per-county weather; ambiguous counties uncolored not guessed. County boundaries
  from Census (real). Do NOT touch the sidebar battery-MW bar or /api/countyheat. Cache geojson
  gitignored under data_archive; commit only small summaries if needed for Fly.
