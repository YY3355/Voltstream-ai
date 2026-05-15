"""
VoltStream AI — Multi-Agent Dispatch System
=============================================
Six autonomous agents that work together as a virtual trading desk.

Architecture:
                    ┌─────────────┐
                    │ Alert Agent  │ ← monitors all agents
                    └──────┬──────┘
                           │
    ┌──────────┐    ┌──────┴──────┐    ┌──────────────┐
    │ Weather  │───→│   Price     │───→│  Dispatch     │
    │  Agent   │    │  Forecast   │    │   Agent       │
    └──────────┘    │   Agent     │    └──────┬───────┘
                    └─────────────┘           │
                           ↑          ┌──────┴───────┐
                           │          │ Market Bid    │
                    ┌──────┴──────┐   │   Agent       │
                    │ Settlement  │   └──────────────┘
                    │   Agent     │
                    └─────────────┘
                    (feedback loop)

Each agent:
- Has a single responsibility
- Communicates via a shared message bus
- Logs every decision for auditability
- Can escalate to human operator
- Learns from outcomes over time
"""

import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from enum import Enum
import numpy as np


# ==================================================================
# SHARED MESSAGE BUS
# ==================================================================

class Priority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AgentMessage:
    """Message passed between agents via the bus."""
    source: str
    target: str  # agent name or "all"
    msg_type: str  # "data", "alert", "escalation", "feedback"
    payload: dict
    priority: str = "medium"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self):
        return asdict(self)


class MessageBus:
    """Central communication hub for all agents."""
    
    def __init__(self):
        self.messages: List[AgentMessage] = []
        self.subscribers: Dict[str, list] = {}
        self.log: List[dict] = []
    
    def publish(self, message: AgentMessage):
        """Publish a message to the bus."""
        self.messages.append(message)
        self.log.append(message.to_dict())
        
        # Notify subscribers
        target = message.target
        if target == "all":
            for name, callbacks in self.subscribers.items():
                for cb in callbacks:
                    cb(message)
        elif target in self.subscribers:
            for cb in self.subscribers[target]:
                cb(message)
    
    def subscribe(self, agent_name: str, callback):
        """Subscribe an agent to receive messages."""
        if agent_name not in self.subscribers:
            self.subscribers[agent_name] = []
        self.subscribers[agent_name].append(callback)
    
    def get_latest(self, source: str = None, msg_type: str = None, n: int = 1):
        """Get latest messages, optionally filtered."""
        filtered = self.messages
        if source:
            filtered = [m for m in filtered if m.source == source]
        if msg_type:
            filtered = [m for m in filtered if m.msg_type == msg_type]
        return filtered[-n:] if filtered else []


# ==================================================================
# AGENT BASE CLASS
# ==================================================================

class BaseAgent:
    """Base class for all VoltStream agents."""
    
    def __init__(self, name: str, bus: MessageBus):
        self.name = name
        self.bus = bus
        self.bus.subscribe(name, self.on_message)
        self.state = {}
        self.decision_log = []
        self.is_running = False
    
    def on_message(self, message: AgentMessage):
        """Handle incoming message. Override in subclass."""
        pass
    
    def emit(self, target: str, msg_type: str, payload: dict, priority: str = "medium"):
        """Send a message to another agent or all agents."""
        msg = AgentMessage(
            source=self.name,
            target=target,
            msg_type=msg_type,
            payload=payload,
            priority=priority,
        )
        self.bus.publish(msg)
    
    def log_decision(self, decision: dict):
        """Log a decision for auditability."""
        entry = {
            'agent': self.name,
            'timestamp': datetime.now().isoformat(),
            **decision,
        }
        self.decision_log.append(entry)
        return entry
    
    def escalate(self, reason: str, context: dict):
        """Escalate to human operator."""
        self.emit("alert_agent", "escalation", {
            'reason': reason,
            'context': context,
            'agent': self.name,
        }, priority="high")


# ==================================================================
# WEATHER AGENT
# ==================================================================

class WeatherAgent(BaseAgent):
    """
    Monitors weather across all ERCOT regions.
    Detects events that will impact energy supply/demand.
    Feeds weather signals to Price Forecast Agent.
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("weather_agent", bus)
        self.regions = {
            'houston': {'lat': 29.76, 'lon': -95.37},
            'dallas': {'lat': 32.78, 'lon': -96.80},
            'west_tx_wind': {'lat': 32.00, 'lon': -101.00},
            'panhandle_wind': {'lat': 35.50, 'lon': -101.50},
            'west_tx_solar': {'lat': 31.50, 'lon': -103.00},
        }
        self.alert_thresholds = {
            'extreme_heat': 100,  # °F
            'high_heat': 95,
            'freeze_warning': 32,
            'wind_ramp_up': 10,  # mph change in 3 hours
            'wind_ramp_down': -10,
            'solar_cliff': -300,  # W/m² change in 1 hour (cloud transient)
        }
    
    def analyze(self, weather_data: dict) -> dict:
        """
        Analyze weather data and generate signals.
        
        Args:
            weather_data: Dict with temperature, wind, solar for each region
        
        Returns:
            signals: Dict of weather-derived signals for price forecasting
        """
        signals = {
            'timestamp': datetime.now().isoformat(),
            'demand_signals': {},
            'supply_signals': {},
            'events': [],
        }
        
        # DEMAND SIGNALS (temperature-driven)
        for region in ['houston', 'dallas']:
            temp = weather_data.get(f'{region}_temperature', 75)
            cdh = max(0, temp - 75)
            hdh = max(0, 40 - temp)
            
            signals['demand_signals'][region] = {
                'temperature': temp,
                'cooling_degree_hours': cdh,
                'heating_degree_hours': hdh,
                'demand_impact': 'high' if cdh > 15 else 'medium' if cdh > 5 else 'low',
            }
            
            # Event detection
            if temp >= self.alert_thresholds['extreme_heat']:
                signals['events'].append({
                    'type': 'extreme_heat',
                    'region': region,
                    'value': temp,
                    'impact': 'Price spike likely — extreme cooling demand',
                    'action': 'Pre-position battery for discharge',
                })
            elif temp <= self.alert_thresholds['freeze_warning']:
                signals['events'].append({
                    'type': 'freeze_warning',
                    'region': region,
                    'value': temp,
                    'impact': 'Potential heating demand surge + generator risk',
                    'action': 'Hold charge for emergency discharge',
                })
        
        # SUPPLY SIGNALS (wind)
        for region in ['west_tx_wind', 'panhandle_wind']:
            wind = weather_data.get(f'{region}_wind_100m', 15)
            wind_ramp = weather_data.get(f'{region}_wind_ramp_3h', 0)
            
            # Wind power proxy (simplified power curve)
            if wind < 7:
                wind_power = 0
            elif wind < 28:
                wind_power = (wind / 28) ** 3
            elif wind < 55:
                wind_power = 1.0
            else:
                wind_power = 0  # cut-out
            
            signals['supply_signals'][region] = {
                'wind_speed_100m': wind,
                'wind_power_factor': round(wind_power, 3),
                'wind_ramp_3h': wind_ramp,
                'supply_impact': 'high' if wind_power > 0.7 else 'medium' if wind_power > 0.3 else 'low',
            }
            
            # Wind ramp events
            if wind_ramp > self.alert_thresholds['wind_ramp_up']:
                signals['events'].append({
                    'type': 'wind_ramp_up',
                    'region': region,
                    'value': wind_ramp,
                    'impact': 'Wind generation surge — prices likely to drop',
                    'action': 'Prepare to charge',
                })
            elif wind_ramp < self.alert_thresholds['wind_ramp_down']:
                signals['events'].append({
                    'type': 'wind_ramp_down',
                    'region': region,
                    'value': wind_ramp,
                    'impact': 'Wind generation falling — prices likely to rise',
                    'action': 'Prepare to discharge',
                })
        
        # SUPPLY SIGNALS (solar)
        solar_ghi = weather_data.get('solar_ghi', 0)
        cloud_cover = weather_data.get('cloud_cover', 50)
        solar_ramp = weather_data.get('solar_ramp_1h', 0)
        
        signals['supply_signals']['solar'] = {
            'ghi': solar_ghi,
            'cloud_cover': cloud_cover,
            'solar_ramp_1h': solar_ramp,
            'supply_impact': 'high' if solar_ghi > 700 else 'medium' if solar_ghi > 300 else 'low',
        }
        
        if solar_ramp < self.alert_thresholds['solar_cliff']:
            signals['events'].append({
                'type': 'solar_cliff',
                'value': solar_ramp,
                'impact': 'Sudden cloud cover — solar generation dropping fast',
                'action': 'Prices may spike — consider holding charge',
            })
        
        # NET LOAD SIGNAL
        total_demand = sum(
            s.get('cooling_degree_hours', 0) * 800
            for s in signals['demand_signals'].values()
        ) + 45000  # base load
        
        total_wind = sum(
            s.get('wind_power_factor', 0) * 15000  # ~15 GW per major region
            for s in signals['supply_signals'].values()
            if 'wind_power_factor' in s
        )
        
        total_solar = solar_ghi / 1000 * 22000  # ~22 GW installed
        
        net_load = total_demand - total_wind - total_solar
        signals['net_load_mw'] = round(net_load, 0)
        signals['net_load_signal'] = (
            'very_high' if net_load > 55000 else
            'high' if net_load > 45000 else
            'normal' if net_load > 30000 else
            'low' if net_load > 15000 else
            'very_low'
        )
        
        # Log and publish
        self.log_decision({
            'action': 'weather_analysis',
            'net_load': net_load,
            'events_detected': len(signals['events']),
            'net_load_signal': signals['net_load_signal'],
        })
        
        self.emit("price_forecast_agent", "data", signals)
        
        # Escalate if critical events
        critical_events = [e for e in signals['events'] if e['type'] in ['extreme_heat', 'freeze_warning']]
        if critical_events:
            self.escalate(
                f"Critical weather event: {critical_events[0]['type']}",
                {'events': critical_events}
            )
        
        return signals


# ==================================================================
# PRICE FORECAST AGENT
# ==================================================================

class PriceForecastAgent(BaseAgent):
    """
    Generates rolling price forecasts using weather + market data.
    Runs every 5 minutes (aligned with ERCOT SCED intervals).
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("price_forecast_agent", bus)
        self.latest_weather = None
        self.latest_prices = []
        self.forecast_history = []
        self.model = None  # XGBoost model loaded here in production
    
    def on_message(self, message: AgentMessage):
        """Receive weather signals from Weather Agent."""
        if message.source == "weather_agent" and message.msg_type == "data":
            self.latest_weather = message.payload
        elif message.source == "settlement_agent" and message.msg_type == "feedback":
            # Settlement agent tells us where our forecasts were wrong
            self.incorporate_feedback(message.payload)
    
    def incorporate_feedback(self, feedback: dict):
        """
        Learn from settlement feedback.
        This is the self-improving loop — the key moat.
        """
        forecast_error = feedback.get('forecast_error', 0)
        error_pattern = feedback.get('error_pattern', '')
        
        self.log_decision({
            'action': 'incorporate_feedback',
            'forecast_error': forecast_error,
            'error_pattern': error_pattern,
            'adjustment': 'Model bias correction applied',
        })
        
        # In production: retrain model with new data,
        # apply bias correction, adjust confidence intervals
    
    def generate_forecast(self, current_price: float, market_data: dict = None) -> dict:
        """
        Generate price forecasts for next 1h, 4h, 24h, 48h.
        
        In production this runs the XGBoost/LSTM model.
        Here we demonstrate the agent logic and output format.
        """
        weather = self.latest_weather or {}
        net_load_signal = weather.get('net_load_signal', 'normal')
        net_load = weather.get('net_load_mw', 40000)
        events = weather.get('events', [])
        
        # Price forecast logic (simplified — real version uses ML model)
        base_forecast = current_price
        
        # Weather-driven adjustment
        if net_load_signal == 'very_high':
            adjustment = 30 + np.random.normal(0, 10)
        elif net_load_signal == 'high':
            adjustment = 10 + np.random.normal(0, 5)
        elif net_load_signal == 'low':
            adjustment = -15 + np.random.normal(0, 5)
        elif net_load_signal == 'very_low':
            adjustment = -25 + np.random.normal(0, 8)
        else:
            adjustment = np.random.normal(0, 5)
        
        # Event-driven spikes
        event_adjustment = 0
        for event in events:
            if event['type'] == 'extreme_heat':
                event_adjustment += 50
            elif event['type'] == 'wind_ramp_down':
                event_adjustment += 15
            elif event['type'] == 'wind_ramp_up':
                event_adjustment -= 20
            elif event['type'] == 'solar_cliff':
                event_adjustment += 25
        
        forecast = {
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'forecasts': {
                '1h': {
                    'price': max(-10, base_forecast + adjustment * 0.5 + event_adjustment),
                    'confidence': 0.85 + np.random.uniform(-0.1, 0.05),
                    'range_low': max(-20, base_forecast + adjustment * 0.5 - 15),
                    'range_high': base_forecast + adjustment * 0.5 + event_adjustment + 20,
                },
                '4h': {
                    'price': max(-10, base_forecast + adjustment + event_adjustment * 0.5),
                    'confidence': 0.72 + np.random.uniform(-0.1, 0.05),
                    'range_low': max(-30, base_forecast + adjustment - 25),
                    'range_high': base_forecast + adjustment + event_adjustment + 40,
                },
                '24h': {
                    'price': max(-10, base_forecast + adjustment * 1.5),
                    'confidence': 0.55 + np.random.uniform(-0.1, 0.05),
                    'range_low': max(-40, base_forecast - 30),
                    'range_high': base_forecast + adjustment * 2 + 50,
                },
            },
            'drivers': {
                'net_load_signal': net_load_signal,
                'net_load_mw': net_load,
                'weather_events': len(events),
                'primary_driver': (
                    'weather_event' if events else
                    'high_demand' if net_load_signal in ['high', 'very_high'] else
                    'renewable_oversupply' if net_load_signal in ['low', 'very_low'] else
                    'market_momentum'
                ),
            },
        }
        
        self.forecast_history.append(forecast)
        
        self.log_decision({
            'action': 'price_forecast',
            'current': current_price,
            'forecast_1h': forecast['forecasts']['1h']['price'],
            'confidence_1h': forecast['forecasts']['1h']['confidence'],
            'primary_driver': forecast['drivers']['primary_driver'],
        })
        
        # Send to dispatch agent
        self.emit("dispatch_agent", "data", forecast)
        
        # Escalate if forecast shows extreme prices
        if forecast['forecasts']['1h']['price'] > 200:
            self.escalate(
                f"Extreme price forecast: ${forecast['forecasts']['1h']['price']:.0f}/MWh in 1h",
                forecast
            )
        
        return forecast


# ==================================================================
# DISPATCH AGENT
# ==================================================================

class DispatchAgent(BaseAgent):
    """
    Makes charge/discharge decisions based on price forecasts.
    Co-optimizes across energy arbitrage and ancillary services.
    Manages SOC and battery degradation.
    """
    
    def __init__(self, bus: MessageBus, battery_config: dict = None):
        super().__init__("dispatch_agent", bus)
        
        self.battery = battery_config or {
            'power_mw': 100,
            'capacity_mwh': 400,
            'soc': 0.50,
            'min_soc': 0.05,
            'max_soc': 0.95,
            'rte': 0.87,
            'degradation_per_cycle': 0.00002,
            'total_cycles': 0,
        }
        self.latest_forecast = None
        self.dispatch_history = []
    
    def on_message(self, message: AgentMessage):
        if message.source == "price_forecast_agent" and message.msg_type == "data":
            self.latest_forecast = message.payload
    
    def decide(self, current_price: float, as_prices: dict = None) -> dict:
        """
        Make a dispatch decision.
        
        Returns a decision with:
        - action: CHARGE, DISCHARGE, HOLD
        - power_mw: how much
        - reason: explainable logic
        - market: which market to participate in
        """
        forecast = self.latest_forecast
        soc = self.battery['soc']
        power = self.battery['power_mw']
        capacity = self.battery['capacity_mwh']
        eff = np.sqrt(self.battery['rte'])
        
        as_prices = as_prices or {'reg_up': 10, 'rrs': 6, 'drrs': 15}
        
        # Get forecast prices
        price_1h = forecast['forecasts']['1h']['price'] if forecast else current_price
        price_4h = forecast['forecasts']['4h']['price'] if forecast else current_price
        confidence = forecast['forecasts']['1h']['confidence'] if forecast else 0.5
        
        # Calculate expected values for each action
        spread_1h = price_1h - current_price
        spread_4h = price_4h - current_price
        
        # Expected revenue from energy arbitrage
        discharge_value = current_price * power  # $/h from discharging now
        charge_cost = current_price * power  # $/h cost of charging now
        future_discharge_value = price_1h * power  # $/h from discharging in 1h
        
        # Expected revenue from ancillary services
        reg_up_value = as_prices['reg_up'] * power * 0.5  # only commit 50% to AS
        rrs_value = as_prices['rrs'] * power * 0.5
        
        # Decision logic
        decision = {
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'forecast_1h': price_1h,
            'forecast_4h': price_4h,
            'confidence': confidence,
            'soc_before': soc,
            'action': 'HOLD',
            'power_mw': 0,
            'market': 'none',
            'reason': '',
            'expected_revenue': 0,
        }
        
        # RULE 1: Negative prices — always charge aggressively
        if current_price < 0:
            max_charge = min(power, (self.battery['max_soc'] - soc) * capacity / eff)
            decision.update({
                'action': 'CHARGE',
                'power_mw': round(max_charge, 1),
                'market': 'rt_energy',
                'reason': f'Negative price (${current_price:.2f}/MWh) — being paid to charge',
                'expected_revenue': abs(current_price) * max_charge,
            })
        
        # RULE 2: Extreme price spike — discharge everything
        elif current_price > 200 and soc > 0.15:
            max_discharge = min(power, (soc - self.battery['min_soc']) * capacity * eff)
            decision.update({
                'action': 'DISCHARGE',
                'power_mw': round(max_discharge, 1),
                'market': 'rt_energy',
                'reason': f'Price spike (${current_price:.2f}/MWh) — maximum discharge',
                'expected_revenue': current_price * max_discharge,
            })
        
        # RULE 3: Price low + forecast says prices rising — charge
        elif current_price < 15 and spread_1h > 10 and soc < 0.85:
            intensity = min(1.0, spread_1h / 30) * confidence
            charge_mw = round(power * intensity, 1)
            max_charge = min(charge_mw, (self.battery['max_soc'] - soc) * capacity / eff)
            decision.update({
                'action': 'CHARGE',
                'power_mw': round(max_charge, 1),
                'market': 'rt_energy',
                'reason': f'Low price (${current_price:.2f}) + forecast rise to ${price_1h:.2f} in 1h ({confidence*100:.0f}% conf)',
                'expected_revenue': -current_price * max_charge,  # cost of charging (negative = saving)
            })
        
        # RULE 4: Price high + forecast says prices falling — discharge
        elif current_price > 40 and spread_1h < -5 and soc > 0.20:
            intensity = min(1.0, (current_price - 40) / 30) * confidence
            discharge_mw = round(power * intensity, 1)
            max_discharge = min(discharge_mw, (soc - self.battery['min_soc']) * capacity * eff)
            decision.update({
                'action': 'DISCHARGE',
                'power_mw': round(max_discharge, 1),
                'market': 'rt_energy',
                'reason': f'High price (${current_price:.2f}) + forecast drop to ${price_1h:.2f} in 1h ({confidence*100:.0f}% conf)',
                'expected_revenue': current_price * max_discharge,
            })
        
        # RULE 5: Ancillary services more valuable than arbitrage
        elif as_prices['reg_up'] > 15 and soc > 0.30 and abs(spread_1h) < 10:
            decision.update({
                'action': 'HOLD',
                'power_mw': round(power * 0.5, 1),
                'market': 'reg_up',
                'reason': f'Reg Up (${as_prices["reg_up"]:.2f}/MW) more valuable than arbitrage (spread: ${spread_1h:.2f})',
                'expected_revenue': reg_up_value,
            })
        
        # RULE 6: SOC management
        elif soc > 0.90 and current_price > 20:
            decision.update({
                'action': 'DISCHARGE',
                'power_mw': round(power * 0.3, 1),
                'market': 'rt_energy',
                'reason': f'SOC high ({soc*100:.0f}%) — shedding to maintain flexibility',
                'expected_revenue': current_price * power * 0.3,
            })
        elif soc < 0.15 and current_price < 30:
            decision.update({
                'action': 'CHARGE',
                'power_mw': round(power * 0.3, 1),
                'market': 'rt_energy',
                'reason': f'SOC low ({soc*100:.0f}%) — building reserve at reasonable price',
                'expected_revenue': 0,
            })
        
        # DEFAULT: Hold
        else:
            decision.update({
                'reason': f'No clear signal — price ${current_price:.2f}, forecast ${price_1h:.2f}, SOC {soc*100:.0f}%',
            })
        
        # Update SOC
        if decision['action'] == 'CHARGE':
            energy_added = decision['power_mw'] * eff / capacity
            self.battery['soc'] = min(self.battery['max_soc'], soc + energy_added)
        elif decision['action'] == 'DISCHARGE':
            energy_removed = decision['power_mw'] / eff / capacity
            self.battery['soc'] = max(self.battery['min_soc'], soc - energy_removed)
        
        decision['soc_after'] = self.battery['soc']
        
        # Log
        self.log_decision(decision)
        self.dispatch_history.append(decision)
        
        # Send to market bidding agent
        self.emit("market_bid_agent", "data", decision)
        
        # Send to all for monitoring
        self.emit("all", "data", {
            'type': 'dispatch_decision',
            **decision,
        })
        
        return decision


# ==================================================================
# MARKET BIDDING AGENT
# ==================================================================

class MarketBidAgent(BaseAgent):
    """
    Translates dispatch decisions into ERCOT market bids.
    Formats DAM, RTM, and AS offers per ERCOT specs.
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("market_bid_agent", bus)
        self.pending_bids = []
        self.submitted_bids = []
    
    def on_message(self, message: AgentMessage):
        if message.source == "dispatch_agent" and message.msg_type == "data":
            self.format_bid(message.payload)
    
    def format_bid(self, dispatch: dict) -> dict:
        """
        Format a dispatch decision into an ERCOT market bid.
        
        In production: submits to QSE's bid submission system
        via API integration.
        """
        action = dispatch.get('action', 'HOLD')
        power = dispatch.get('power_mw', 0)
        market = dispatch.get('market', 'none')
        
        if action == 'HOLD' and market == 'none':
            return None
        
        bid = {
            'timestamp': datetime.now().isoformat(),
            'market': market,
            'resource_type': 'ESR',  # Energy Storage Resource
            'settlement_point': 'HB_HOUSTON',
            'status': 'formatted',
        }
        
        if market == 'rt_energy':
            if action == 'DISCHARGE':
                bid.update({
                    'bid_type': 'energy_offer',
                    'direction': 'generation',
                    'mw': power,
                    'price': dispatch.get('current_price', 0) * 0.95,  # bid slightly below current
                    'ercot_format': {
                        'QSE': 'VOLTSTREAM_QSE',
                        'Resource': 'VS_BESS_001',
                        'HE': datetime.now().hour + 1,
                        'MW': power,
                        'Price': round(dispatch.get('current_price', 0) * 0.95, 2),
                        'CurveType': 'OFFER',
                    }
                })
            elif action == 'CHARGE':
                bid.update({
                    'bid_type': 'energy_bid',
                    'direction': 'load',
                    'mw': power,
                    'price': dispatch.get('current_price', 0) * 1.05,  # bid slightly above current
                    'ercot_format': {
                        'QSE': 'VOLTSTREAM_QSE',
                        'Resource': 'VS_BESS_001',
                        'HE': datetime.now().hour + 1,
                        'MW': power,
                        'Price': round(dispatch.get('current_price', 0) * 1.05, 2),
                        'CurveType': 'BID',
                    }
                })
        
        elif market == 'reg_up':
            bid.update({
                'bid_type': 'as_offer',
                'as_type': 'Reg-Up',
                'mw': power,
                'price': dispatch.get('current_price', 10) * 0.8,
            })
        
        self.pending_bids.append(bid)
        
        self.log_decision({
            'action': 'bid_formatted',
            'market': market,
            'direction': bid.get('direction', 'none'),
            'mw': power,
            'price': bid.get('price', 0),
        })
        
        return bid


# ==================================================================
# SETTLEMENT AGENT
# ==================================================================

class SettlementAgent(BaseAgent):
    """
    Reconciles actual performance against forecasts.
    Identifies where models were wrong and feeds back.
    Generates revenue attribution reports.
    THIS IS THE LEARNING LOOP.
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("settlement_agent", bus)
        self.settlements = []
        self.cumulative_revenue = 0
        self.forecast_errors = []
    
    def reconcile(self, actual_price: float, forecasted_price: float,
                  action_taken: str, mw: float, interval_hours: float = 0.25):
        """
        Compare actual vs forecasted price for a settled interval.
        Calculate actual revenue and forecast error.
        Feed error back to Price Forecast Agent.
        """
        # Actual revenue
        if action_taken == 'DISCHARGE':
            revenue = actual_price * mw * interval_hours
        elif action_taken == 'CHARGE':
            revenue = -actual_price * mw * interval_hours
        else:
            revenue = 0
        
        # Forecast error
        error = actual_price - forecasted_price
        error_pct = abs(error / actual_price) * 100 if actual_price != 0 else 0
        
        # Determine error pattern
        if error > 20:
            pattern = 'underforecast_spike'
        elif error < -20:
            pattern = 'overforecast_drop'
        elif abs(error) < 5:
            pattern = 'accurate'
        else:
            pattern = 'moderate_error'
        
        settlement = {
            'timestamp': datetime.now().isoformat(),
            'actual_price': actual_price,
            'forecasted_price': forecasted_price,
            'error': round(error, 2),
            'error_pct': round(error_pct, 1),
            'error_pattern': pattern,
            'action': action_taken,
            'mw': mw,
            'revenue': round(revenue, 2),
            'interval_hours': interval_hours,
        }
        
        self.settlements.append(settlement)
        self.cumulative_revenue += revenue
        self.forecast_errors.append(error)
        
        # Log
        self.log_decision({
            'action': 'settlement_reconciliation',
            'revenue': revenue,
            'cumulative': self.cumulative_revenue,
            'forecast_error': error,
            'pattern': pattern,
        })
        
        # FEEDBACK LOOP: Send error analysis back to Price Forecast Agent
        if len(self.forecast_errors) >= 10:
            recent_errors = self.forecast_errors[-10:]
            mae = np.mean(np.abs(recent_errors))
            bias = np.mean(recent_errors)
            
            self.emit("price_forecast_agent", "feedback", {
                'forecast_error': mae,
                'forecast_bias': bias,
                'error_pattern': pattern,
                'recent_errors': recent_errors,
                'recommendation': (
                    'Model overforecasting — reduce upward bias'
                    if bias > 5 else
                    'Model underforecasting — increase baseline'
                    if bias < -5 else
                    'Model performing within tolerance'
                ),
            })
        
        return settlement
    
    def revenue_report(self) -> dict:
        """Generate revenue attribution report."""
        if not self.settlements:
            return {'total': 0, 'intervals': 0}
        
        discharge_rev = sum(s['revenue'] for s in self.settlements if s['action'] == 'DISCHARGE')
        charge_cost = sum(s['revenue'] for s in self.settlements if s['action'] == 'CHARGE')
        
        mae = np.mean(np.abs(self.forecast_errors)) if self.forecast_errors else 0
        
        return {
            'total_revenue': round(self.cumulative_revenue, 2),
            'discharge_revenue': round(discharge_rev, 2),
            'charge_cost': round(charge_cost, 2),
            'net_revenue': round(discharge_rev + charge_cost, 2),
            'intervals_settled': len(self.settlements),
            'avg_forecast_error': round(mae, 2),
            'forecast_bias': round(np.mean(self.forecast_errors), 2) if self.forecast_errors else 0,
        }


# ==================================================================
# ALERT AGENT
# ==================================================================

class AlertAgent(BaseAgent):
    """
    Monitors all agents and escalates to human operators.
    The 5% that needs human judgment.
    """
    
    def __init__(self, bus: MessageBus):
        super().__init__("alert_agent", bus)
        self.active_alerts = []
        self.alert_history = []
    
    def on_message(self, message: AgentMessage):
        if message.msg_type == "escalation":
            self.handle_escalation(message)
        elif message.msg_type == "data" and message.payload.get('type') == 'dispatch_decision':
            self.monitor_dispatch(message.payload)
    
    def handle_escalation(self, message: AgentMessage):
        """Process an escalation from any agent."""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'source_agent': message.source,
            'reason': message.payload.get('reason', 'Unknown'),
            'context': message.payload.get('context', {}),
            'priority': message.priority,
            'status': 'active',
            'requires_human': True,
        }
        
        self.active_alerts.append(alert)
        self.alert_history.append(alert)
        
        self.log_decision({
            'action': 'alert_raised',
            'source': message.source,
            'reason': alert['reason'],
            'priority': message.priority,
        })
        
        # In production: send notification to operator
        # via SMS, email, Slack, or dashboard push notification
        print(f"\n{'!'*60}")
        print(f"  ALERT [{message.priority.upper()}] from {message.source}")
        print(f"  {alert['reason']}")
        print(f"{'!'*60}\n")
    
    def monitor_dispatch(self, dispatch: dict):
        """Monitor dispatch decisions for anomalies."""
        # Alert if making large trades with low confidence
        if dispatch.get('power_mw', 0) > 80 and dispatch.get('confidence', 1) < 0.6:
            self.handle_escalation(AgentMessage(
                source="alert_agent",
                target="alert_agent",
                msg_type="escalation",
                payload={
                    'reason': f"Large trade ({dispatch['power_mw']}MW) with low confidence ({dispatch['confidence']*100:.0f}%)",
                    'context': dispatch,
                },
                priority="high",
            ))


# ==================================================================
# ORCHESTRATOR — Runs all agents together
# ==================================================================

class VoltStreamOrchestrator:
    """
    Coordinates all agents into a unified system.
    This is the main entry point for the VoltStream service.
    """
    
    def __init__(self, battery_config: dict = None):
        self.bus = MessageBus()
        
        # Initialize all agents
        self.weather = WeatherAgent(self.bus)
        self.forecast = PriceForecastAgent(self.bus)
        self.dispatch = DispatchAgent(self.bus, battery_config)
        self.bidding = MarketBidAgent(self.bus)
        self.settlement = SettlementAgent(self.bus)
        self.alerts = AlertAgent(self.bus)
        
        self.tick_count = 0
    
    def tick(self, weather_data: dict, current_price: float, as_prices: dict = None):
        """
        Run one cycle of all agents.
        In production: runs every 5 minutes aligned with ERCOT SCED.
        """
        self.tick_count += 1
        
        # 1. Weather Agent analyzes conditions
        weather_signals = self.weather.analyze(weather_data)
        
        # 2. Price Forecast Agent generates forecast
        forecast = self.forecast.generate_forecast(current_price)
        
        # 3. Dispatch Agent makes decision
        decision = self.dispatch.decide(current_price, as_prices)
        
        # 4. Market Bid Agent formats bid
        # (happens automatically via message bus)
        
        return {
            'tick': self.tick_count,
            'weather_signals': weather_signals,
            'forecast': forecast,
            'decision': decision,
        }
    
    def settle(self, actual_price: float, forecasted_price: float,
               action: str, mw: float):
        """Settle an interval after the fact."""
        return self.settlement.reconcile(
            actual_price, forecasted_price, action, mw
        )
    
    def status(self) -> dict:
        """Get full system status."""
        return {
            'ticks': self.tick_count,
            'battery_soc': self.dispatch.battery['soc'],
            'active_alerts': len(self.alerts.active_alerts),
            'revenue': self.settlement.revenue_report(),
            'message_bus_size': len(self.bus.log),
            'agents': {
                'weather': len(self.weather.decision_log),
                'forecast': len(self.forecast.decision_log),
                'dispatch': len(self.dispatch.decision_log),
                'bidding': len(self.bidding.decision_log),
                'settlement': len(self.settlement.decision_log),
                'alerts': len(self.alerts.decision_log),
            }
        }


# ==================================================================
# DEMO
# ==================================================================

def demo():
    """Run a demo of the full multi-agent system."""
    
    print("=" * 70)
    print("VOLTSTREAM AI — MULTI-AGENT SYSTEM DEMO")
    print("=" * 70)
    print("\n6 agents working together as a virtual trading desk\n")
    
    # Initialize orchestrator
    vs = VoltStreamOrchestrator({
        'power_mw': 100,
        'capacity_mwh': 400,
        'soc': 0.50,
        'min_soc': 0.05,
        'max_soc': 0.95,
        'rte': 0.87,
        'degradation_per_cycle': 0.00002,
        'total_cycles': 0,
    })
    
    # Simulate 24 hours of operation
    print("Simulating 24 hours of autonomous operation...\n")
    
    for hour in range(24):
        # Simulated weather
        temp = 72 + 15 * np.sin((hour - 6) / 24 * 2 * np.pi) + np.random.normal(0, 2)
        wind = max(0, 15 + 8 * np.sin((hour - 3) / 24 * 2 * np.pi) + np.random.normal(0, 4))
        solar = max(0, np.sin((hour - 6) / 13 * np.pi) * 900) if 6 < hour < 19 else 0
        
        weather = {
            'houston_temperature': temp,
            'dallas_temperature': temp - 3,
            'west_tx_wind_wind_100m': wind,
            'panhandle_wind_wind_100m': wind * 1.2,
            'west_tx_wind_wind_ramp_3h': np.random.normal(0, 5),
            'panhandle_wind_wind_ramp_3h': np.random.normal(0, 5),
            'solar_ghi': solar,
            'cloud_cover': max(0, min(100, 30 + np.random.normal(0, 20))),
            'solar_ramp_1h': np.random.normal(0, 50),
        }
        
        # Simulated price (correlated with net load)
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
        
        as_prices = {'reg_up': 8 + np.random.uniform(0, 10), 'rrs': 5 + np.random.uniform(0, 6), 'drrs': 12}
        
        # Run one tick
        result = vs.tick(weather, price, as_prices)
        decision = result['decision']
        
        # Settle the interval
        actual_price = price + np.random.normal(0, 3)  # actual differs slightly
        vs.settle(actual_price, price, decision['action'], decision['power_mw'])
        
        # Print
        action_color = {'CHARGE': '🟢', 'DISCHARGE': '🟡', 'HOLD': '⚪'}
        print(f"  {hour:02d}:00  ${price:6.1f}/MWh  {action_color.get(decision['action'], '⚪')} {decision['action']:10s} {decision['power_mw']:5.0f}MW  SOC:{decision['soc_after']*100:4.0f}%  │ {decision['reason'][:60]}")
    
    # Final report
    status = vs.status()
    revenue = status['revenue']
    
    print(f"\n{'='*70}")
    print("24-HOUR PERFORMANCE REPORT")
    print(f"{'='*70}")
    print(f"  Total Revenue:      ${revenue['total_revenue']:>10,.2f}")
    print(f"  Discharge Revenue:  ${revenue['discharge_revenue']:>10,.2f}")
    print(f"  Charge Cost:        ${revenue['charge_cost']:>10,.2f}")
    print(f"  Net Revenue:        ${revenue['net_revenue']:>10,.2f}")
    print(f"  Intervals Settled:  {revenue['intervals_settled']}")
    print(f"  Avg Forecast Error: ${revenue['avg_forecast_error']:.2f}/MWh")
    print(f"  Forecast Bias:      ${revenue['forecast_bias']:.2f}/MWh")
    print(f"  Active Alerts:      {status['active_alerts']}")
    print(f"  Battery SOC:        {status['battery_soc']*100:.0f}%")
    
    print(f"\n  Agent Activity:")
    for agent, count in status['agents'].items():
        print(f"    {agent:<15} {count} decisions logged")
    
    print(f"\n  Total messages on bus: {status['message_bus_size']}")
    
    print(f"\n{'='*70}")
    print("THIS IS VOLTSTREAM'S MOAT:")
    print(f"{'='*70}")
    print(f"""
  Every 5 minutes, 6 agents coordinate:
  1. Weather Agent sees conditions across all of Texas
  2. Price Forecast Agent predicts where prices are heading
  3. Dispatch Agent decides charge/discharge/hold with reasoning
  4. Market Bid Agent formats ERCOT-compliant bids
  5. Settlement Agent reconciles and finds forecast errors
  6. Alert Agent escalates the 5% that needs human judgment
  
  The Settlement Agent feeds errors back to the Price Forecast
  Agent, which improves predictions, which improves dispatch,
  which generates more revenue, which generates more data.
  
  This loop gets better every day. After 6 months on an asset,
  no competitor can match your model without 6 months of the
  same data. THAT is the moat.
""")


if __name__ == '__main__':
    demo()
