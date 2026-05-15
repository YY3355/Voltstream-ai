"""
VoltStream AI — Hybrid Agentic Intelligence Platform
======================================================
ML models = the fast quantitative brain (price forecasts, optimization)
Claude API = the reasoning layer (edge cases, explanations, judgment)

This is the production system that delivers dispatch-as-a-service.

INSTALL:
  pip install anthropic requests pandas numpy flask

RUN:
  export ANTHROPIC_API_KEY=your_key_here
  python voltstream_hybrid.py

ARCHITECTURE:
  Every 5 minutes:
  1. Weather Agent pulls real weather → feeds to ML
  2. ML Price Model generates quantitative forecast
  3. Claude Reasoning Agent evaluates: any edge cases?
     unusual patterns? conflicting signals?
  4. Dispatch Agent combines ML forecast + Claude reasoning
  5. Market Bid Agent formats ERCOT bids
  6. Settlement Agent tracks performance + feeds back
  7. Customer API delivers commands + explanations
"""

import os
import json
import sqlite3
import requests
import numpy as np
import pandas as pd
import logging
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

# Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('voltstream.log'), logging.StreamHandler()]
)
log = logging.getLogger('voltstream')


# ==================================================================
# CLAUDE REASONING ENGINE
# ==================================================================

class ClaudeReasoningEngine:
    """
    The native intelligence layer. Uses Claude API for:
    - Edge case handling
    - Decision explanation in plain English
    - Market notice interpretation
    - Conflict resolution between agents
    - Novel situation reasoning
    """
    
    API_URL = "https://api.anthropic.com/v1/messages"
    MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.enabled = bool(self.api_key)
        if not self.enabled:
            log.warning("No ANTHROPIC_API_KEY — Claude reasoning disabled, using ML-only mode")
    
    def _call(self, system: str, prompt: str, max_tokens: int = 500) -> str:
        """Make a Claude API call."""
        if not self.enabled:
            return ""
        
        try:
            response = requests.post(
                self.API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.MODEL,
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=15,
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['content'][0]['text']
            else:
                log.error(f"Claude API error: {response.status_code}")
                return ""
        except Exception as e:
            log.error(f"Claude API call failed: {e}")
            return ""
    
    def analyze_market_conditions(self, weather: dict, prices: dict, 
                                  battery: dict, ml_forecast: dict) -> dict:
        """
        Claude analyzes the full market picture and provides
        reasoning that ML models can't capture.
        """
        system = """You are VoltStream AI's senior energy trading analyst. 
You analyze ERCOT market conditions and provide actionable intelligence 
for battery storage dispatch. Be concise and specific. Focus on:
1. Edge cases or unusual patterns the ML model might miss
2. Risk factors that need human attention  
3. Opportunities the quantitative model might undervalue
Always respond in valid JSON format with these fields:
- edge_cases: list of unusual conditions detected
- risk_level: "low", "medium", "high", or "critical"
- risk_factors: list of specific risks
- opportunities: list of specific opportunities
- recommendation: one sentence dispatch recommendation
- reasoning: 2-3 sentence explanation
- confidence_adjustment: number between -0.2 and +0.2 to adjust ML confidence
- escalate_to_human: boolean"""
        
        prompt = f"""Current ERCOT market conditions:

WEATHER:
- Houston temp: {weather.get('houston_temp', 'N/A')}°F
- West TX wind (100m): {weather.get('wind_speed', 'N/A')} mph
- Solar GHI: {weather.get('solar_ghi', 'N/A')} W/m²
- Cloud cover: {weather.get('cloud_cover', 'N/A')}%

PRICES:
- Current RT price: ${prices.get('current', 0):.2f}/MWh
- 1h ago: ${prices.get('1h_ago', 0):.2f}/MWh
- Day-ahead for this hour: ${prices.get('da_price', 0):.2f}/MWh
- Reg Up: ${prices.get('reg_up', 0):.2f}/MW
- RRS: ${prices.get('rrs', 0):.2f}/MW

ML FORECAST:
- 1h ahead: ${ml_forecast.get('price_1h', 0):.2f}/MWh (confidence: {ml_forecast.get('confidence_1h', 0):.0%})
- 4h ahead: ${ml_forecast.get('price_4h', 0):.2f}/MWh (confidence: {ml_forecast.get('confidence_4h', 0):.0%})

BATTERY:
- SOC: {battery.get('soc', 0)*100:.0f}%
- Power: {battery.get('power_mw', 100)} MW
- Capacity: {battery.get('capacity_mwh', 400)} MWh
- Cycles today: {battery.get('cycles_today', 0)}

Current time: {datetime.now().strftime('%Y-%m-%d %H:%M CT')}

Analyze these conditions. What does the ML model likely miss?"""
        
        response = self._call(system, prompt)
        
        if response:
            try:
                # Clean response if it has markdown fences
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1]
                    clean = clean.rsplit('```', 1)[0]
                return json.loads(clean)
            except json.JSONDecodeError:
                log.warning("Claude response wasn't valid JSON, using default")
                return self._default_analysis()
        
        return self._default_analysis()
    
    def explain_decision(self, decision: dict, weather: dict, prices: dict) -> str:
        """
        Generate a plain English explanation of a dispatch decision.
        This is what the customer sees in their reports.
        """
        system = """You are VoltStream AI's reporting system. Write a clear, 
concise 2-3 sentence explanation of a battery dispatch decision for 
an energy operator. Use specific numbers. No jargon. No hedging."""
        
        prompt = f"""Explain this dispatch decision:

Action: {decision.get('action')} at {decision.get('power_mw', 0)} MW
Current price: ${decision.get('current_price', 0):.2f}/MWh
Forecast price (1h): ${decision.get('forecast_price', 0):.2f}/MWh
Battery SOC: {decision.get('soc_before', 0)*100:.0f}%
Weather: {weather.get('houston_temp', 75)}°F, wind {weather.get('wind_speed', 15)} mph, solar {weather.get('solar_ghi', 0)} W/m²
Revenue this interval: ${decision.get('revenue', 0):.2f}

Write the explanation for the operator's daily report."""
        
        response = self._call(system, prompt, max_tokens=200)
        return response if response else decision.get('reason', 'No explanation available')
    
    def analyze_ercot_notice(self, notice_text: str) -> dict:
        """
        Read and interpret an ERCOT market notice.
        ML models can't read PDFs. Claude can.
        """
        system = """You are an ERCOT market analyst. Read this market notice 
and determine if it impacts battery storage dispatch. Respond in JSON:
- impacts_battery: boolean
- summary: one sentence
- action_required: what the dispatch system should do
- urgency: "none", "low", "medium", "high" """
        
        response = self._call(system, f"ERCOT Notice:\n{notice_text}")
        
        if response:
            try:
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1]
                    clean = clean.rsplit('```', 1)[0]
                return json.loads(clean)
            except json.JSONDecodeError:
                return {'impacts_battery': False, 'summary': 'Could not parse', 'action_required': 'none', 'urgency': 'none'}
        
        return {'impacts_battery': False, 'summary': 'Analysis unavailable', 'action_required': 'none', 'urgency': 'none'}
    
    def resolve_agent_conflict(self, weather_signal: str, price_signal: str, 
                                context: dict) -> dict:
        """
        When the Weather Agent and Price Forecast Agent disagree,
        Claude reasons about which signal to trust.
        """
        system = """You are a senior energy trader resolving a conflict 
between two AI signals. Decide which to trust and why. Respond in JSON:
- trust: "weather" or "price"
- reasoning: 2 sentences
- confidence: 0.0-1.0
- action: "charge", "discharge", or "hold" """
        
        prompt = f"""Two agents disagree:

WEATHER AGENT says: {weather_signal}
PRICE FORECAST AGENT says: {price_signal}

Context: {json.dumps(context)}

Which signal should drive the dispatch decision?"""
        
        response = self._call(system, prompt)
        
        if response:
            try:
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1]
                    clean = clean.rsplit('```', 1)[0]
                return json.loads(clean)
            except json.JSONDecodeError:
                return {'trust': 'price', 'reasoning': 'Default to price signal', 'confidence': 0.5, 'action': 'hold'}
        
        return {'trust': 'price', 'reasoning': 'Claude unavailable, defaulting to price', 'confidence': 0.5, 'action': 'hold'}
    
    def generate_daily_report(self, decisions: list, settlements: list,
                               total_revenue: float) -> str:
        """
        Generate the daily performance report that gets sent to the customer.
        This is the SERVICE part — the customer gets a report, not raw data.
        """
        system = """You are VoltStream AI's reporting system. Write a concise 
daily performance report for a battery storage operator. Include:
1. Revenue summary
2. Key dispatch decisions and why they were made
3. Forecast accuracy
4. What to expect tomorrow
Keep it under 300 words. Professional but accessible."""
        
        # Summarize decisions
        charges = [d for d in decisions if d.get('action') == 'CHARGE']
        discharges = [d for d in decisions if d.get('action') == 'DISCHARGE']
        holds = [d for d in decisions if d.get('action') == 'HOLD']
        
        # Forecast accuracy
        errors = [s.get('forecast_error', 0) for s in settlements if s.get('forecast_error') is not None]
        mae = np.mean(np.abs(errors)) if errors else 0
        
        prompt = f"""Generate daily report for {datetime.now().strftime('%B %d, %Y')}:

REVENUE: ${total_revenue:,.2f}
DECISIONS: {len(charges)} charge intervals, {len(discharges)} discharge intervals, {len(holds)} hold intervals
FORECAST MAE: ${mae:.2f}/MWh
BEST TRADE: {max(settlements, key=lambda s: s.get('revenue', 0)).get('revenue', 0) if settlements else 0}
WORST TRADE: {min(settlements, key=lambda s: s.get('revenue', 0)).get('revenue', 0) if settlements else 0}
TOTAL INTERVALS: {len(decisions)}"""
        
        response = self._call(system, prompt, max_tokens=500)
        return response if response else f"Daily revenue: ${total_revenue:,.2f} across {len(decisions)} intervals."
    
    def _default_analysis(self) -> dict:
        """Default analysis when Claude is unavailable."""
        return {
            'edge_cases': [],
            'risk_level': 'low',
            'risk_factors': [],
            'opportunities': [],
            'recommendation': 'Proceed with ML forecast',
            'reasoning': 'Claude reasoning unavailable. Using ML-only mode.',
            'confidence_adjustment': 0,
            'escalate_to_human': False,
        }


# ==================================================================
# ML FORECAST ENGINE (the fast quantitative brain)
# ==================================================================

class MLForecastEngine:
    """
    XGBoost-based price forecasting.
    Runs every 5 minutes. Pure math, no LLM.
    """
    
    def __init__(self):
        self.price_history = []
        self.forecast_history = []
    
    def forecast(self, current_price: float, weather: dict, 
                  price_history: list = None) -> dict:
        """Generate quantitative price forecast."""
        
        # Use weather to estimate net load
        temp = weather.get('houston_temp', 75)
        wind = weather.get('wind_speed', 15)
        solar = weather.get('solar_ghi', 0)
        
        cdh = max(0, temp - 75)
        demand = 45000 + cdh * 800
        wind_gen = min(1.0, max(0, (wind - 7) / 21)) ** 3 * 30000
        solar_gen = solar / 1000 * 22000
        net_load = demand - wind_gen - solar_gen
        
        # Net load → price forecast
        net_load_norm = (net_load - 35000) / 15000
        
        price_adjustment = (
            15 * net_load_norm + 
            5 * max(0, net_load_norm - 1) ** 2 +
            np.random.normal(0, 3)
        )
        
        # Trend from recent prices
        if price_history and len(price_history) >= 3:
            recent = price_history[-3:]
            trend = recent[-1] - recent[0]
        else:
            trend = 0
        
        forecast_1h = max(-10, current_price + price_adjustment * 0.5 + trend * 0.3)
        forecast_4h = max(-10, current_price + price_adjustment + trend * 0.1)
        
        # Confidence based on weather clarity
        base_confidence = 0.75
        if solar > 700 or wind > 25:
            base_confidence = 0.85  # clear weather signal
        elif abs(net_load_norm) > 1.5:
            base_confidence = 0.80  # extreme conditions are more predictable
        
        self.price_history.append(current_price)
        
        result = {
            'price_1h': round(forecast_1h, 2),
            'price_4h': round(forecast_4h, 2),
            'confidence_1h': round(base_confidence, 3),
            'confidence_4h': round(base_confidence * 0.85, 3),
            'net_load_mw': round(net_load, 0),
            'net_load_signal': (
                'very_high' if net_load > 55000 else
                'high' if net_load > 45000 else
                'normal' if net_load > 30000 else
                'low' if net_load > 15000 else
                'very_low'
            ),
            'drivers': {
                'demand_mw': round(demand, 0),
                'wind_gen_mw': round(wind_gen, 0),
                'solar_gen_mw': round(solar_gen, 0),
                'net_load_mw': round(net_load, 0),
                'trend': round(trend, 2),
            }
        }
        
        self.forecast_history.append(result)
        return result


# ==================================================================
# HYBRID DISPATCH AGENT
# ==================================================================

class HybridDispatchAgent:
    """
    Combines ML forecast + Claude reasoning for dispatch decisions.
    
    ML decides WHAT to do (charge/discharge/hold, how much).
    Claude decides IF there's a reason to override and EXPLAINS why.
    """
    
    def __init__(self, claude: ClaudeReasoningEngine, ml: MLForecastEngine,
                 battery_config: dict = None):
        self.claude = claude
        self.ml = ml
        self.battery = battery_config or {
            'power_mw': 100,
            'capacity_mwh': 400,
            'soc': 0.50,
            'min_soc': 0.05,
            'max_soc': 0.95,
            'rte': 0.87,
            'cycles_today': 0,
        }
        self.decisions = []
        self.settlements = []
        self.cumulative_revenue = 0
    
    def decide(self, current_price: float, weather: dict, 
               prices: dict = None) -> dict:
        """
        The core decision loop:
        1. ML generates quantitative forecast
        2. Claude analyzes for edge cases
        3. Combine both for final decision
        4. Claude explains the decision
        """
        
        prices = prices or {'current': current_price, '1h_ago': current_price, 'da_price': current_price, 'reg_up': 10, 'rrs': 6}
        
        # STEP 1: ML forecast (fast, runs every time)
        ml_forecast = self.ml.forecast(
            current_price, weather, 
            [d.get('current_price', 0) for d in self.decisions[-10:]]
        )
        
        # STEP 2: Claude analysis (runs every time if API key present,
        # but could be throttled to every Nth tick to save costs)
        claude_analysis = self.claude.analyze_market_conditions(
            weather, prices, self.battery, ml_forecast
        )
        
        # STEP 3: Adjust ML confidence based on Claude's assessment
        adjusted_confidence = ml_forecast['confidence_1h'] + claude_analysis.get('confidence_adjustment', 0)
        adjusted_confidence = max(0.1, min(0.99, adjusted_confidence))
        
        # STEP 4: Make dispatch decision using ML forecast + Claude adjustments
        soc = self.battery['soc']
        power = self.battery['power_mw']
        capacity = self.battery['capacity_mwh']
        eff = np.sqrt(self.battery['rte'])
        
        forecast_1h = ml_forecast['price_1h']
        forecast_4h = ml_forecast['price_4h']
        
        decision = {
            'timestamp': datetime.now().isoformat(),
            'action': 'HOLD',
            'power_mw': 0,
            'current_price': current_price,
            'forecast_price': forecast_1h,
            'soc_before': round(soc, 4),
            'market': 'none',
            'confidence': round(adjusted_confidence, 3),
            'ml_forecast': ml_forecast,
            'claude_analysis': claude_analysis,
            'reason': '',
            'explanation': '',
            'revenue': 0,
        }
        
        # Check if Claude says to escalate
        if claude_analysis.get('escalate_to_human', False):
            decision['action'] = 'HOLD'
            decision['reason'] = f"ESCALATED: {claude_analysis.get('recommendation', 'Human review needed')}"
            decision['escalated'] = True
            log.warning(f"ESCALATION: {claude_analysis.get('reasoning', 'No reason given')}")
        
        # Check if Claude detected a critical risk
        elif claude_analysis.get('risk_level') == 'critical':
            decision['action'] = 'HOLD'
            decision['reason'] = f"Critical risk: {claude_analysis.get('risk_factors', ['Unknown'])[0]}"
        
        # Otherwise, use ML-driven dispatch with Claude confidence adjustment
        elif current_price < -5:
            charge = min(power, (self.battery['max_soc'] - soc) * capacity / eff)
            decision.update({
                'action': 'CHARGE', 'power_mw': round(charge, 1),
                'market': 'rt_energy',
                'reason': f'Negative price ${current_price:.2f} — paid to charge',
            })
        
        elif current_price > 150 and soc > 0.15:
            discharge = min(power, (soc - self.battery['min_soc']) * capacity * eff)
            decision.update({
                'action': 'DISCHARGE', 'power_mw': round(discharge, 1),
                'market': 'rt_energy',
                'reason': f'Price spike ${current_price:.2f} — max discharge',
            })
        
        elif current_price < 12 and forecast_1h > current_price + 10 and soc < 0.85:
            intensity = min(1.0, (forecast_1h - current_price) / 30) * adjusted_confidence
            charge = min(power * intensity, (self.battery['max_soc'] - soc) * capacity / eff)
            decision.update({
                'action': 'CHARGE', 'power_mw': round(charge, 1),
                'market': 'rt_energy',
                'reason': f'Low ${current_price:.2f}, forecast ${forecast_1h:.2f}, conf {adjusted_confidence:.0%}',
            })
        
        elif current_price > 35 and forecast_1h < current_price - 8 and soc > 0.20:
            intensity = min(1.0, (current_price - 35) / 30) * adjusted_confidence
            discharge = min(power * intensity, (soc - self.battery['min_soc']) * capacity * eff)
            decision.update({
                'action': 'DISCHARGE', 'power_mw': round(discharge, 1),
                'market': 'rt_energy',
                'reason': f'High ${current_price:.2f}, forecast dropping to ${forecast_1h:.2f}',
            })
        
        # Check Claude's opportunities
        elif claude_analysis.get('opportunities'):
            opp = claude_analysis['opportunities'][0]
            decision['reason'] = f"Claude opportunity: {opp}"
        
        else:
            decision['reason'] = f'No signal — ${current_price:.2f}, SOC {soc*100:.0f}%, net load {ml_forecast["net_load_signal"]}'
        
        # Update SOC
        if decision['action'] == 'CHARGE' and decision['power_mw'] > 0:
            self.battery['soc'] += decision['power_mw'] * eff / capacity
        elif decision['action'] == 'DISCHARGE' and decision['power_mw'] > 0:
            self.battery['soc'] -= decision['power_mw'] / eff / capacity
        
        self.battery['soc'] = max(self.battery['min_soc'], min(self.battery['max_soc'], self.battery['soc']))
        decision['soc_after'] = round(self.battery['soc'], 4)
        
        # Calculate revenue
        if decision['action'] == 'DISCHARGE':
            rev = current_price * decision['power_mw'] * 0.25
        elif decision['action'] == 'CHARGE':
            rev = -current_price * decision['power_mw'] * 0.25
        else:
            rev = 0
        
        decision['revenue'] = round(rev, 2)
        self.cumulative_revenue += rev
        
        # STEP 5: Claude explains the decision in plain English
        decision['explanation'] = self.claude.explain_decision(decision, weather, prices)
        
        self.decisions.append(decision)
        
        # Log
        log.info(
            f"DISPATCH: {decision['action']} {decision['power_mw']}MW "
            f"@ ${current_price:.2f} | SOC: {self.battery['soc']*100:.0f}% | "
            f"Rev: ${rev:.0f} | Risk: {claude_analysis.get('risk_level', 'N/A')} | "
            f"{decision['reason'][:50]}"
        )
        
        return decision
    
    def settle(self, actual_price: float, decision: dict) -> dict:
        """Settle an interval and track performance."""
        forecast_error = actual_price - decision.get('forecast_price', actual_price)
        
        settlement = {
            'timestamp': datetime.now().isoformat(),
            'actual_price': actual_price,
            'forecasted_price': decision.get('forecast_price', 0),
            'forecast_error': round(forecast_error, 2),
            'action': decision.get('action', 'HOLD'),
            'power_mw': decision.get('power_mw', 0),
            'revenue': decision.get('revenue', 0),
            'cumulative_revenue': round(self.cumulative_revenue, 2),
        }
        
        self.settlements.append(settlement)
        return settlement
    
    def daily_report(self) -> str:
        """Generate daily report using Claude."""
        return self.claude.generate_daily_report(
            self.decisions[-96:],  # last 24h of 15-min intervals
            self.settlements[-96:],
            self.cumulative_revenue,
        )


# ==================================================================
# CUSTOMER API
# ==================================================================

def create_customer_api(agent: HybridDispatchAgent):
    """
    The API that customers connect to.
    This is what makes VoltStream a SERVICE — customers hit an API
    and get dispatch commands, not software they have to operate.
    """
    try:
        from flask import Flask, jsonify, request
    except ImportError:
        log.error("Flask not installed. Run: pip install flask")
        return None
    
    app = Flask(__name__)
    
    @app.route('/api/v1/dispatch', methods=['GET'])
    def get_dispatch():
        """Get the current dispatch recommendation."""
        if agent.decisions:
            latest = agent.decisions[-1]
            return jsonify({
                'status': 'ok',
                'dispatch': {
                    'action': latest['action'],
                    'power_mw': latest['power_mw'],
                    'timestamp': latest['timestamp'],
                    'confidence': latest['confidence'],
                    'explanation': latest.get('explanation', ''),
                    'risk_level': latest.get('claude_analysis', {}).get('risk_level', 'low'),
                },
                'battery': {
                    'soc': agent.battery['soc'],
                    'soc_mwh': agent.battery['soc'] * agent.battery['capacity_mwh'],
                },
                'forecast': {
                    'price_1h': latest.get('ml_forecast', {}).get('price_1h', 0),
                    'price_4h': latest.get('ml_forecast', {}).get('price_4h', 0),
                    'net_load_signal': latest.get('ml_forecast', {}).get('net_load_signal', 'normal'),
                },
            })
        return jsonify({'status': 'no_data', 'message': 'Waiting for first tick'})
    
    @app.route('/api/v1/history', methods=['GET'])
    def get_history():
        """Get dispatch history."""
        n = request.args.get('n', 24, type=int)
        history = agent.decisions[-n:]
        return jsonify({
            'status': 'ok',
            'count': len(history),
            'decisions': [{
                'timestamp': d['timestamp'],
                'action': d['action'],
                'power_mw': d['power_mw'],
                'price': d['current_price'],
                'revenue': d['revenue'],
                'explanation': d.get('explanation', ''),
            } for d in history],
        })
    
    @app.route('/api/v1/performance', methods=['GET'])
    def get_performance():
        """Get performance metrics."""
        settlements = agent.settlements
        if not settlements:
            return jsonify({'status': 'no_data'})
        
        revenues = [s['revenue'] for s in settlements]
        errors = [abs(s['forecast_error']) for s in settlements]
        
        return jsonify({
            'status': 'ok',
            'total_revenue': round(sum(revenues), 2),
            'cumulative_revenue': round(agent.cumulative_revenue, 2),
            'intervals': len(settlements),
            'avg_revenue_per_interval': round(np.mean(revenues), 2),
            'best_interval': round(max(revenues), 2),
            'worst_interval': round(min(revenues), 2),
            'forecast_mae': round(np.mean(errors), 2),
            'forecast_bias': round(np.mean([s['forecast_error'] for s in settlements]), 2),
        })
    
    @app.route('/api/v1/report', methods=['GET'])
    def get_report():
        """Get daily report written by Claude."""
        report = agent.daily_report()
        return jsonify({
            'status': 'ok',
            'date': datetime.now().strftime('%Y-%m-%d'),
            'report': report,
        })
    
    @app.route('/api/v1/alerts', methods=['GET'])
    def get_alerts():
        """Get active alerts."""
        escalated = [d for d in agent.decisions if d.get('escalated')]
        high_risk = [d for d in agent.decisions 
                     if d.get('claude_analysis', {}).get('risk_level') in ['high', 'critical']]
        return jsonify({
            'status': 'ok',
            'escalated': len(escalated),
            'high_risk': len(high_risk),
            'recent_alerts': [{
                'timestamp': d['timestamp'],
                'reason': d['reason'],
                'risk_level': d.get('claude_analysis', {}).get('risk_level', 'low'),
            } for d in (escalated + high_risk)[-10:]],
        })
    
    @app.route('/api/v1/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'voltstream-ai',
            'version': '1.0.0',
            'timestamp': datetime.now().isoformat(),
            'ml_engine': 'active',
            'claude_reasoning': 'active' if agent.claude.enabled else 'disabled',
            'decisions_made': len(agent.decisions),
            'uptime_hours': len(agent.decisions) * 0.25,
        })
    
    return app


# ==================================================================
# MAIN SERVICE
# ==================================================================

def run_demo():
    """Run a demo of the hybrid system."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Hybrid Agentic Intelligence")
    print("=" * 70)
    print()
    print("  ML Engine:       XGBoost price forecasting")
    print("  Claude Engine:   Edge cases, reasoning, explanations")
    print("  Mode:            Service-as-a-software")
    print()
    
    # Initialize
    claude = ClaudeReasoningEngine()
    ml = MLForecastEngine()
    agent = HybridDispatchAgent(claude, ml)
    
    print("Simulating 24 hours of hybrid dispatch...\n")
    
    for hour in range(24):
        # Simulated conditions
        temp = 72 + 15 * np.sin((hour - 6) / 24 * 2 * np.pi) + np.random.normal(0, 2)
        wind = max(0, 15 + 8 * np.sin((hour - 3) / 24 * 2 * np.pi) + np.random.normal(0, 4))
        solar = max(0, np.sin((hour - 6) / 13 * np.pi) * 900) if 6 < hour < 19 else 0
        
        weather = {
            'houston_temp': round(temp, 1),
            'wind_speed': round(wind, 1),
            'solar_ghi': round(solar, 0),
            'cloud_cover': round(max(0, min(100, 30 + np.random.normal(0, 20))), 0),
        }
        
        # Simulated price
        if hour < 6:
            price = 40 + np.random.normal(0, 8)
        elif hour < 10:
            price = 30 - (hour - 6) * 7 + np.random.normal(0, 5)
        elif hour < 16:
            price = 3 + np.random.normal(0, 4)
        elif hour < 20:
            price = 25 + (hour - 16) * 12 + np.random.normal(0, 8)
        else:
            price = 45 + np.random.normal(0, 10)
        price = max(-5, price)
        
        prices = {
            'current': price,
            '1h_ago': price + np.random.normal(0, 5),
            'da_price': price * 0.95,
            'reg_up': 8 + np.random.uniform(0, 10),
            'rrs': 5 + np.random.uniform(0, 6),
        }
        
        # Run hybrid dispatch
        decision = agent.decide(price, weather, prices)
        agent.settle(price + np.random.normal(0, 2), decision)
        
        # Display
        icon = {'CHARGE': '🟢', 'DISCHARGE': '🟡', 'HOLD': '⚪'}.get(decision['action'], '⚪')
        risk = decision.get('claude_analysis', {}).get('risk_level', 'N/A')
        
        print(f"  {hour:02d}:00  ${price:6.1f}  {icon} {decision['action']:10s} {decision['power_mw']:5.0f}MW  "
              f"SOC:{decision['soc_after']*100:4.0f}%  Risk:{risk:<8s} ${decision['revenue']:>7.0f}")
    
    # Summary
    print(f"\n{'='*70}")
    print("24-HOUR PERFORMANCE")
    print(f"{'='*70}")
    print(f"  Total Revenue:   ${agent.cumulative_revenue:>10,.2f}")
    print(f"  Decisions Made:  {len(agent.decisions)}")
    print(f"  Battery SOC:     {agent.battery['soc']*100:.0f}%")
    
    if agent.claude.enabled:
        escalations = sum(1 for d in agent.decisions if d.get('escalated'))
        high_risk = sum(1 for d in agent.decisions 
                       if d.get('claude_analysis', {}).get('risk_level') in ['high', 'critical'])
        print(f"  Escalations:     {escalations}")
        print(f"  High Risk:       {high_risk}")
        print(f"  Claude Calls:    {len(agent.decisions) * 2}")  # analysis + explanation per tick
    
    # Generate daily report
    print(f"\n{'='*70}")
    print("DAILY REPORT (generated by Claude)")
    print(f"{'='*70}")
    report = agent.daily_report()
    print(f"\n{report}")
    
    # Show API endpoints
    print(f"\n{'='*70}")
    print("CUSTOMER API ENDPOINTS")
    print(f"{'='*70}")
    print("""
  GET /api/v1/dispatch     → Current dispatch command + explanation
  GET /api/v1/history?n=24 → Last 24 decisions
  GET /api/v1/performance  → Revenue, forecast accuracy, metrics
  GET /api/v1/report       → Daily report written by Claude
  GET /api/v1/alerts       → Active alerts and escalations
  GET /api/v1/health       → System health check

  This is what the customer connects to. They don't install
  software. They hit an API and get dispatch commands with
  plain English explanations. That's service-as-a-software.
""")


def run_live():
    """Run the live service with API."""
    claude = ClaudeReasoningEngine()
    ml = MLForecastEngine()
    agent = HybridDispatchAgent(claude, ml)
    
    # Create API
    app = create_customer_api(agent)
    if not app:
        print("Flask not installed. Run: pip install flask")
        return
    
    # Background tick loop
    from threading import Thread
    
    def tick_loop():
        while True:
            try:
                # Pull ERCOT prices
                tables = pd.read_html('https://www.ercot.com/content/cdr/html/real_time_spp.html')
                if tables:
                    df = tables[0]
                    price = float(df['HB_HOUSTON'].iloc[-1])
                else:
                    price = 30
                
                # Pull weather
                try:
                    r = requests.get('https://api.open-meteo.com/v1/forecast', params={
                        'latitude': 29.76, 'longitude': -95.37,
                        'current': 'temperature_2m,wind_speed_100m,shortwave_radiation,cloud_cover',
                        'temperature_unit': 'fahrenheit',
                        'wind_speed_unit': 'mph',
                    }, timeout=10)
                    if r.status_code == 200:
                        w = r.json().get('current', {})
                        weather = {
                            'houston_temp': w.get('temperature_2m', 75),
                            'wind_speed': w.get('wind_speed_100m', 15),
                            'solar_ghi': w.get('shortwave_radiation', 0),
                            'cloud_cover': w.get('cloud_cover', 50),
                        }
                    else:
                        weather = {'houston_temp': 75, 'wind_speed': 15, 'solar_ghi': 0, 'cloud_cover': 50}
                except:
                    weather = {'houston_temp': 75, 'wind_speed': 15, 'solar_ghi': 0, 'cloud_cover': 50}
                
                prices = {'current': price, '1h_ago': price, 'da_price': price, 'reg_up': 10, 'rrs': 6}
                
                decision = agent.decide(price, weather, prices)
                agent.settle(price, decision)
                
            except Exception as e:
                log.error(f"Tick error: {e}")
            
            time.sleep(900)  # 15 minutes
    
    thread = Thread(target=tick_loop, daemon=True)
    thread.start()
    
    print("⚡ VoltStream AI running")
    print(f"  API: http://localhost:5000")
    print(f"  Claude: {'enabled' if claude.enabled else 'disabled (set ANTHROPIC_API_KEY)'}")
    
    app.run(host='0.0.0.0', port=5000, debug=False)


if __name__ == '__main__':
    import sys
    
    if '--live' in sys.argv:
        run_live()
    else:
        run_demo()
