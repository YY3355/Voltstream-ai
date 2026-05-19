"""
VoltStream AI — Unified Orchestrator v2
=========================================
Everything connected. Nothing disconnected.

Every tick:
1. OBSERVE   — Observability starts timing
2. SENSE     — Pull real prices + weather
3. GROUND    — Feedback loop scores last tick against reality
4. WEIGHT    — Get adaptive module weights from feedback loop
5. RECALL    — Hybrid RAG (vector + knowledge graph + router)
6. REASON    — Causal engine (weighted by adaptive trust)
7. PLAN      — Monte Carlo futures (weighted)
8. COMPETE   — Game theory (weighted)
9. SCAN      — Cross-domain signals (weighted)
10. PACK     — Context manager budgets tokens
11. DECIDE   — Weighted vote across all modules
12. ACT      — Execute on battery
13. RECORD   — Observability logs structured JSON
14. LEARN    — Feed decision to RAG + feedback loop + self-learner
15. HEALTH   — Health monitor checks all systems

One loop. Every component feeds every other component.
"""

import numpy as np
import json
import time
import os
import logging
from datetime import datetime
from typing import Dict, Optional

log = logging.getLogger('voltstream.orchestrator')


class BrainState:
    """Complete state of the brain at any moment."""
    
    def __init__(self, battery_config: dict = None):
        self.battery = battery_config or {
            'power_mw': 100, 'capacity_mwh': 400, 'soc': 0.50,
            'min_soc': 0.05, 'max_soc': 0.95, 'rte': 0.87,
            'node': 'HB_HOUSTON',
        }
        self.current_price = 0
        self.prices = {}
        self.weather = {}
        self.hour = datetime.now().hour
        self.timestamp = datetime.now()
        self.price_history = []
        self.max_history = 2000
        
        self.module_outputs = {}
        self.situation = {}
        self.condition = 'normal'
        self.module_weights = {}
        self.rag_context = {}
        self.hybrid_rag_context = {}
        self.packed_context = ''
        
        self.decision = {}
        self.decision_history = []
        self.tick = 0


class DataLayer:
    """Pulls real prices and weather."""
    
    def __init__(self):
        self.ercot_url = 'https://www.ercot.com/content/cdr/html/real_time_spp.html'
        self.weather_url = 'https://api.open-meteo.com/v1/forecast'
    
    def pull_prices(self) -> dict:
        try:
            import pandas as pd
            tables = pd.read_html(self.ercot_url)
            if tables:
                df = tables[0]
                prices = {}
                for hub in ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'HB_PAN']:
                    if hub in df.columns:
                        prices[hub] = float(df[hub].iloc[-1])
                if prices:
                    return {'source': 'ercot_live', 'prices': prices}
        except Exception:
            pass
        hour = datetime.now().hour
        base = self._synthetic_price(hour)
        return {'source': 'synthetic', 'prices': {
            'HB_HOUSTON': base + np.random.normal(0, 3),
            'HB_NORTH': base + np.random.normal(2, 3),
            'HB_SOUTH': base + np.random.normal(-2, 3),
            'HB_WEST': base + np.random.normal(5, 8),
        }}
    
    def pull_weather(self) -> dict:
        locations = {'houston': (29.76, -95.37), 'west_texas': (32.0, -101.0)}
        weather = {}
        for name, (lat, lon) in locations.items():
            try:
                import requests
                r = requests.get(self.weather_url, params={
                    'latitude': lat, 'longitude': lon,
                    'current': 'temperature_2m,wind_speed_10m,cloud_cover',
                    'temperature_unit': 'fahrenheit', 'wind_speed_unit': 'mph',
                }, timeout=5)
                if r.status_code == 200:
                    d = r.json().get('current', {})
                    weather[name] = {'temperature': d.get('temperature_2m', 75),
                                     'wind_speed': d.get('wind_speed_10m', 15),
                                     'cloud_cover': d.get('cloud_cover', 50)}
            except Exception:
                weather[name] = {'temperature': 75, 'wind_speed': 15, 'cloud_cover': 50}
        if not weather:
            weather = {'houston': {'temperature': 80, 'wind_speed': 12, 'cloud_cover': 30},
                       'west_texas': {'temperature': 85, 'wind_speed': 18, 'cloud_cover': 20}}
        return weather
    
    def _synthetic_price(self, hour):
        p = {0:35,1:32,2:30,3:28,4:27,5:30,6:25,7:20,8:12,9:5,10:3,11:2,
             12:3,13:5,14:8,15:15,16:30,17:45,18:55,19:50,20:42,21:38,22:36,23:35}
        return p.get(hour, 30) + np.random.normal(0, 5)


class UnifiedOrchestrator:
    """The complete brain. One loop. Everything connected."""
    
    def __init__(self, battery_config: dict = None, db_path: str = ':memory:'):
        self.state = BrainState(battery_config)
        self.data = DataLayer()
        self.obs = None
        self.feedback = None
        self.hybrid_rag = None
        self.context_mgr = None
        self.modules = {}
        self._load_systems()
        self._load_modules()
        self.running = False
        self.tick_interval = 300
    
    def _load_systems(self):
        for name, path, cls_name in [
            ('obs', 'core.observability', 'Observability'),
            ('feedback', 'core.feedback_loop', 'LiveFeedbackLoop'),
            ('hybrid_rag', 'core.hybrid_rag', 'HybridRAG'),
            ('context_mgr', 'core.context_manager', 'ContextWindowManager'),
        ]:
            try:
                mod = __import__(path, fromlist=[cls_name])
                cls = getattr(mod, cls_name)
                if name == 'obs':
                    self.obs = cls(log_path='logs/voltstream.jsonl')
                elif name == 'context_mgr':
                    self.context_mgr = cls(max_tokens=4000)
                else:
                    setattr(self, name, cls())
                log.info(f"  Loaded: {name}")
            except Exception as e:
                log.warning(f"  Skipped: {name} ({e})")
    
    def _load_modules(self):
        module_map = {
            'ml_forecast': ('models.production_ml', 'ProductionMLForecaster'),
            'ensemble': ('models.ensemble', 'EnsembleForecaster'),
            'causal': ('core.causal_engine', 'CausalReasoningEngine'),
            'planning': ('core.planning_engine', 'AnticipatoryPlanner'),
            'game_theory': ('agents.game_theory', 'GameTheoryEngine'),
            'cross_domain': ('agents.cross_domain', 'CrossDomainSynthesizer'),
            'self_learning': ('agents.self_learning', 'SelfDirectedLearner'),
            'rag': ('core.rag_engine_v2', 'RAGEngineV2'),
        }
        for name, (mod_path, cls_name) in module_map.items():
            try:
                mod = __import__(mod_path, fromlist=[cls_name])
                self.modules[name] = getattr(mod, cls_name)()
                log.info(f"  Loaded: {name}")
            except Exception as e:
                log.warning(f"  Skipped: {name} ({e})")
    
    def tick(self) -> dict:
        """ONE TICK. The unified heartbeat."""
        tick_start = time.time()
        self.state.tick += 1
        self.state.timestamp = datetime.now()
        self.state.hour = self.state.timestamp.hour
        self.state.module_outputs = {}
        modules_failed = []
        
        # 1. OBSERVE
        if self.obs:
            self.obs.on_tick_start(self.state.tick)
        
        # 2. SENSE
        price_data = self.data.pull_prices()
        self.state.prices = price_data['prices']
        self.state.current_price = self.state.prices.get(
            self.state.battery['node'],
            list(self.state.prices.values())[0] if self.state.prices else 30)
        self.state.weather = self.data.pull_weather()
        self.state.price_history.append(self.state.current_price)
        if len(self.state.price_history) > self.state.max_history:
            self.state.price_history = self.state.price_history[-self.state.max_history:]
        
        hw = self.state.weather.get('houston', {})
        ww = self.state.weather.get('west_texas', {})
        self.state.situation = {
            'price': self.state.current_price, 'hour': self.state.hour,
            'temperature': hw.get('temperature', 75),
            'wind_speed': ww.get('wind_speed', 15),
            'solar_ghi': max(0, (1 - hw.get('cloud_cover', 50)/100) * 800) if 6 < self.state.hour < 19 else 0,
            'soc': self.state.battery['soc'],
            'price_1h_ago': self.state.price_history[-12] if len(self.state.price_history) > 12 else self.state.current_price,
            'price_4h_ago': self.state.price_history[-48] if len(self.state.price_history) > 48 else self.state.current_price,
        }
        self.state.condition = self._classify_condition()
        
        # 3. GROUND (feedback scores last tick)
        if self.feedback and self.state.tick > 1:
            try:
                self.feedback.record_tick(self.state.tick, self.state.current_price,
                                          self.state.hour, self.state.module_outputs,
                                          self.state.decision, {'condition': self.state.condition})
            except Exception as e:
                if self.obs: self.obs.on_error(e, 'feedback', self.state.tick)
        
        # 4. WEIGHT (adaptive module weights)
        if self.feedback:
            self.state.module_weights = self.feedback.get_module_weights(self.state.condition)
        else:
            self.state.module_weights = {m: 1.0 for m in self.modules}
        
        # 5-9. RUN MODULES (each timed and reported to observability)
        def run_module(name, fn):
            try:
                t0 = time.time()
                result = fn()
                lat = (time.time() - t0) * 1000
                self.state.module_outputs[name] = result
                if self.obs: self.obs.on_module_run(name, lat, True)
                return result
            except Exception as e:
                modules_failed.append(name)
                if self.obs: self.obs.on_error(e, name, self.state.tick)
                return None
        
        # 5. RECALL (hybrid RAG)
        if self.hybrid_rag:
            signals = {}
            if self.state.current_price > 80: signals['high_price'] = True
            if ww.get('wind_speed', 15) < 7: signals['low_wind'] = True
            hrag = run_module('hybrid_rag', lambda: self.hybrid_rag.retrieve(self.state.situation, signals))
            if hrag: self.state.hybrid_rag_context = hrag
        
        if 'rag' in self.modules:
            rag = run_module('rag', lambda: self.modules['rag'].retrieve_and_reason(self.state.situation))
            if rag: self.state.rag_context = rag.get('analysis', {})
        
        # 6. REASON
        if 'causal' in self.modules:
            run_module('causal', lambda: self.modules['causal'].reason({
                'temperature': hw.get('temperature', 75), 'wind_speed': ww.get('wind_speed', 15),
                'solar_ghi': self.state.situation['solar_ghi'], 'hour': self.state.hour, 'gas_price': 3.50,
            }))
        
        # 7. PLAN
        if 'planning' in self.modules:
            run_module('planning', lambda: self.modules['planning'].plan(
                current_price=self.state.current_price, current_soc=self.state.battery['soc'],
                current_hour=self.state.hour, n_simulations=50,
            ))
        
        # 8. COMPETE
        if 'game_theory' in self.modules:
            run_module('game_theory', lambda: self.modules['game_theory'].analyze(
                current_price=self.state.current_price, hour=self.state.hour,
                our_soc=self.state.battery['soc'],
            ))
        
        # 9. SCAN
        if 'cross_domain' in self.modules:
            run_module('cross_domain', lambda: self.modules['cross_domain'].synthesize())
        
        # 10. PACK
        if self.context_mgr:
            try:
                trades = [{'similarity': 0.8, 'action': self.state.rag_context.get('best_action', 'HOLD'),
                          'revenue': self.state.rag_context.get('best_avg_revenue', 0),
                          'was_correct': 1, 'price': self.state.current_price,
                          'hour': self.state.hour, 'rerank_score': 0.7}] if self.state.rag_context.get('has_history') else []
                packed = self.context_mgr.build_context(self.state.situation, trades, [])
                self.state.packed_context = packed.get('context', '')
            except Exception:
                pass
        
        # 11. DECIDE (weighted)
        decision = self._weighted_decide()
        self.state.decision = decision
        self.state.decision_history.append(decision)
        
        # 12. ACT
        self._execute(decision)
        
        # 13. RECORD
        tick_duration = (time.time() - tick_start) * 1000
        tick_data = {
            'tick': self.state.tick, 'price': round(self.state.current_price, 2),
            'price_source': price_data['source'], 'action': decision['action'],
            'intensity': decision['intensity'], 'confidence': round(decision['confidence'], 3),
            'soc': round(self.state.battery['soc'], 4), 'hour': self.state.hour,
            'condition': self.state.condition, 'n_modules_voted': decision['n_modules_voted'],
            'modules_failed': modules_failed, 'latency_ms': round(tick_duration, 1),
            'module_weights': {k: round(v, 2) for k, v in self.state.module_weights.items()},
        }
        health = self.obs.on_tick_complete(self.state.tick, tick_data) if self.obs else {'status': 'no_obs'}
        
        # 14. LEARN
        if self.hybrid_rag:
            try:
                self.hybrid_rag.add_experience(self.state.situation, decision['action'], 0, True)
            except Exception:
                pass
        
        if 'self_learning' in self.modules and self.state.tick % 24 == 0:
            run_module('self_learning', lambda: self.modules['self_learning'].learn())
        
        return {**decision, 'tick': self.state.tick, 'price': self.state.current_price,
                'soc': self.state.battery['soc'], 'condition': self.state.condition,
                'latency_ms': tick_duration, 'health': health.get('status', 'unknown'),
                'modules_failed': modules_failed, 'adaptive_weights': dict(self.state.module_weights)}
    
    def _weighted_decide(self) -> dict:
        """Combine module outputs using ADAPTIVE weights from feedback."""
        votes = []
        w = self.state.module_weights
        o = self.state.module_outputs
        price = self.state.current_price
        soc = self.state.battery['soc']
        
        # ML forecast
        if 'ml_forecast' in self.modules:
            try:
                ml = self.modules['ml_forecast'].predict(price, {'houston_temp': self.state.situation.get('temperature', 75)}, hour=self.state.hour)
                o['ml_forecast'] = ml
                mw = w.get('ml_forecast', 1.0)
                p1h = ml.get('price_1h', price)
                if price > 50 and soc > 0.15: votes.append(('DISCHARGE', 0.7*mw, f'ML: high ${price:.0f}'))
                elif price < 10 and soc < 0.85: votes.append(('CHARGE', 0.7*mw, f'ML: low ${price:.0f}'))
                elif p1h > price+15 and soc < 0.80: votes.append(('CHARGE', 0.6*mw, 'ML: price rising'))
                elif p1h < price-10 and soc > 0.20: votes.append(('DISCHARGE', 0.6*mw, 'ML: price falling'))
            except Exception: pass
        
        # RAG
        rc = self.state.rag_context
        if rc and rc.get('has_history'):
            rw = w.get('rag', 1.0)
            best = rc.get('best_action', 'HOLD')
            sr = rc.get('success_rate', 0.5)
            if sr > 0.6: votes.append((best, sr*0.8*rw, f'RAG: {best} ({sr:.0%})'))
        
        # Causal
        c = o.get('causal', {})
        if c:
            cw = w.get('causal', 1.0)
            rec = c.get('battery_recommendation', {})
            if rec.get('action') in ['CHARGE','DISCHARGE']:
                votes.append((rec['action'], rec.get('confidence',0.5)*cw, f"Causal: {rec.get('reason','')[:50]}"))
        
        # Planning
        p = o.get('planning', {})
        if p:
            pw = w.get('planning', 1.0)
            a = p.get('recommended_action', 'HOLD')
            sh = p.get('recommended_details', {}).get('sharpe', 0)
            if 'CHARGE' in a: votes.append(('CHARGE', min(0.9,sh)*pw, f'Plan: {a}'))
            elif 'DISCHARGE' in a: votes.append(('DISCHARGE', min(0.9,sh)*pw, f'Plan: {a}'))
        
        # Game theory
        g = o.get('game_theory', {})
        if g:
            gw = w.get('game_theory', 1.0)
            s = g.get('our_strategy', {})
            a = s.get('action', 'DEFER')
            if a not in ['DEFER','HOLD']:
                votes.append((a, s.get('confidence',0.5)*gw, f"GT: {s.get('strategy_type','')}"))
        
        # Cross-domain
        x = o.get('cross_domain', {})
        if x:
            xw = w.get('cross_domain', 1.0)
            b = x.get('market_bias', 'neutral')
            if 'bullish' in b and soc < 0.80: votes.append(('CHARGE', 0.5*xw, f'XD: {b}'))
            elif b == 'strongly_bearish' and soc > 0.20: votes.append(('DISCHARGE', 0.5*xw, f'XD: {b}'))
        
        # Hybrid RAG structural
        hr = self.state.hybrid_rag_context
        if hr and hr.get('graph_results', 0) > 0:
            fc = hr.get('fused_context', '').lower()
            if 'congestion' in fc or 'outage' in fc:
                votes.append(('HOLD', 0.4, 'HybridRAG: grid stress'))
        
        # Overrides
        if price < 0: votes = [('CHARGE', 0.95, f'OVERRIDE: neg ${price:.1f}')]
        elif price > 200 and soc > 0.10: votes = [('DISCHARGE', 0.95, f'OVERRIDE: ${price:.0f}')]
        
        if not votes:
            return {'action':'HOLD','intensity':0,'confidence':0.5,'reasoning':'No signal.',
                    'votes':[],'n_modules_voted':0}
        
        scores = {}
        reasons = {}
        for a, c, r in votes:
            scores[a] = scores.get(a, 0) + c
            reasons.setdefault(a, []).append(r)
        
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        cons = scores[best] / max(total, 0.01)
        intensity = min(1.0, cons*0.8+0.2)
        
        if best == 'DISCHARGE' and soc < self.state.battery['min_soc']+0.05: best, intensity = 'HOLD', 0
        elif best == 'CHARGE' and soc > self.state.battery['max_soc']-0.05: best, intensity = 'HOLD', 0
        
        return {'action': best, 'intensity': round(intensity, 2), 'confidence': round(cons, 3),
                'reasoning': ' | '.join(reasons.get(best, [])),
                'votes': [{'action':a,'conf':round(c,3),'reason':r} for a,c,r in votes],
                'n_modules_voted': len(votes), 'all_scores': {k:round(v,3) for k,v in scores.items()}}
    
    def _execute(self, decision):
        a, i = decision['action'], decision['intensity']
        pw = self.state.battery['power_mw'] * i
        eff = np.sqrt(self.state.battery['rte'])
        cap = self.state.battery['capacity_mwh']
        if a == 'CHARGE':
            self.state.battery['soc'] = min(self.state.battery['max_soc'], self.state.battery['soc'] + pw*eff/12/cap)
        elif a == 'DISCHARGE':
            self.state.battery['soc'] = max(self.state.battery['min_soc'], self.state.battery['soc'] - pw/eff/12/cap)
    
    def _classify_condition(self):
        p, h = self.state.current_price, self.state.hour
        if p > 80: return 'spike'
        elif p < 0: return 'negative'
        elif p < 10: return 'low'
        elif 17 <= h <= 21: return 'evening_peak'
        elif 8 <= h <= 16: return 'midday'
        return 'overnight'
    
    def run(self, n_ticks=None, interval=None):
        self.running = True
        iv = interval or self.tick_interval
        count = 0
        if self.obs: self.obs.on_event('startup', f'{len(self.modules)} modules loaded')
        while self.running:
            try:
                r = self.tick()
                count += 1
                log.info(f"  Tick {r['tick']} | ${r['price']:.2f} | {r['action']} | conf={r['confidence']:.0%} | "
                         f"{r['latency_ms']:.0f}ms | health={r['health']} | SOC={r['soc']*100:.1f}%")
                if n_ticks and count >= n_ticks: break
                if n_ticks is None or count < n_ticks: time.sleep(iv)
            except KeyboardInterrupt: self.running = False
            except Exception as e:
                if self.obs: self.obs.on_error(e, 'orchestrator', self.state.tick)
                time.sleep(10)
        if self.obs: self.obs.on_event('shutdown', f'{count} ticks')
    
    def status(self) -> dict:
        r = {'tick': self.state.tick, 'price': self.state.current_price,
             'soc': self.state.battery['soc'], 'condition': self.state.condition,
             'modules': list(self.modules.keys()),
             'systems': {'obs': self.obs is not None, 'feedback': self.feedback is not None,
                         'hybrid_rag': self.hybrid_rag is not None, 'context_mgr': self.context_mgr is not None},
             'adaptive_weights': dict(self.state.module_weights)}
        if self.feedback: r['feedback'] = self.feedback.get_performance_report()
        if self.obs: r['observability'] = self.obs.get_status()
        return r


# Keep backward compatibility
Orchestrator = UnifiedOrchestrator


def demo():
    print("=" * 70)
    print("VoltStream AI — Unified Orchestrator v2")
    print("=" * 70)
    print("\n  Everything connected. One loop. 15 steps.\n")
    
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    o = UnifiedOrchestrator()
    
    print(f"\n  Modules: {list(o.modules.keys())}")
    print(f"  Systems: obs={'Y' if o.obs else 'N'} feedback={'Y' if o.feedback else 'N'} "
          f"hrag={'Y' if o.hybrid_rag else 'N'} ctx={'Y' if o.context_mgr else 'N'}")
    print(f"\n  Running 3 ticks...\n")
    
    o.run(n_ticks=3, interval=0)
    
    s = o.status()
    print(f"\n  Ticks: {s['tick']} | SOC: {s['soc']*100:.1f}% | Systems: {sum(s['systems'].values())}/4")
    if s.get('adaptive_weights'):
        print(f"  Weights: {', '.join(f'{k}={v:.2f}' for k,v in sorted(s['adaptive_weights'].items()))}")


if __name__ == '__main__':
    demo()
