# ⚡ VoltStream AI

**Autonomous battery dispatch optimization for ERCOT using hybrid agentic AI.**

Six AI agents work together as a virtual trading desk — making dispatch decisions 24/7, learning from every trade, and delivering more revenue than traditional approaches.

## The Problem

Battery storage operators in ERCOT leave millions on the table. On May 2, 2026, a standard peak/off-peak strategy **lost $7,671** on a 100MW asset because solar has inverted Texas price patterns. VoltStream's AI made **$70,123** on the same asset, same day.

## Six Intelligence Layers

| Layer | What It Does | File |
|-------|-------------|------|
| Ensemble Forecasting | 5 ML models vote on prices with adaptive weights | `models/ensemble.py` |
| RL Agent | Learns optimal trading from experience (99.3% capture rate) | `agents/rl_agent.py` |
| Multi-Model Weather | 5 weather providers, disagreement = uncertainty signal | `data/multi_weather.py` |
| Probabilistic Dispatch | Trades against distributions, manages tail risk | `models/probabilistic.py` |
| Persistent Memory | Self-correcting system that compounds over time | `agents/memory.py` |
| Graph Neural Network | Models ERCOT grid topology for nodal price prediction | `models/gnn.py` |

Plus **Claude API** for edge case reasoning and plain English explanations.

## The Brain (Intelligence Levels)

Beyond the six base layers, VoltStream has a multi-level reasoning system:

| Level | Capability | File |
|-------|-----------|------|
| Level 1 | Pattern Memory (remembers what worked before) | `agents/memory.py` |
| Level 2 | Causal Reasoning (understands WHY prices move) | `core/causal_engine.py` |
| Level 3 | Anticipatory Planning (simulates 300+ futures like chess) | `core/planning_engine.py` |
| Level 4 | Market Awareness (game theory, models other batteries) | `agents/game_theory.py` |
| Level 5 | Cross-Domain Synthesis (connects news/weather/gas/regulatory) | `agents/cross_domain.py` |

## Quick Start

```bash
pip install -r requirements.txt
python main.py status      # Check all modules
python main.py demo        # Run 24h demo
python main.py train       # Train RL agent
python main.py live        # Start live service (real ERCOT data)
python main.py gnn         # Nodal price analysis
python main.py ensemble    # Ensemble forecast demo
python main.py weather     # Multi-provider weather demo
```

For live service with Claude reasoning:
```bash
export ANTHROPIC_API_KEY=your_key
python main.py live
# Dashboard at http://localhost:5000
```

## Customer API

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/dispatch` | Current dispatch command + explanation |
| `GET /api/v1/history` | Decision history |
| `GET /api/v1/performance` | Revenue and accuracy metrics |
| `GET /api/v1/report` | Daily report written by Claude |
| `GET /api/v1/alerts` | Active alerts |

## Project Structure

```
voltstream-ai/
├── main.py                  # Entry point
├── requirements.txt
├── core/
│   ├── hybrid_engine.py     # ML + Claude hybrid dispatch
│   ├── cloud_service.py     # 24/7 service with API
│   ├── optimizer.py         # Battery optimizer + backtester
│   ├── ancillary_optimizer.py # AS co-optimization
│   ├── causal_engine.py     # Level 2: Causal reasoning
│   └── planning_engine.py   # Level 3: Anticipatory planning
├── agents/
│   ├── multi_agent.py       # 6-agent virtual trading desk
│   ├── rl_agent.py          # Reinforcement learning agent
│   ├── memory.py            # Level 1: Persistent memory
│   ├── notice_reader.py     # Market notice reader
│   ├── game_theory.py       # Level 4: Game theory
│   └── cross_domain.py      # Level 5: Cross-domain synthesis
├── models/
│   ├── ensemble.py          # 5-model ensemble forecaster
│   ├── probabilistic.py     # Quantile forecasting
│   ├── gnn.py               # Graph neural network
│   ├── price_forecaster.py  # XGBoost price model
│   └── rl_dispatch_model.json
├── data/
│   ├── weather_engine.py    # Open-Meteo integration
│   ├── multi_weather.py     # Multi-provider weather
│   ├── ercot_generator.py   # Synthetic data generator
│   ├── ercot_live.py        # Live ERCOT data puller
│   └── ercot_api.py         # ERCOT API pipeline
└── docs/
    ├── voltstream_dashboard.html
    ├── voltstream_real_data_dashboard.html
    ├── voltstream_platform.jsx
    ├── voltstream_lead_list.md
    └── voltstream_weekend_battleplan.md
```

## Key Results

**Real ERCOT Data (May 2, 2026):**
- Naive strategy: **-$7,671** (lost money)
- VoltStream: **$70,123** (+$77,794 uplift)
- Capture rate: 91.7% of perfect foresight

**RL Agent (30-day simulation):**
- Naive: -$1,078,803
- RL Agent: $1,015,791
- Capture rate: 99.3% of perfect foresight

## The Moat

1. **Data Gravity** — Every asset generates proprietary data that improves models
2. **Self-Improving Loop** — Settlement feeds errors back to forecaster
3. **Persistent Memory** — 6 months of corrections no competitor can replicate
4. **Integration Depth** — Connected to SCADA, BMS, QSE, settlement
5. **Network Effects** — More assets = better models = more assets

## Business Model

Service-as-a-software. Customers get managed dispatch via API. They pay 8% of revenue. If we don't improve their revenue, they pay nothing.

---

Built with conviction. Houston, TX.
