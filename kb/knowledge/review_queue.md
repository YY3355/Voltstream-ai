# KB Pass 2 — Validation review queue (Pass 1 items, source-checked)

**911 items validated.** 817 deterministic-pass (provisional); 94 flagged → judged: 40 SUPPORTED, 47 UNSUPPORTED, 7 UNCLEAR. **Human-review queue = 54** (UNSUPPORTED + UNCLEAR).

## Read this first — the deterministic-PASS blind spot
A deterministic PASS only means *the formula's tokens appear on the source pages* — it **cannot** catch a formula whose tokens are all present but **assembled wrong** (inverted ratio, dropped term). PASS = provisionally trusted, not proven. So the queue below is *flagged* items; the sampled-passed-formulas section adds a few PASSED formulas from notation-heavy chapters for your eyeball. Also note: **most flags are page-attribution (the item's claimed pages drift), not content fabrication** — triage those faster than a formula or content flag.

## Per-chapter flags

| ch | title | det-pass | SUPPORTED | UNSUPPORTED | UNCLEAR |
|---|---|---|---|---|---|
| 1 | 1.1 AN OVERVIEW OF THE ENERGY MARK | 108 | 4 | 4 | 0 |
| 2 | 1.2 TRADING MARKETS | 75 | 1 | 1 | 0 |
| 3 | 1.3 EXPLORATION AND PRODUCTION | 18 | 1 | 2 | 1 |
| 4 | 2.1 NATURAL GAS | 47 | 3 | 4 | 2 |
| 5 | 2.2 ELECTRICITY | 59 | 3 | 3 | 1 |
| 6 | 2.3 OIL | 44 | 2 | 7 | 1 |
| 7 | 2.4 COAL | 31 | 0 | 2 | 0 |
| 9 | 2.6 NATURAL GAS LIQUIDS | 7 | 2 | 3 | 0 |
| 12 | 3.3 STATISTICS | 19 | 2 | 4 | 0 |
| 13 | 3.4 FINANCIAL OPTIONS | 27 | 2 | 1 | 0 |
| 14 | 3.5 OPTION PRICING | 42 | 1 | 2 | 0 |
| 15 | 3.6 SPREAD OPTIONS | 14 | 1 | 0 | 1 |
| 18 | 4.3 TOLLING AGREEMENTS | 21 | 0 | 1 | 1 |
| 21 | 4.6 WIND POWER | 9 | 0 | 3 | 0 |
| 23 | 4.8 ELECTRICITY STORAGE | 11 | 3 | 1 | 0 |
| 24 | 4.9 LEVELIZED COST OF ENTRY | 3 | 0 | 3 | 0 |
| 25 | 4.10 SECONDARY ELECTRICITY MARKETS | 18 | 2 | 1 | 0 |
| 26 | 5.1 NATURAL GAS TRANSPORTATION | 15 | 2 | 1 | 0 |
| 27 | 5.2 NATURAL GAS STORAGE | 25 | 0 | 3 | 0 |
| 28 | 5.3 LIQUEFIED NATURAL GAS | 8 | 1 | 1 | 0 |

## Review queue (54) — FORMULAS FIRST

### 1. [UNSUPPORTED · ⚠FORMULA] Wind power intermittency and cube-law energy relationship
- source: ch1 p54 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `Energy ∝ (wind speed)^3`
- judge: Source text covers only solar power and the opening of wind power (turbines since 1970s, wind farms in high-wind areas) but never states or implies the cube-law energy relationship.

### 2. [UNSUPPORTED · ⚠FORMULA] Natural gas energy-content units and conversions
- source: ch4 p134-134 · flagged: **formula-tokens-missing** · file has 3 formula(s)
  - formula: `1 cubic foot of dry natural gas ≈ 1,000 Btu`
  - formula: `1 Bcf (billion cubic feet) ≈ 1,000,000 MMBtu`
  - formula: `1 therm = 100,000 Btu = 0.1 MMBtu`
- judge: Source text covers natural gas background (Henry Hub pricing, composition, history) but contains no mention of Btu content, MMBtu, Bcf, or therm conversions.

### 3. [UNSUPPORTED · ⚠FORMULA] Natural gas processing and quality standards
- source: ch4 p140 · flagged: **page-attribution+formula-tokens-missing** · file has 1 formula(s)
  - formula: `1,035 Btu/scf ± 5%`
- judge: Source page covers reservoir pressure/porosity/permeability geology, not gas processing, impurity removal, or the 1,035 Btu/scf ±5% spec.

### 4. [UNSUPPORTED · ⚠FORMULA] Common units for trading crude oil (barrel, tonne, conversion)
- source: ch6 p216 · flagged: **page-attribution+formula-tokens-missing** · file has 3 formula(s)
  - formula: `1 bbl = 42 US gallons ≈ 159 liters`
  - formula: `1 t = 1,000 kg ≈ 2,204.6 lbs`
  - formula: `1 tonne ≈ 7.5 barrels (rough average; ranges ~7.2 to ~7.5 bbl/tonne depending on crude density)`
- judge: Source text discusses crude oil market participants and trade flows but contains no mention of barrels, gallons, tonnes, or any unit conversions.

### 5. [UNSUPPORTED · ⚠FORMULA] Crude oil trading units: barrels vs. metric tonnes
- source: ch6 p221 · flagged: **formula-tokens-missing** · file has 2 formula(s)
  - formula: `1 BBL = 42 gallons`
  - formula: `1 MT ≈ 7.5 BBL (light crude)`
- judge: Source text explains the barrel-vs-tonne convention and density-dependent conversion but contains no numeric formulas (42 gallons/BBL, ~7.5 BBL/MT); those figures aren't present in the excerpt.

### 6. [UNSUPPORTED · ⚠FORMULA] Downstream processing and cracking
- source: ch6 p222-223 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `42 gallons crude → ~45 gallons finished products (via cracking/downstream processing)`
- judge: Source text only covers barrel/tonne conversion factors and crude transportation logistics; it contains no mention of cracking, downstream processing, sulfur removal, octane, gasoline yield percentage

### 7. [UNSUPPORTED · ⚠FORMULA] Mean absolute deviation
- source: ch12 p310 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `MAD = (1/n) * S|x_i - mean|`
- judge: Source text covers mode/median/mean only; no mention of mean absolute deviation, its formula, or its calculus tractability critique.

### 8. [UNSUPPORTED · ⚠FORMULA] Variance (sigma squared)
- source: ch12 p310-311 · flagged: **page-attribution** · file has 1 formula(s)
  - formula: `s^2 = (1/n) * S(x_i - mean)^2`
- judge: Source pages cover only mean/median/mode and an intro sentence to variation; no variance definition, sigma-squared notation, or formula appears in the given text.

### 9. [UNSUPPORTED · ⚠FORMULA] Payoff diagrams: forward contract vs call option
- source: ch13 p336-338 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `Payoff = max(Underlying Price - Strike Price, 0)`
- judge: Source describes the option payoff as 'half the payoff of a forward' and defines in/out of the money, but never states the max(Underlying-Strike,0) formula, nor the cited numeric examples ($8 MMBtu fo

### 10. [UNSUPPORTED · ⚠FORMULA] Wind energy's cube-law relationship to wind speed
- source: ch21 p462-463 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `Energy ∝ (Wind Speed)^3`
- judge: Source text on these pages contains no cube-law formula or any statement relating wind energy to the cube of wind speed.

### 11. [UNSUPPORTED · ⚠FORMULA] Capacity factor for wind generation
- source: ch21 p464-465 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `Capacity Factor = Actual Energy Produced / (Nameplate Capacity × Hours in Period)`
- judge: Source pages contain no capacity-factor definition, formula, or the 876,000 MWh/35%/40% figures at all — text is about wind variability and turbine maintenance.

### 12. [UNCLEAR · ⚠FORMULA] Spark spread option
- source: ch18 p425 · flagged: **formula-tokens-missing** · file has 1 formula(s)
  - formula: `Payoff per unit = max(Spark Spread, 0); Total Profit = max(Spark Spread, 0) × Volume`
- judge: Text describes the shutdown-option concept and references a spark spread net-profit formula in 'Figure 4.3.2', but that figure's content (and any max(spread,0) payoff formula) is not reproduced in the

### 13. [UNSUPPORTED · prose] Congestion and locational marginal price (LMP)
- source: ch1 p32-32 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page text covers AC vs DC power transmission physics only, with no mention of congestion, LMP, or marginal pricing to support the item's claims.

### 14. [UNSUPPORTED · prose] Wind turbine mechanical stress and wake turbulence
- source: ch1 p54 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text ends after introducing wind turbines/farms and 'sustained high winds' location; it contains no content on torque/mechanical stress, maintenance costs, or wake turbulence between turbines.

### 15. [UNSUPPORTED · prose] Credit Exposure
- source: ch1 p67 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page discusses VAR limitations and asymmetric P&L, not credit exposure, bankruptcy recovery, or debt priority claimed by the item.

### 16. [UNSUPPORTED · prose] Present value sensitivity to interest rate changes
- source: ch2 p105 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page discusses yield curve shapes and parallel shifts, not a present value example or any $1,000/$621/$784 figures.

### 17. [UNSUPPORTED · prose] Tax and royalty contract
- source: ch3 p121 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page text is about hydrocarbon fuel composition (Figure 1.3.1), with no mention of tax/royalty contracts, licensing fees, or gross profit shares.

### 18. [UNSUPPORTED · prose] Why fracking grew quickly (product mix, resource abundance, cost)
- source: ch3 p129 · flagged: **page-attribution** · file has 0 formula(s)
- judge: The provided source text discusses environmental pollution, shale oil processing, and deepwater drilling only—none of the claims about product mix, resource location, or cost competitiveness with Midd

### 19. [UNSUPPORTED · prose] Why natural gas storage is operationally necessary
- source: ch4 p148-149 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source pages cover basis trading and pipeline pressure mechanics only; nothing about storage buffering supply/demand, restart times, or aboveground vs underground storage appears in the given text.

### 20. [UNSUPPORTED · prose] Economics of natural gas storage facility siting
- source: ch4 p149 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text is about Henry Hub futures contracts and pipeline compressor mechanics; it contains no content about storage facility siting, count (~400), or pumping-equipment economics.

### 21. [UNSUPPORTED · prose] Nondiscriminatory power auctions and the clearing/marginal price
- source: ch5 p171 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only defines regulated vs. deregulated markets; it contains no mention of bidding, dispatch order, clearing price, or marginal price as claimed in the item.

### 22. [UNSUPPORTED · prose] Locational Marginal Price (LMP) and out-of-merit dispatch
- source: ch5 p176 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text is cut off before introducing LMP or the location-specific pricing concept; no mention of LMP, out-of-merit dispatch cost isolation, or splitting cost to affected locations appears in the 

### 23. [UNSUPPORTED · prose] Power Purchase Agreements (PPAs)
- source: ch5 p180 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page text covers rate base mechanics and Public Utility Commissions, with no mention of PPAs, third-party generators, or contract-price/asset-sale terms.

### 24. [UNSUPPORTED · prose] Drivers of where crude oil flows (transport cost, politics, regulation
- source: ch6 p215 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text covers only petroleum's origin, refining, and regional product pricing; it contains nothing about import/export nations, geographic flow logic, the 1973 OPEC embargo, or low-sulfur fuel re

### 25. [UNSUPPORTED · prose] Describing crude oil: density (API gravity) and sulfur content (sweet 
- source: ch6 p216-217 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text covers market participants and units, not API gravity/density or sweet-sour sulfur classification; only a tangential note on sulfur being a pollutant tying to price appears, but 'API gravi

### 26. [UNSUPPORTED · prose] Crude oil shipping and vessel size constraints
- source: ch6 p222 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text cuts off mid-sentence right as the Transportation section begins and contains no mention of tankers, ship size, port draft, or the Suez/Panama canals.

### 27. [UNSUPPORTED · prose] Physical Crude Oil Priced off Futures (Reversed Price Discovery)
- source: ch6 p234 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only defines spot/physical/financial transactions and futures contract naming; it never states crude oil is priced off futures rather than physical spot as claimed

### 28. [UNSUPPORTED · prose] Physical/operating constraints of coal as a solid fuel
- source: ch7 p247-247 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source pages are about coal's electrical generation dominance and low trading volume; they contain no discussion of coal as a solid fuel, firebox feeding mechanisms, or shutdown/burn-out behavior.

### 29. [UNSUPPORTED · prose] Flue gas desulfurization (lime/limestone scrubbers)
- source: ch7 p254 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text covers coal plant economies of scale and AC/DC transmission history; it contains no mention of flue gas desulfurization, lime scrubbers, or sulfur removal percentages.

### 30. [UNSUPPORTED · prose] NGL liquefaction, compaction, and storage/transport behavior
- source: ch9 p276 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only defines the five NGLs and their gaseous state at STP; it contains no mention of liquefaction via compression, the ~270x volume reduction, methane/cryogenic comparison, or storage/tran

### 31. [UNSUPPORTED · prose] Natural gasoline (pentanes+): uses including dilbit
- source: ch9 p278 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page provided covers propane, ethane, and butanes only; no text about natural gasoline/pentanes+, naphtha blending, denatured ethanol, or dilbit/Canada export appears.

### 32. [UNSUPPORTED · prose] NGL purity grades: pipeline grade vs. fractionation grade
- source: ch9 p279 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text is about NGL hubs (Mont Belvieu/Conway) and physical/financial trading, with no mention of pipeline grade vs. fractionation grade purity levels or a price premium for purer product.

### 33. [UNSUPPORTED · prose] Why variation/dispersion matters alongside the average
- source: ch12 p309-310 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text covers mode/median/mean central tendency only; it never discusses variation/dispersion, volatility, standard deviation, mean absolute deviation, or variance as claimed in the item.

### 34. [UNSUPPORTED · prose] Portfolio diversification benefit of combining imperfectly correlated 
- source: ch12 p317-318 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source pages show only exponential weighting/decay and reward-to-risk (Sharpe/Information Ratio) content; no mention of combining strategies, correlation-based diversification, or the natural gas rise

### 35. [UNSUPPORTED · prose] Random walk
- source: ch14 p352-352 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text never mentions random walks, dimensionality, or the binomial tree at all.

### 36. [UNSUPPORTED · prose] Stochastic process
- source: ch14 p352-352 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text discusses option pricing models and price distribution assumptions but never mentions 'stochastic process', coin flips, dice rolls, martingales, or random walks.

### 37. [UNSUPPORTED · prose] Valuation date vs. expiration date for a tolling option
- source: ch18 p434 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only describes calculating expiration-date profit by averaging profitable spreads and multiplying by dispatch rate; it never defines a 'valuation date', never discusses retained flexibilit

### 38. [UNSUPPORTED · prose] Turbine wake effects and wind farm maintenance burden
- source: ch21 p463-464 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text is about wind farm siting/land availability and cube-law wind energy; contains nothing about turbine wake turbulence, downwind stress, farm layout/aesthetics, or maintenance logistics.

### 39. [UNSUPPORTED · prose] Baseload plants and effectively free overnight power for storage
- source: ch23 p477-477 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text discusses general storage arbitrage and round-trip efficiency losses; it contains no mention of nuclear/coal baseload plants, ramping/reheating costs, or overnight power becoming effective

### 40. [UNSUPPORTED · prose] Final LCOE per MWh: adding operating costs and netting revenue
- source: ch24 p488 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text covers only WACC and CRF (Figures 4.9.1-4.9.2); it never mentions operating costs, maintenance, fuel, or netting other revenue against capital recovery as claimed.

### 41. [UNSUPPORTED · prose] Limitations of LCOE as a price estimate
- source: ch24 p488 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text discusses CONE/WACC/CRF revenue-requirement calculation, not LCOE limitations or regional/tax/transmission/regulatory factors claimed in the item.

### 42. [UNSUPPORTED · prose] Regulatory use of LCOE and the EIA Annual Energy Outlook
- source: ch24 p488-489 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text describes CONE/DCF/LCOE methodology only; it never mentions the EIA or the Annual Energy Outlook publishing cost figures.

### 43. [UNSUPPORTED · prose] Spinning reserve and nonspinning reserve
- source: ch25 p495 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page only introduces ancillary services markets generally; it never mentions spinning/nonspinning reserve, synchronization, or the 10-minute/30-60-minute timing claims.

### 44. [UNSUPPORTED · prose] Pipelines as continuous-operation, insurance-like businesses
- source: ch26 p506-506 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only contains the chapter purpose/summary (pipelines are for-profit, gas is hard to transport otherwise) and cuts off at the 'Key Topics' heading — it never mentions an insurance analogy, 

### 45. [UNSUPPORTED · prose] Maximum pressure as a facility design constraint
- source: ch27 p528 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only describes storage geology (impermeable underground area, analogy to pressurized containers/wells) and never discusses maximum pressure trade-offs, withdrawal speed, structural risk, o

### 46. [UNSUPPORTED · prose] Why New Aquifer Storage Development Is Unlikely
- source: ch27 p534 · flagged: **page-attribution** · file has 0 formula(s)
- judge: The provided source page is an unrelated New Jersey storage trading example and contains no mention of aquifer facilities, cushion/base gas economics, cheap natural gas history, or U.S. government dri

### 47. [UNSUPPORTED · prose] Storage Facility as an Enabler of Delivery-Insurance Trades
- source: ch27 p536 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page text is unrelated (natural gas storage-vs-5-year-average figure reference), contains no mention of delivery-insurance trades or premiums.

### 48. [UNSUPPORTED · prose] LNG Safety Concerns and Facility Siting
- source: ch28 p541-541 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only covers LNG's three-step process (liquefaction, transportation, regasification) and does not mention facility safety debate, catastrophic risk, methane's non-toxic/non-explosive proper

### 49. [UNCLEAR · prose] Risk in exploration and production
- source: ch3 p120-121 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text provided is only about hydrocarbon fuel chemistry/types, not E&P risk, leasing, or price decline — cannot verify the item's claims from this excerpt.

### 50. [UNCLEAR · prose] Natural gas pricing conventions and price behavior
- source: ch4 p133-133 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text cuts off mid-sentence in the Key Topics list before reaching any content on Henry Hub, spread pricing, weather-driven spot, or futures cyclicality/cost-of-carry, so those specific claims c

### 51. [UNCLEAR · prose] Zone Rates vs. Postage Stamp Rates
- source: ch4 p144-144 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text only lists transportation contract charge terms; it contains no mention of zone rates or postage stamp rates.

### 52. [UNCLEAR · prose] Importance and cyclic predictability of electrical demand forecasting
- source: ch5 p180-181 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text cuts off mid-sentence ('these auctions can't just be reactive—they need to') right before explaining forecasting needs; none of the item's specific claims (cyclic patterns, fuel lead-time,

### 53. [UNCLEAR · prose] Heating Oil Seasonal Demand Pattern
- source: ch6 p232 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source text supports winter residential heating concentrated in the northeastern US but cuts off mid-sentence before covering summer price lows, stockpiling behavior, storage capacity limits, or the f

### 54. [UNCLEAR · prose] Three unknown parameters in spread option valuation
- source: ch15 p384 · flagged: **page-attribution** · file has 0 formula(s)
- judge: Source page text is only a figure caption ('Figure 3.6.9 Spread option call formula') with no surrounding explanatory text to confirm the claims about three unknowns or implied correlation.

## Blind-spot insurance — sampled PASSED formulas in notation-heavy chapters
(These PASSED deterministically; eyeball that they're assembled correctly, per the blind spot above.)

**ch12 3.3 Statistics** (2 passed formulas):
- p303-304: `x̄ = (Σ x_i, i=1 to n) / n`
- p317-318: `Ratio = average return / standard deviation of returns`

**ch14 3.5 Option Pricing** (1 passed formulas):
- p372-373: `P(down) = 100% - P(up)`

**ch30 6.2 Value at Risk** (1 passed formulas):
- p562-565: `σ² = σ × σ`
