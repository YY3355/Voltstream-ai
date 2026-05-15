# VoltStream AI — Weekend Battle Plan & Validation Meeting Toolkit

## Your weekend schedule

### Friday night (tonight)
- [ ] Register for ERCOT API at https://apiexplorer.ercot.com (10 min)
- [ ] Subscribe to "Public API" product, copy subscription key
- [ ] Fill in credentials in `ercot_api_pipeline.py`, run `quick_test()`
- [ ] Pull 30 days of real ERCOT data using the pipeline
- [ ] Re-run the backtest on real data — note actual results

### Saturday
- [ ] Identify 15–20 targets for validation outreach (list below)
- [ ] Send LinkedIn connection requests with custom note (template below)
- [ ] Send 5–10 cold emails (template below)
- [ ] Research each target company for 10 min before reaching out
- [ ] Join Greentown Labs Houston as a member (apply online)

### Sunday
- [ ] Follow up on any Saturday replies
- [ ] Refine your 60-second pitch based on real backtest numbers
- [ ] Prepare your demo walkthrough (script below)
- [ ] Set up a simple website/landing page (even a Notion page works)
- [ ] Schedule any meetings that are confirmed for next week

---

## Who to target for validation meetings

### Tier 1: Battery storage operators active in ERCOT (your direct customers)
Find these by searching the ERCOT generation interconnection queue
(public at ercot.com) for "ESR" (Energy Storage Resource) entries.

Companies to research and contact:
1. Jupiter Power — Houston-based, one of the largest battery developers in Texas
2. Broad Reach Power — Houston-based, 1+ GW of storage in ERCOT
3. Key Capture Energy — major ERCOT battery operator
4. Plus Power — developing large-scale BESS projects in Texas
5. Eolian Energy — battery storage developer with ERCOT projects
6. Arevon Energy — utility-scale storage operator
7. NextEra Energy Resources — largest renewables+storage operator
8. Vistra Corp — owns multiple battery projects in Texas
9. Recurrent Energy — battery storage developer in ERCOT
10. 174 Power Global — Hanwha's US storage arm, active in Texas

Target titles: VP of Trading, Director of Asset Optimization, Head of Energy
Management, VP of Commercial Operations, Director of Market Operations

### Tier 2: Independent power producers adding storage
11. Calpine (now owned by Constellation) — Houston HQ, massive ERCOT fleet
12. NRG Energy — Houston HQ, adding storage to existing portfolio
13. LS Power — major IPP with growing storage portfolio
14. Talen Energy — storage development in ERCOT

### Tier 3: Energy trading desks and QSEs
15. Tenaska — trading desk in Houston, manages third-party assets
16. Vitol — energy trading, active in ERCOT power markets
17. Shell Energy — trading desk, could be both customer and strategic partner
18. Mercuria — energy trading firm with power trading desk

### Tier 4: Ecosystem (not customers but invaluable for intros and learning)
19. Greentown Labs Houston — clean energy incubator, join as member
20. Rice Alliance — startup accelerator, energy track
21. Houston Energy Transition Initiative (HETI)
22. Energy Capital Ventures — VC firm, energy-focused
23. Ara Partners — decarbonization PE/VC firm in Houston

---

## LinkedIn outreach template

### Connection request note (300 char limit)

**For battery operators:**
> Hi [Name] — I'm building an AI-driven dispatch optimization platform for
> ERCOT battery storage. Our backtest shows 160%+ revenue uplift vs
> peak/off-peak strategies. Would love 15 min to get your perspective on
> the market. Moving to Houston soon.

**For energy traders/QSEs:**
> Hi [Name] — building AI price forecasting tools for ERCOT. Our models
> forecast RT prices with ~$17/MWh MAE. Interested in how traders and
> QSEs think about optimization. Would love to learn from your experience.

**For ecosystem/investors:**
> Hi [Name] — I'm launching an energy tech startup focused on ERCOT
> battery optimization software. Moving to Houston and looking to connect
> with the energy transition community. Would love to learn from your
> experience.

---

## Cold email template

**Subject: AI battery optimization for ERCOT — quick question**

Hi [Name],

I'm building VoltStream AI, a software platform that autonomously
optimizes charge/discharge decisions for battery storage assets in
ERCOT.

Our backtest on a 100 MW / 400 MWh system shows:
— $5.7M annual revenue with ML-driven dispatch
— vs $2.2M with a basic peak/off-peak strategy
— 94.8% capture rate vs perfect foresight
— Fewer battery cycles (less degradation)

I'm not trying to sell anything yet — I'm validating whether this is a
real pain point for operators. I have three questions I'd love your take
on:

1. How do you currently optimize dispatch on your storage assets?
2. What would a 15–20% revenue improvement be worth to you annually?
3. Would you be open to a 90-day pilot if we could demonstrate
   outperformance?

Would you have 15 minutes next week for a quick call? Happy to share our
full backtest results.

Best,
[Your name]
[Your phone]
[Your email]

---

## The 15-minute validation call script

### Opening (2 min)
"Thanks for taking the time. I'm building software that helps battery
storage operators in ERCOT maximize revenue through AI-driven dispatch
optimization. I'm not selling anything today — I'm trying to understand
the market and make sure I'm building something people actually need.
Can I ask you a few questions?"

### Discovery questions (8 min)

**Current state:**
- "Can you walk me through how you currently make charge/discharge
  decisions on your storage assets?"
- "Is that done by a human trader, automated software, or a mix?"
- "What tools or platforms are you using for optimization today?"

**Pain points:**
- "What's the biggest challenge in maximizing revenue from your
  storage assets right now?"
- "How do you handle ancillary service co-optimization — are you
  bidding into Reg Up, RRS, ECRS simultaneously with energy
  arbitrage?"
- "What happens when your system misses a price spike?"

**Value quantification:**
- "Roughly what revenue per kW-year are you achieving on your
  ERCOT storage assets?"
- "If a tool could demonstrably improve that by 15–20%, what would
  that be worth across your portfolio?"
- "What would it take for you to test a new optimization tool —
  what would you need to see?"

**Buying process:**
- "If you were going to evaluate a tool like this, who else would
  need to be involved in the decision?"
- "Would you prefer a SaaS subscription, revenue share, or
  performance-based pricing?"

### Demo tease (3 min)
"Let me show you what we've built so far."

[Open the VoltStream dashboard HTML file]

Walk them through:
1. The backtest results — revenue comparison between strategies
2. Monthly revenue breakdown — point out seasonal patterns
3. Capture rate vs perfect foresight — "we're capturing 95% of the
   theoretical maximum"
4. Battery cycle savings — "our system uses fewer cycles, meaning
   less degradation on your asset"

Key phrase: "These results are based on synthetic data modeled on real
ERCOT patterns. We're now running against actual ERCOT market data.
Would you be interested in seeing backtest results on your specific
asset's node?"

### Close (2 min)
"This has been incredibly helpful. Two things I'd love to follow up on:

1. Would you be open to sharing which ERCOT nodes your assets sit on?
   I'll run a custom backtest and send you the results — no
   commitment, just data.

2. If the results look strong, would you consider a 90-day shadow
   pilot where our system runs recommendations alongside your current
   approach? You compare the results and only switch if we win."

"Who else in the ERCOT storage space should I be talking to?"

---

## Objections you'll hear and how to handle them

**"We already have optimization software from our hardware vendor
(Tesla/Fluence/etc.)"**
> "That makes sense — most operators start there. What we hear from
> others is that vendor-bundled tools are good but not great, because
> they're not deeply tuned to ERCOT's specific market mechanics.
> Our system is ERCOT-native and hardware-agnostic. Would it be worth
> comparing performance? We can run a backtest against the same
> period your vendor tool was operating."

**"We do this in-house with our own traders"**
> "Impressive — that tells me you take optimization seriously. The
> question is: can your traders watch every 5-minute SCED interval
> 24/7 and simultaneously optimize across energy, Reg Up, Reg Down,
> RRS, and ECRS? Our system never sleeps and processes more signals
> than a human can. Even a 5–10% improvement on an asset your traders
> are already optimizing is meaningful at scale."

**"How do I know your backtest isn't overfit?"**
> "Fair question — that's exactly why we want to do a live shadow
> pilot. Backtests are directional. The real test is live performance
> side-by-side with your current approach. We're willing to do that
> with no upfront fee because we're confident in the results."

**"We're not ready to switch — we just signed a contract with
another vendor"**
> "Totally understand. When does that contract come up? We'd love to
> stay in touch and run a comparison when the timing is right. In the
> meantime, would you be open to sharing your experience with that
> vendor — what's working and what's not? That helps us build a
> better product."

**"Revenue share means we're giving up money on something we already
own"**
> "Think of it this way — you're not giving up anything. You're
> choosing between 100% of $2M or 92% of $5.7M. The 8% fee only
> applies to revenue we generate. If we don't improve your revenue,
> you pay nothing."

---

## Metrics to track from your conversations

After each call, log these in a spreadsheet:

| Field | Why it matters |
|-------|---------------|
| Company name | |
| Contact name & title | |
| MW of storage in ERCOT | Sizes your addressable market |
| Current optimization approach | In-house, vendor, manual? |
| Revenue per kW-year they're achieving | Benchmark for your backtest |
| Top pain point | Build features around this |
| Interest level (1-5) | Prioritize follow-ups |
| Willing to do a pilot? | Your conversion funnel |
| Decision maker or influencer? | Map the org |
| Referrals given | Your growth engine |
| Follow-up action & date | Keep momentum |

---

## What "valuable" looks like for the meeting

You're not walking in with a pitch deck. You're walking in with:

1. **Real ERCOT data** — you pulled live market prices and can show
   today's price movements. This proves you understand the market.

2. **A working backtest** — not a slide, actual code that ran against
   real (or realistic) price data and generated specific dollar
   amounts.

3. **The dashboard** — a polished visual showing strategy comparison,
   monthly revenue, and your pitch. This looks like a real product.

4. **The right questions** — you're not selling, you're learning.
   Operators will respect that you've done your homework and are
   asking smart questions about their specific challenges.

5. **A concrete next step** — "Give me your node, I'll run a custom
   backtest." This is a no-commitment, high-value offer that keeps
   the relationship moving forward.

This combination — technical proof + market knowledge + genuine
curiosity — is what separates you from the 100 other people who
email them about AI optimization.

---

## Quick reference: ERCOT market structure

Know this cold before your meetings:

- **SCED**: Security-Constrained Economic Dispatch, runs every 5 min
- **LMP**: Locational Marginal Price (price at a specific node)
- **SPP**: Settlement Point Price (what you actually get paid)
- **DAM**: Day-Ahead Market (hourly, clears day before)
- **RTM**: Real-Time Market (5-min intervals)
- **AS**: Ancillary Services (Reg Up, Reg Down, RRS, ECRS, Non-Spin)
- **QSE**: Qualified Scheduling Entity (manages market participation)
- **ESR**: Energy Storage Resource (how ERCOT classifies batteries)
- **ERCOT system-wide offer cap**: $5,000/MWh
- **Load Zones**: LZ_HOUSTON, LZ_NORTH, LZ_SOUTH, LZ_WEST
- **Trading Hubs**: HB_HOUSTON, HB_NORTH, HB_SOUTH, HB_WEST, HB_PAN
