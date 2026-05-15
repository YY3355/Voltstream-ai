"""
VoltStream AI — Multi-Provider Weather Intelligence
=====================================================
Instead of one weather source, pull from multiple forecast models
simultaneously. When weather models disagree about tomorrow's
wind in West Texas, that uncertainty flows directly into price
forecast confidence.

PROVIDERS (all free via Open-Meteo):
1. GFS — NOAA's Global Forecast System (US primary model)
2. HRRR — High-Resolution Rapid Refresh (best for Texas short-term)
3. ECMWF — European model (often most accurate globally)
4. ICON — German weather service model
5. GEM — Canadian model (good for cold fronts from the north)

Each model has different strengths:
- HRRR: best 0-18 hour wind/solar for Texas
- ECMWF: best 2-7 day temperature forecasts
- GFS: good all-around, updates every 6 hours
- ICON: good for convective storms
- GEM: good for arctic front timing

When models disagree on wind speed by >5 mph, that's a signal
that renewable generation is uncertain → price forecast confidence
should drop → dispatch agent should be more conservative.
"""

import requests
import numpy as np
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional


# Open-Meteo provides access to multiple weather models
# through different API endpoints — all free, no key needed

WEATHER_MODELS = {
    'gfs': {
        'name': 'GFS (NOAA)',
        'url': 'https://api.open-meteo.com/v1/gfs',
        'update_freq': '6h',
        'best_for': 'General US forecasting',
        'horizon': '16 days',
    },
    'hrrr': {
        'name': 'HRRR (NOAA)',
        'url': 'https://api.open-meteo.com/v1/forecast',  # HRRR via main endpoint
        'update_freq': '1h',
        'best_for': 'Short-term Texas wind/solar (0-18h)',
        'horizon': '48 hours',
    },
    'ecmwf': {
        'name': 'ECMWF (European)',
        'url': 'https://api.open-meteo.com/v1/ecmwf',
        'update_freq': '6h',
        'best_for': 'Medium-range temperature (2-7 days)',
        'horizon': '10 days',
    },
    'icon': {
        'name': 'ICON (German DWD)',
        'url': 'https://api.open-meteo.com/v1/dwd-icon',
        'update_freq': '6h',
        'best_for': 'Convective storms, precipitation',
        'horizon': '7 days',
    },
    'gem': {
        'name': 'GEM (Canadian)',
        'url': 'https://api.open-meteo.com/v1/gem',
        'update_freq': '12h',
        'best_for': 'Arctic fronts, cold weather events',
        'horizon': '10 days',
    },
}

# ERCOT-critical weather locations
ERCOT_LOCATIONS = {
    'houston': {'lat': 29.76, 'lon': -95.37, 'role': 'demand_center'},
    'dallas': {'lat': 32.78, 'lon': -96.80, 'role': 'demand_center'},
    'west_tx_wind': {'lat': 32.00, 'lon': -101.00, 'role': 'wind_generation'},
    'panhandle_wind': {'lat': 35.50, 'lon': -101.50, 'role': 'wind_generation'},
    'south_tx_wind': {'lat': 27.50, 'lon': -97.50, 'role': 'wind_generation'},
    'west_tx_solar': {'lat': 31.50, 'lon': -103.00, 'role': 'solar_generation'},
}

WEATHER_VARS = 'temperature_2m,wind_speed_100m,shortwave_radiation,cloud_cover,relative_humidity_2m,wind_direction_100m'


class WeatherProvider:
    """Pulls forecast from a single weather model."""
    
    def __init__(self, model_key: str):
        self.key = model_key
        self.config = WEATHER_MODELS[model_key]
        self.name = self.config['name']
        self.url = self.config['url']
        self.last_pull = None
        self.last_data = None
        self.error_count = 0
    
    def pull(self, lat: float, lon: float, hours: int = 48) -> Optional[dict]:
        """Pull forecast from this provider."""
        try:
            params = {
                'latitude': lat,
                'longitude': lon,
                'hourly': WEATHER_VARS,
                'forecast_hours': hours,
                'temperature_unit': 'fahrenheit',
                'wind_speed_unit': 'mph',
                'timezone': 'America/Chicago',
            }
            
            r = requests.get(self.url, params=params, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                self.last_data = data.get('hourly', {})
                self.last_pull = datetime.now()
                self.error_count = 0
                return self.last_data
            else:
                self.error_count += 1
                return None
                
        except Exception as e:
            self.error_count += 1
            return None
    
    @property
    def is_healthy(self):
        return self.error_count < 3


class MultiProviderWeather:
    """
    Pulls weather from all 5 providers and compares them.
    Disagreement between models = uncertainty signal.
    """
    
    def __init__(self):
        self.providers = {key: WeatherProvider(key) for key in WEATHER_MODELS}
        self.comparison_history = []
    
    def pull_all(self, location: str = 'west_tx_wind') -> dict:
        """
        Pull forecasts from all providers for one location.
        Compare them and generate uncertainty signals.
        """
        loc = ERCOT_LOCATIONS.get(location, ERCOT_LOCATIONS['west_tx_wind'])
        results = {}
        
        for key, provider in self.providers.items():
            data = provider.pull(loc['lat'], loc['lon'])
            if data:
                results[key] = data
        
        return results
    
    def pull_all_simulated(self, location: str = 'west_tx_wind', 
                           hours: int = 24) -> dict:
        """
        Simulated multi-provider pull for demo/testing.
        Each model has slightly different forecasts — realistic.
        """
        np.random.seed(int(datetime.now().timestamp()) % 1000)
        
        results = {}
        base_hour = datetime.now().hour
        
        for model_key, config in WEATHER_MODELS.items():
            hourly_data = {
                'time': [],
                'temperature_2m': [],
                'wind_speed_100m': [],
                'shortwave_radiation': [],
                'cloud_cover': [],
                'wind_direction_100m': [],
            }
            
            # Each model has its own bias and noise characteristics
            model_biases = {
                'gfs': {'temp': 0, 'wind': 0, 'solar': 0, 'noise': 1.0},
                'hrrr': {'temp': -0.5, 'wind': 1.0, 'solar': -10, 'noise': 0.7},  # most accurate for TX
                'ecmwf': {'temp': 0.3, 'wind': -0.5, 'solar': 5, 'noise': 0.8},
                'icon': {'temp': -1.0, 'wind': 0.8, 'solar': -15, 'noise': 1.2},
                'gem': {'temp': 1.5, 'wind': -1.5, 'solar': 10, 'noise': 1.5},  # least accurate for TX
            }
            
            bias = model_biases.get(model_key, {'temp': 0, 'wind': 0, 'solar': 0, 'noise': 1})
            
            for h in range(hours):
                forecast_hour = (base_hour + h) % 24
                t = datetime.now() + timedelta(hours=h)
                
                # Base weather (ground truth)
                true_temp = 75 + 15 * np.sin((forecast_hour - 6) / 24 * 2 * np.pi)
                true_wind = max(0, 18 + 10 * np.sin((forecast_hour - 3) / 24 * 2 * np.pi))
                true_solar = max(0, np.sin((forecast_hour - 6) / 13 * np.pi) * 900) if 6 < forecast_hour < 19 else 0
                true_cloud = max(0, min(100, 25 + 20 * np.sin(forecast_hour / 8)))
                
                # Model's version (bias + noise, noise grows with forecast horizon)
                horizon_noise = 1 + h * 0.05  # uncertainty grows over time
                
                temp = true_temp + bias['temp'] + np.random.normal(0, 1.5 * bias['noise'] * horizon_noise)
                wind = max(0, true_wind + bias['wind'] + np.random.normal(0, 2.0 * bias['noise'] * horizon_noise))
                solar = max(0, true_solar + bias['solar'] + np.random.normal(0, 30 * bias['noise'] * horizon_noise))
                cloud = max(0, min(100, true_cloud + np.random.normal(0, 10 * bias['noise'] * horizon_noise)))
                wind_dir = 225 + np.random.normal(0, 15 * bias['noise'])  # SW prevailing
                
                hourly_data['time'].append(t.strftime('%Y-%m-%dT%H:00'))
                hourly_data['temperature_2m'].append(round(temp, 1))
                hourly_data['wind_speed_100m'].append(round(wind, 1))
                hourly_data['shortwave_radiation'].append(round(solar, 1))
                hourly_data['cloud_cover'].append(round(cloud, 1))
                hourly_data['wind_direction_100m'].append(round(wind_dir, 0))
            
            results[model_key] = hourly_data
        
        return results
    
    def compare(self, multi_data: dict, variable: str = 'wind_speed_100m') -> dict:
        """
        Compare forecasts across all providers for a specific variable.
        
        Returns:
            consensus: weighted average forecast
            spread: range between models (uncertainty signal)
            confidence: inverse of spread (0-1)
            individual: each model's forecast
            disagreement_hours: hours where models disagree significantly
        """
        if not multi_data:
            return {'consensus': [], 'spread': [], 'confidence': [], 'individual': {}}
        
        # Extract the variable from each model
        model_forecasts = {}
        min_length = float('inf')
        
        for model_key, data in multi_data.items():
            if variable in data:
                values = data[variable]
                model_forecasts[model_key] = np.array(values, dtype=float)
                min_length = min(min_length, len(values))
        
        if not model_forecasts:
            return {'consensus': [], 'spread': [], 'confidence': [], 'individual': {}}
        
        # Trim to same length
        for key in model_forecasts:
            model_forecasts[key] = model_forecasts[key][:int(min_length)]
        
        n_hours = int(min_length)
        
        # Model weights (HRRR gets highest weight for Texas)
        weights = {
            'hrrr': 0.30,   # best for short-term TX
            'gfs': 0.25,    # solid all-around
            'ecmwf': 0.25,  # best for medium-range
            'icon': 0.10,   # decent
            'gem': 0.10,    # least reliable for TX
        }
        
        # Normalize weights for available models
        available_weights = {k: v for k, v in weights.items() if k in model_forecasts}
        total_w = sum(available_weights.values())
        norm_weights = {k: v / total_w for k, v in available_weights.items()}
        
        # Calculate consensus (weighted average)
        consensus = np.zeros(n_hours)
        for model_key, forecast in model_forecasts.items():
            w = norm_weights.get(model_key, 1.0 / len(model_forecasts))
            consensus += forecast * w
        
        # Calculate spread (std across models at each hour)
        all_forecasts = np.array(list(model_forecasts.values()))
        spread = np.std(all_forecasts, axis=0)
        
        # Min/max range
        range_low = np.min(all_forecasts, axis=0)
        range_high = np.max(all_forecasts, axis=0)
        
        # Confidence (inverse of normalized spread)
        if variable == 'wind_speed_100m':
            confidence = np.clip(1.0 - spread / 10, 0.1, 0.95)
        elif variable == 'temperature_2m':
            confidence = np.clip(1.0 - spread / 5, 0.1, 0.95)
        elif variable == 'shortwave_radiation':
            confidence = np.clip(1.0 - spread / 100, 0.1, 0.95)
        else:
            confidence = np.clip(1.0 - spread / 20, 0.1, 0.95)
        
        # Find disagreement hours
        disagreement_hours = []
        for h in range(n_hours):
            if variable == 'wind_speed_100m' and spread[h] > 5:
                disagreement_hours.append(h)
            elif variable == 'temperature_2m' and spread[h] > 3:
                disagreement_hours.append(h)
            elif variable == 'shortwave_radiation' and spread[h] > 100:
                disagreement_hours.append(h)
        
        return {
            'consensus': consensus.tolist(),
            'spread': spread.tolist(),
            'range_low': range_low.tolist(),
            'range_high': range_high.tolist(),
            'confidence': confidence.tolist(),
            'individual': {k: v.tolist() for k, v in model_forecasts.items()},
            'weights': norm_weights,
            'disagreement_hours': disagreement_hours,
            'n_models': len(model_forecasts),
        }
    
    def generate_dispatch_signals(self, multi_data: dict) -> dict:
        """
        Translate multi-model weather into dispatch-ready signals.
        This is what gets fed to the price forecast and dispatch agents.
        """
        wind = self.compare(multi_data, 'wind_speed_100m')
        temp = self.compare(multi_data, 'temperature_2m')
        solar = self.compare(multi_data, 'shortwave_radiation')
        cloud = self.compare(multi_data, 'cloud_cover')
        
        n_hours = min(
            len(wind['consensus']),
            len(temp['consensus']),
            len(solar['consensus']),
        )
        
        signals = []
        for h in range(n_hours):
            # Net load estimate from weather consensus
            cdh = max(0, temp['consensus'][h] - 75)
            demand = 45000 + cdh * 800
            
            wind_speed = wind['consensus'][h]
            if wind_speed < 7:
                wind_gen = 0
            elif wind_speed < 28:
                wind_gen = ((wind_speed - 7) / 21) ** 3 * 30000
            else:
                wind_gen = 30000
            
            solar_gen = solar['consensus'][h] / 1000 * 22000
            net_load = demand - wind_gen - solar_gen
            
            # Uncertainty from model disagreement
            wind_uncertainty = wind['spread'][h] if h < len(wind['spread']) else 0
            temp_uncertainty = temp['spread'][h] if h < len(temp['spread']) else 0
            solar_uncertainty = solar['spread'][h] if h < len(solar['spread']) else 0
            
            # Overall weather confidence (average across variables)
            weather_conf = np.mean([
                wind['confidence'][h] if h < len(wind['confidence']) else 0.5,
                temp['confidence'][h] if h < len(temp['confidence']) else 0.5,
                solar['confidence'][h] if h < len(solar['confidence']) else 0.5,
            ])
            
            # Dispatch recommendation strength
            if weather_conf > 0.8:
                dispatch_strength = 'strong'
            elif weather_conf > 0.6:
                dispatch_strength = 'moderate'
            else:
                dispatch_strength = 'weak'
            
            signals.append({
                'hour': h,
                'wind_consensus': round(wind['consensus'][h], 1),
                'wind_spread': round(wind_uncertainty, 1),
                'temp_consensus': round(temp['consensus'][h], 1),
                'temp_spread': round(temp_uncertainty, 1),
                'solar_consensus': round(solar['consensus'][h], 0),
                'solar_spread': round(solar_uncertainty, 0),
                'net_load_mw': round(net_load, 0),
                'weather_confidence': round(weather_conf, 3),
                'dispatch_strength': dispatch_strength,
            })
        
        return {
            'signals': signals,
            'wind_disagreement_hours': wind['disagreement_hours'],
            'model_weights': wind['weights'],
            'n_models': wind['n_models'],
        }


def demo():
    """Demonstrate multi-provider weather intelligence."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Multi-Provider Weather Intelligence")
    print("=" * 70)
    print()
    print("  5 weather models, each seeing the atmosphere differently.")
    print("  Disagreement = uncertainty = be careful trading.")
    print()
    
    # Initialize
    mpw = MultiProviderWeather()
    
    # Pull from all models (simulated for demo)
    print("  Pulling from 5 weather models for West TX wind corridor...\n")
    multi_data = mpw.pull_all_simulated('west_tx_wind', hours=24)
    
    for model_key, data in multi_data.items():
        config = WEATHER_MODELS[model_key]
        print(f"  ✓ {config['name']:<25} {len(data['time'])} hours | Best for: {config['best_for']}")
    
    # Compare wind forecasts
    wind_comparison = mpw.compare(multi_data, 'wind_speed_100m')
    
    print(f"\n{'='*70}")
    print("WIND SPEED FORECAST COMPARISON (100m hub height)")
    print(f"{'='*70}")
    print(f"\n  Model weights: ", end='')
    for model, weight in wind_comparison['weights'].items():
        print(f"{model}={weight:.0%} ", end='')
    print()
    
    print(f"\n  {'Hour':<6} {'Consensus':>10} {'Spread':>8} {'Conf':>6} {'Range':>14} ", end='')
    for model in ['hrrr', 'gfs', 'ecmwf', 'icon', 'gem']:
        print(f"  {model:>6}", end='')
    print(f"  {'Signal':>8}")
    print(f"  {'-'*95}")
    
    for h in range(24):
        cons = wind_comparison['consensus'][h]
        spread = wind_comparison['spread'][h]
        conf = wind_comparison['confidence'][h]
        lo = wind_comparison['range_low'][h]
        hi = wind_comparison['range_high'][h]
        
        disagree = '⚠' if h in wind_comparison['disagreement_hours'] else ' '
        
        print(f"  {h:02d}:00  {cons:>8.1f}mph {spread:>6.1f}  {conf:>5.0%}  [{lo:>5.1f}-{hi:>5.1f}]", end='')
        
        for model in ['hrrr', 'gfs', 'ecmwf', 'icon', 'gem']:
            val = wind_comparison['individual'][model][h]
            print(f"  {val:>6.1f}", end='')
        
        print(f"  {disagree}")
    
    # Generate dispatch signals
    dispatch = mpw.generate_dispatch_signals(multi_data)
    
    print(f"\n{'='*70}")
    print("DISPATCH SIGNALS FROM WEATHER")
    print(f"{'='*70}")
    print(f"\n  {'Hour':<6} {'Wind':>6} {'±':>5} {'Temp':>6} {'±':>5} {'Solar':>6} {'±':>5} {'Net Load':>10} {'Conf':>6} {'Strength':>10}")
    print(f"  {'-'*75}")
    
    for sig in dispatch['signals']:
        print(f"  {sig['hour']:02d}:00  "
              f"{sig['wind_consensus']:>5.1f} {sig['wind_spread']:>4.1f}  "
              f"{sig['temp_consensus']:>5.1f} {sig['temp_spread']:>4.1f}  "
              f"{sig['solar_consensus']:>5.0f} {sig['solar_spread']:>4.0f}  "
              f"{sig['net_load_mw']:>9.0f}  "
              f"{sig['weather_confidence']:>5.0%}  "
              f"{sig['dispatch_strength']:>10}")
    
    # Summary
    disagreements = len(dispatch['wind_disagreement_hours'])
    avg_conf = np.mean([s['weather_confidence'] for s in dispatch['signals']])
    strong = sum(1 for s in dispatch['signals'] if s['dispatch_strength'] == 'strong')
    weak = sum(1 for s in dispatch['signals'] if s['dispatch_strength'] == 'weak')
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"  Hours with model disagreement: {disagreements}/24")
    print(f"  Average weather confidence: {avg_conf:.0%}")
    print(f"  Strong dispatch signals: {strong}/24")
    print(f"  Weak dispatch signals (trade cautiously): {weak}/24")
    
    print(f"\n{'='*70}")
    print("HOW THIS FLOWS INTO DISPATCH:")
    print(f"{'='*70}")
    print("""
  Weather confidence feeds directly into the dispatch agent:
  
  STRONG signal (>80% confidence):
    → Trade aggressively at full power
    → Trust the price forecast
  
  MODERATE signal (60-80% confidence):
    → Trade at reduced intensity
    → Widen stop-loss thresholds
  
  WEAK signal (<60% confidence):
    → Reduce position or hold
    → Flag for Claude reasoning review
    → Alert operator if critical hours
  
  This is what separates VoltStream from single-model systems:
  We KNOW when we don't know. And when we don't know, we
  protect the customer's money instead of guessing.
""")


if __name__ == '__main__':
    demo()
