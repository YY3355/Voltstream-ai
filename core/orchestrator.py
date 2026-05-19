"""
VoltStream AI — Master Orchestrator
=====================================
This is the HEARTBEAT of VoltStream. Every 5 minutes:

1. SENSE   — Pull real prices + weather
2. RECALL  — RAG retrieves similar past situations
3. REASON  — Causal engine explains WHY
4. PLAN    — Monte Carlo simulates 300 futures
5. COMPETE — Game theory models the herd
6. SCAN    — Cross-domain checks for outside signals
7. DECIDE  — All inputs converge into one dispatch decision
8. ACT     — Log the decision (or execute via API)
9. LEARN   — Settlement checks past decisions, self-learner improves

This replaces cloud_service.py with a true brain loop.
Every module we built plugs in here.

TO RUN:
  python -m core.orchestrator

  Or from main.py:
  python main.py orchestrate
"""

import numpy as np
import sqlite3
import json
import logging
import time
import os
from datetime import datetime, timedelta
from typing import Dict, Optional

log = logging.getLogger('voltstream.orchestrator')


class BrainState:
    """
    The complete state of the brain at any moment.
    Passed between modules so each one can see
    what the others have concluded.
    """
    
    def __init__(self, battery_config: dict = None):
        self.battery = battery_config or {
            'power_mw': 100,
            'capacity_mwh': 400,
            'soc': 0.50,
            'min_soc': 0.05,
            'max_soc': 0.95,
            'rte': 0.87,
            'node': 'HB_HOUSTON',
        }
        
        # Current market data
        self.current_price = 0
        self.prices = {}  # all hub prices
        self.weather = {}
        self.hour = datetime.now().hour
        self.timestamp = datetime.now()
        
        # Price history (rolling)
        self.price_history = []
        self.max_history = 2000
        
        # Module outputs (filled each tick)
        self.ml_forecast = {}
        self.rag_context = {}
        self.causal_analysis = {}
        self.planning_result = {}
        self.game_theory = {}
        self.cross_domain = {}
        self.self_learning = {}
        
        # Final decision
        self.decision = {}
        self.decision_history = []
        
        # Tick counter
        self.tick = 0


class DataLayer:
    """
    Handles all data ingestion: prices, weather, notices.
    Tries real sources first, falls back gracefully.
    """
    
    def __init__(self):
        self.ercot_url = 'https://www.ercot.com/content/cdr/html/real_time_spp.html'
        self.weather_url = 'https://api.open-meteo.com/v1/forecast'
        self.last_price_pull = None
        self.last_weather_pull = None
    
    def pull_prices(self) -> dict:
        """Pull real-time ERCOT prices. Scraper then synthetic fallback."""
        try:
            import pandas as pd
            tables = pd.read_html(self.ercot_url, timeout=10)
            if tables:
                df = tables[0]
                prices = {}
                for hub in ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'HB_PAN']:
                    if hub in df.columns:
                        prices[hub] = float(df[hub].iloc[-1])
                
                if prices:
                    self.last_price_pull = datetime.now()
                    log.info(f"ERCOT prices pulled: HB_HOUSTON=${prices.get('HB_HOUSTON', 0):.2f}")
                    return {'source': 'ercot_live', 'prices': prices}
        except Exception as e:
            log.warning(f"ERCOT scrape failed: {e}")
        
        # Synthetic fallback
        hour = datetime.now().hour
        base = self._synthetic_price(hour)
        prices = {
            'HB_HOUSTON': base + np.random.normal(0, 3),
            'HB_NORTH': base + np.random.normal(2, 3),
            'HB_SOUTH': base + np.random.normal(-2, 3),
            'HB_WEST': base + np.random.normal(5, 8),
            'HB_PAN': base + np.random.normal(3, 6),
        }
        self.last_price_pull = datetime.now()
        return {'source': 'synthetic', 'prices': prices}
    
    def pull_weather(self) -> dict:
        """Pull weather data from Open-Meteo."""
        locations = {
            'houston': (29.76, -95.37),
            'dallas': (32.78, -96.80),
            'west_texas': (32.00, -101.00),
            'panhandle': (35.50, -101.50),
        }
        
        weather = {}
        for name, (lat, lon) in locations.items():
            try:
                import requests
                r = requests.get(self.weather_url, params={
                    'latitude': lat, 'longitude': lon,
                    'current': 'temperature_2m,wind_speed_10m,cloud_cover',
                    'temperature_unit': 'fahrenheit',
                    'wind_speed_unit': 'mph',
                }, timeout=10)
                
                if r.status_code == 200:
                    data = r.json().get('current', {})
                    weather[name] = {
                        'temperature': data.get('temperature_2m', 75),
                        'wind_speed': data.get('wind_speed_10m', 15),
                        'cloud_cover': data.get('cloud_cover', 50),
                    }
            except Exception:
                weather[name] = {'temperature': 75, 'wind_speed': 15, 'cloud_cover': 50}
        
        if not weather:
            weather = {
                'houston': {'temperature': 80, 'wind_speed': 12, 'cloud_cover': 30},
                'dallas': {'temperature': 78, 'wind_speed': 10, 'cloud_cover': 35},
                'west_texas': {'temperature': 85, 'wind_speed': 18, 'cloud_cover': 20},
                'panhandle': {'temperature': 76, 'wind_speed': 22, 'cloud_cover': 25},
            }
        
        self.last_weather_pull = datetime.now()
        return weather
    
    def _synthetic_price(self, hour: int) -> float:
        """Generate realistic synthetic price based on hour."""
        patterns = {
            0: 35, 1: 32, 2: 30, 3: 28, 4: 27, 5: 30,
            6: 25, 7: 20, 8: 12, 9: 5, 10: 3, 11: 2,
            12: 3, 13: 5, 14: 8, 15: 15, 16: 30, 17: 45,
            18: 55, 19: 50, 20: 42, 21: 38, 22: 36, 23: 35,
        }
        return patterns.get(hour, 30) + np.random.normal(0, 5)


class DecisionEngine:
    """
    Combines all module outputs into one final decision.
    
    Each module votes with a confidence. The engine weighs
    all votes and picks the action with the highest
    confidence-weighted support.
    """
    
    def decide(self, state: BrainState) -> dict:
        """
        Combine all module outputs into one decision.
        """
        votes = []
        
        # ML forecast vote
        if state.ml_forecast:
            price_1h = state.ml_forecast.get('price_1h', state.current_price)
            spread = price_1h - state.current_price
            
            if spread > 15 and state.battery['soc'] < 0.80:
                votes.append(('CHARGE', 0.6, 'ML: price rising, charge now'))
            elif spread < -10 and state.battery['soc'] > 0.20:
                votes.append(('DISCHARGE', 0.6, 'ML: price falling, discharge now'))
            elif state.current_price > 50 and state.battery['soc'] > 0.15:
                votes.append(('DISCHARGE', 0.7, f'ML: high price ${state.current_price:.0f}'))
            elif state.current_price < 10 and state.battery['soc'] < 0.85:
                votes.append(('CHARGE', 0.7, f'ML: low price ${state.current_price:.0f}'))
        
        # RAG vote
        if state.rag_context and state.rag_context.get('has_history'):
            best = state.rag_context.get('best_action', 'HOLD')
            success = state.rag_context.get('success_rate', 0.5)
            if success > 0.6:
                votes.append((best, success * 0.8, f'RAG: {best} worked {success:.0%} of the time'))
        
        # Causal vote
        if state.causal_analysis:
            rec = state.causal_analysis.get('battery_recommendation', {})
            if rec.get('action') in ['CHARGE', 'DISCHARGE']:
                votes.append((rec['action'], rec.get('confidence', 0.5),
                             f"Causal: {rec.get('reason', '')[:60]}"))
        
        # Planning vote
        if state.planning_result:
            action = state.planning_result.get('recommended_action', 'HOLD')
            sharpe = state.planning_result.get('recommended_details', {}).get('sharpe', 0)
            if action in ['CHARGE_FULL', 'CHARGE_HALF', 'CHARGE_QUARTER']:
                votes.append(('CHARGE', min(0.9, sharpe), f'Planning: {action}'))
            elif action in ['DISCHARGE_FULL', 'DISCHARGE_HALF', 'DISCHARGE_QUARTER']:
                votes.append(('DISCHARGE', min(0.9, sharpe), f'Planning: {action}'))
            else:
                votes.append(('HOLD', 0.5, 'Planning: HOLD'))
        
        # Game theory vote
        if state.game_theory:
            strat = state.game_theory.get('our_strategy', {})
            action = strat.get('action', 'DEFER')
            if action != 'DEFER':
                votes.append((action, strat.get('confidence', 0.5),
                             f"Game theory: {strat.get('strategy_type', '')}"))
        
        # Cross-domain vote
        if state.cross_domain:
            bias = state.cross_domain.get('market_bias', 'neutral')
            if bias in ['strongly_bullish', 'moderately_bullish']:
                if state.battery['soc'] < 0.80:
                    votes.append(('CHARGE', 0.6, f'Cross-domain: {bias}, accumulate charge'))
            elif bias in ['strongly_bearish']:
                if state.battery['soc'] > 0.20:
                    votes.append(('DISCHARGE', 0.5, f'Cross-domain: {bias}, reduce exposure'))
        
        # Negative price override (always charge)
        if state.current_price < 0:
            votes = [('CHARGE', 0.95, f'Override: negative price ${state.current_price:.1f}')]
        
        # Extreme price override (always discharge if able)
        if state.current_price > 200 and state.battery['soc'] > 0.10:
            votes = [('DISCHARGE', 0.95, f'Override: extreme price ${state.current_price:.0f}')]
        
        # Tally votes
        if not votes:
            return {
                'action': 'HOLD',
                'intensity': 0,
                'confidence': 0.5,
                'reasoning': 'No strong signal from any module.',
                'votes': [],
                'n_modules_voted': 0,
            }
        
        action_scores = {}
        action_reasons = {}
        
        for action, confidence, reason in votes:
            if action not in action_scores:
                action_scores[action] = 0
                action_reasons[action] = []
            action_scores[action] += confidence
            action_reasons[action].append(reason)
        
        best_action = max(action_scores, key=action_scores.get)
        best_score = action_scores[best_action]
        total_score = sum(action_scores.values())
        
        # Intensity based on consensus
        consensus = best_score / max(total_score, 1)
        intensity = min(1.0, consensus * 0.8 + 0.2)
        
        # SOC guardrails
        if best_action == 'DISCHARGE' and state.battery['soc'] < state.battery['min_soc'] + 0.05:
            best_action = 'HOLD'
            intensity = 0
        elif best_action == 'CHARGE' and state.battery['soc'] > state.battery['max_soc'] - 0.05:
            best_action = 'HOLD'
            intensity = 0
        
        return {
            'action': best_action,
            'intensity': round(intensity, 2),
            'confidence': round(consensus, 3),
            'reasoning': ' | '.join(action_reasons.get(best_action, [])),
            'votes': [{'action': a, 'conf': c, 'reason': r} for a, c, r in votes],
            'n_modules_voted': len(votes),
            'all_scores': {k: round(v, 3) for k, v in action_scores.items()},
        }


class PersistenceLayer:
    """Stores all decisions and outcomes for learning."""
    
    def __init__(self, db_path: str = 'voltstream_brain.db'):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''CREATE TABLE IF NOT EXISTS ticks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            tick_number INTEGER,
            price REAL,
            price_source TEXT,
            hour INTEGER,
            soc REAL,
            action TEXT,
            intensity REAL,
            confidence REAL,
            reasoning TEXT,
            n_modules INTEGER,
            votes TEXT,
            weather TEXT,
            duration_ms REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        conn.commit()
        conn.close()
    
    def log_tick(self, state: BrainState, decision: dict, duration_ms: float):
        """Log a complete tick."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                '''INSERT INTO ticks (timestamp, tick_number, price, price_source, hour, soc,
                   action, intensity, confidence, reasoning, n_modules, votes, weather, duration_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    state.timestamp.isoformat(),
                    state.tick,
                    state.current_price,
                    state.prices.get('_source', 'unknown'),
                    state.hour,
                    state.battery['soc'],
                    decision['action'],
                    decision['intensity'],
                    decision['confidence'],
                    decision['reasoning'][:500],
                    decision['n_modules_voted'],
                    json.dumps(decision.get('votes', [])),
                    json.dumps({k: v.get('temperature', 0) for k, v in state.weather.items()} if state.weather else {}),
                    duration_ms,
                )
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"Failed to log tick: {e}")
    
    def get_recent_decisions(self, limit: int = 10) -> list:
        """Get recent decisions for display."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                'SELECT * FROM ticks ORDER BY id DESC LIMIT ?', (limit,)
            ).fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception:
            return []


class Orchestrator:
    """
    The master brain loop.
    
    Connects every module VoltStream has into one
    continuous decision-making system.
    """
    
    def __init__(self, battery_config: dict = None, db_path: str = 'voltstream_brain.db'):
        self.state = BrainState(battery_config)
        self.data = DataLayer()
        self.decision_engine = DecisionEngine()
        self.persistence = PersistenceLayer(db_path)
        
        # Import modules (gracefully handle missing ones)
        self.modules = {}
        self._load_modules()
        
        self.running = False
        self.tick_interval = 300  # 5 minutes in seconds
    
    def _load_modules(self):
        """Load all available brain modules."""
        module_map = {
            'ml_forecast': ('models.production_ml', 'ProductionMLForecaster'),
            'ensemble': ('models.ensemble', 'EnsembleForecaster'),
            'causal': ('core.causal_engine', 'CausalReasoningEngine'),
            'planning': ('core.planning_engine', 'AnticipatoryPlanner'),
            'game_theory': ('agents.game_theory', 'GameTheoryEngine'),
            'cross_domain': ('agents.cross_domain', 'CrossDomainSynthesizer'),
            'self_learning': ('agents.self_learning', 'SelfDirectedLearner'),
            'rag': ('core.rag_engine_v2', 'RAGEngineV2'),
            'memory': ('agents.memory', 'AgentMemory'),
        }
        
        for name, (module_path, class_name) in module_map.items():
            try:
                mod = __import__(module_path, fromlist=[class_name])
                cls = getattr(mod, class_name)
                self.modules[name] = cls()
                log.info(f"  Loaded: {name}")
            except Exception as e:
                log.warning(f"  Skipped: {name} ({e})")
    
    def tick(self) -> dict:
        """
        ONE TICK of the brain. This is the heartbeat.
        
        Every 5 minutes, this runs and produces one decision.
        """
        tick_start = time.time()
        self.state.tick += 1
        self.state.timestamp = datetime.now()
        self.state.hour = self.state.timestamp.hour
        
        log.info(f"{'='*60}")
        log.info(f"TICK {self.state.tick} | {self.state.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        log.info(f"{'='*60}")
        
        # ============================================
        # STEP 1: SENSE (pull real data)
        # ============================================
        price_data = self.data.pull_prices()
        self.state.prices = price_data['prices']
        self.state.prices['_source'] = price_data['source']
        self.state.current_price = self.state.prices.get(
            self.state.battery['node'], 
            list(self.state.prices.values())[0] if self.state.prices else 30
        )
        
        self.state.weather = self.data.pull_weather()
        
        # Update price history
        self.state.price_history.append(self.state.current_price)
        if len(self.state.price_history) > self.state.max_history:
            self.state.price_history = self.state.price_history[-self.state.max_history:]
        
        houston_weather = self.state.weather.get('houston', {})
        
        log.info(f"  Price: ${self.state.current_price:.2f}/MWh ({price_data['source']})")
        log.info(f"  Weather: {houston_weather.get('temperature', '?')}F, "
                 f"wind {houston_weather.get('wind_speed', '?')}mph")
        log.info(f"  SOC: {self.state.battery['soc']*100:.0f}%")
        
        # ============================================
        # STEP 2: RECALL (RAG retrieves history)
        # ============================================
        if 'rag' in self.modules:
            try:
                situation = {
                    'price': self.state.current_price,
                    'hour': self.state.hour,
                    'temperature': houston_weather.get('temperature', 75),
                    'wind_speed': self.state.weather.get('west_texas', {}).get('wind_speed', 15),
                    'solar_ghi': max(0, (1 - houston_weather.get('cloud_cover', 50) / 100) * 800) if 6 < self.state.hour < 19 else 0,
                    'soc': self.state.battery['soc'],
                    'price_1h_ago': self.state.price_history[-12] if len(self.state.price_history) > 12 else self.state.current_price,
                    'price_4h_ago': self.state.price_history[-48] if len(self.state.price_history) > 48 else self.state.current_price,
                }
                rag_result = self.modules['rag'].retrieve_and_reason(situation)
                self.state.rag_context = rag_result.get('analysis', {})
                log.info(f"  RAG: {rag_result.get('analysis', {}).get('n_results', 0)} similar situations found")
            except Exception as e:
                log.warning(f"  RAG failed: {e}")
        
        # ============================================
        # STEP 3: REASON (causal engine)
        # ============================================
        if 'causal' in self.modules:
            try:
                conditions = {
                    'temperature': houston_weather.get('temperature', 75),
                    'wind_speed': self.state.weather.get('west_texas', {}).get('wind_speed', 15),
                    'solar_ghi': max(0, (1 - houston_weather.get('cloud_cover', 50) / 100) * 800) if 6 < self.state.hour < 19 else 0,
                    'hour': self.state.hour,
                    'gas_price': 3.50,
                }
                causal = self.modules['causal'].reason(conditions)
                self.state.causal_analysis = causal
                log.info(f"  Causal: price driven by {causal.get('merit_order', {}).get('marginal_fuel', '?')}")
            except Exception as e:
                log.warning(f"  Causal failed: {e}")
        
        # ============================================
        # STEP 4: PLAN (Monte Carlo futures)
        # ============================================
        if 'planning' in self.modules:
            try:
                plan = self.modules['planning'].plan(
                    current_price=self.state.current_price,
                    current_soc=self.state.battery['soc'],
                    current_hour=self.state.hour,
                    n_simulations=100,  # reduced for speed in live
                )
                self.state.planning_result = plan
                log.info(f"  Planning: recommends {plan.get('recommended_action', '?')}")
            except Exception as e:
                log.warning(f"  Planning failed: {e}")
        
        # ============================================
        # STEP 5: COMPETE (game theory)
        # ============================================
        if 'game_theory' in self.modules:
            try:
                gt = self.modules['game_theory'].analyze(
                    current_price=self.state.current_price,
                    hour=self.state.hour,
                    our_soc=self.state.battery['soc'],
                )
                self.state.game_theory = gt
                herd = gt.get('fleet_analysis', {}).get('herd_direction', '?')
                log.info(f"  Game theory: herd is {herd}")
            except Exception as e:
                log.warning(f"  Game theory failed: {e}")
        
        # ============================================
        # STEP 6: SCAN (cross-domain signals)
        # ============================================
        if 'cross_domain' in self.modules:
            try:
                synth = self.modules['cross_domain'].synthesize()
                self.state.cross_domain = synth
                bias = synth.get('market_bias', 'neutral')
                log.info(f"  Cross-domain: {synth.get('total_signals', 0)} signals, bias={bias}")
            except Exception as e:
                log.warning(f"  Cross-domain failed: {e}")
        
        # ============================================
        # STEP 7: DECIDE (combine all inputs)
        # ============================================
        decision = self.decision_engine.decide(self.state)
        self.state.decision = decision
        self.state.decision_history.append(decision)
        
        log.info(f"  DECISION: {decision['action']} (intensity={decision['intensity']:.0%}, "
                 f"confidence={decision['confidence']:.0%}, {decision['n_modules_voted']} modules voted)")
        log.info(f"  Reasoning: {decision['reasoning'][:100]}")
        
        # ============================================
        # STEP 8: ACT (simulate battery response)
        # ============================================
        self._simulate_battery_action(decision)
        
        # ============================================
        # STEP 9: LEARN (store and improve)
        # ============================================
        tick_duration = (time.time() - tick_start) * 1000
        self.persistence.log_tick(self.state, decision, tick_duration)
        
        # Feed data to self-learner periodically
        if 'self_learning' in self.modules and self.state.tick % 24 == 0:
            try:
                learn_result = self.modules['self_learning'].learn()
                log.info(f"  Self-learning: cycle {learn_result.get('cycle', '?')}, "
                        f"{learn_result.get('weaknesses_found', 0)} weaknesses found")
            except Exception:
                pass
        
        log.info(f"  Tick completed in {tick_duration:.0f}ms | SOC: {self.state.battery['soc']*100:.1f}%")
        
        return decision
    
    def _simulate_battery_action(self, decision: dict):
        """Simulate the battery responding to the decision."""
        action = decision['action']
        intensity = decision['intensity']
        power = self.state.battery['power_mw'] * intensity
        eff = np.sqrt(self.state.battery['rte'])
        capacity = self.state.battery['capacity_mwh']
        
        if action == 'CHARGE':
            energy = power * eff / 12  # 5-minute interval
            new_soc = min(self.state.battery['max_soc'],
                         self.state.battery['soc'] + energy / capacity)
            self.state.battery['soc'] = new_soc
        
        elif action == 'DISCHARGE':
            energy = power / eff / 12
            new_soc = max(self.state.battery['min_soc'],
                         self.state.battery['soc'] - energy / capacity)
            self.state.battery['soc'] = new_soc
    
    def run(self, n_ticks: int = None, interval: int = None):
        """
        Run the brain loop.
        
        n_ticks: number of ticks to run (None = forever)
        interval: seconds between ticks (None = use default 300s)
        """
        self.running = True
        tick_interval = interval or self.tick_interval
        tick_count = 0
        
        log.info(f"VoltStream Orchestrator starting")
        log.info(f"  Battery: {self.state.battery['power_mw']}MW / {self.state.battery['capacity_mwh']}MWh")
        log.info(f"  Node: {self.state.battery['node']}")
        log.info(f"  Modules loaded: {list(self.modules.keys())}")
        log.info(f"  Tick interval: {tick_interval}s")
        log.info(f"  Ticks: {'unlimited' if n_ticks is None else n_ticks}")
        
        while self.running:
            try:
                self.tick()
                tick_count += 1
                
                if n_ticks and tick_count >= n_ticks:
                    break
                
                if n_ticks is None or tick_count < n_ticks:
                    time.sleep(tick_interval)
                    
            except KeyboardInterrupt:
                log.info("Orchestrator stopped by user")
                self.running = False
            except Exception as e:
                log.error(f"Tick failed: {e}")
                time.sleep(10)
        
        log.info(f"Orchestrator stopped after {tick_count} ticks")
    
    def status(self) -> dict:
        """Get current brain status."""
        return {
            'tick': self.state.tick,
            'running': self.running,
            'current_price': self.state.current_price,
            'soc': self.state.battery['soc'],
            'last_decision': self.state.decision,
            'modules_loaded': list(self.modules.keys()),
            'modules_available': len(self.modules),
            'price_history_length': len(self.state.price_history),
            'decisions_made': len(self.state.decision_history),
        }


def demo():
    """Run the orchestrator for 5 ticks to demonstrate."""
    
    print("=" * 70)
    print("VoltStream AI — Master Orchestrator")
    print("=" * 70)
    print()
    print("  Every 5 minutes, the brain:")
    print("  SENSE -> RECALL -> REASON -> PLAN -> COMPETE -> SCAN -> DECIDE -> ACT -> LEARN")
    print()
    print("  Running 5 ticks to demonstrate...")
    print()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )
    
    orchestrator = Orchestrator(db_path=':memory:')
    
    print(f"  Modules loaded: {list(orchestrator.modules.keys())}")
    print(f"  Battery: {orchestrator.state.battery['power_mw']}MW / {orchestrator.state.battery['capacity_mwh']}MWh")
    print(f"  Starting SOC: {orchestrator.state.battery['soc']*100:.0f}%")
    print()
    
    # Run 5 ticks with no delay
    orchestrator.run(n_ticks=5, interval=0)
    
    # Show summary
    status = orchestrator.status()
    print(f"\n{'='*70}")
    print("ORCHESTRATOR SUMMARY")
    print(f"{'='*70}")
    print(f"  Ticks completed: {status['tick']}")
    print(f"  Final SOC: {status['soc']*100:.1f}%")
    print(f"  Modules active: {status['modules_available']}")
    print(f"  Decisions made: {status['decisions_made']}")
    
    print(f"\n  Decision history:")
    for i, d in enumerate(orchestrator.state.decision_history, 1):
        print(f"    Tick {i}: {d['action']} (conf={d['confidence']:.0%}, "
              f"{d['n_modules_voted']} modules)")
    
    print(f"\n{'='*70}")
    print("THIS IS THE HEARTBEAT.")
    print(f"{'='*70}")
    print()
    print("  Every module we built now runs together:")
    print("  ML forecasting + RAG memory + Causal reasoning +")
    print("  Monte Carlo planning + Game theory + Cross-domain +")
    print("  Self-learning. All feeding one decision every 5 minutes.")
    print()
    print("  To run live:")
    print("    python -m core.orchestrator")
    print()
    print("  To run forever (production):")
    print("    nohup python -m core.orchestrator &")


if __name__ == '__main__':
    demo()
