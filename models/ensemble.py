"""
VoltStream AI — Ensemble Price Forecasting
============================================
Instead of one model, run 5 different models simultaneously.
Each model sees the market differently. When they agree,
confidence is high. When they disagree, something unusual
is happening and we should be cautious.

MODELS:
1. XGBoost — gradient boosted trees, best for tabular data
2. Random Forest — bagged trees, robust to outliers  
3. Linear Regression — simple, interpretable baseline
4. Weather-Only Model — prices purely from weather signals
5. Momentum Model — prices purely from recent price action

The ensemble blends all 5 weighted by recent accuracy.
Models that have been more accurate recently get more weight.
"""

import numpy as np
from datetime import datetime
import json


class BaseModel:
    """Base class for all forecast models."""
    
    def __init__(self, name):
        self.name = name
        self.predictions = []
        self.actuals = []
        self.errors = []
        self.recent_mae = 999  # start high, improve with data
    
    def predict(self, features: dict) -> float:
        raise NotImplementedError
    
    def update(self, predicted: float, actual: float):
        """Track prediction accuracy."""
        self.predictions.append(predicted)
        self.actuals.append(actual)
        self.errors.append(abs(predicted - actual))
        
        # Rolling MAE over last 50 predictions
        recent = self.errors[-50:]
        self.recent_mae = np.mean(recent) if recent else 999
    
    @property
    def weight(self):
        """Weight inversely proportional to recent error."""
        if self.recent_mae <= 0:
            return 1.0
        return 1.0 / (self.recent_mae + 1)


class XGBoostModel(BaseModel):
    """
    Gradient boosted tree model (simplified).
    Best at capturing nonlinear relationships.
    In production: real XGBoost with 49 features.
    """
    
    def __init__(self):
        super().__init__("XGBoost")
        self.learned_splits = {}
    
    def predict(self, features: dict) -> float:
        price = features.get('current_price', 30)
        net_load = features.get('net_load_mw', 40000)
        hour = features.get('hour', 12)
        temp = features.get('temperature', 75)
        
        # Nonlinear response to net load (merit order curve)
        net_load_norm = (net_load - 35000) / 15000
        base = 25 + 15 * net_load_norm + 8 * max(0, net_load_norm - 1) ** 2
        
        # Temperature interaction
        cdh = max(0, temp - 75)
        temp_effect = cdh * 1.5
        
        # Price momentum
        momentum = features.get('price_momentum', 0)
        
        # Hourly seasonality (learned splits)
        if hour in [7, 8, 9]:
            hourly = -10  # solar ramp
        elif hour in [17, 18, 19]:
            hourly = 12  # evening ramp
        elif hour in [10, 11, 12, 13, 14]:
            hourly = -15  # solar peak
        else:
            hourly = 0
        
        forecast = base + temp_effect + momentum * 0.3 + hourly
        forecast += np.random.normal(0, 3)  # model uncertainty
        
        return max(-20, forecast)


class RandomForestModel(BaseModel):
    """
    Random forest model (simplified).
    More robust to outliers than XGBoost.
    Acts as a stabilizing force in the ensemble.
    """
    
    def __init__(self):
        super().__init__("RandomForest")
    
    def predict(self, features: dict) -> float:
        price = features.get('current_price', 30)
        net_load = features.get('net_load_mw', 40000)
        hour = features.get('hour', 12)
        wind = features.get('wind_speed', 15)
        solar = features.get('solar_ghi', 0)
        
        # Simulated forest: average of multiple simple trees
        tree_predictions = []
        
        # Tree 1: price-based
        t1 = price * 0.7 + 10
        tree_predictions.append(t1)
        
        # Tree 2: net load based
        t2 = 20 + (net_load - 30000) / 1500
        tree_predictions.append(t2)
        
        # Tree 3: renewable supply based
        renewable_factor = (wind / 30 * 0.6 + solar / 1000 * 0.4)
        t3 = 45 - renewable_factor * 40
        tree_predictions.append(t3)
        
        # Tree 4: time-based
        if hour < 6:
            t4 = 40
        elif hour < 16:
            t4 = 10
        elif hour < 21:
            t4 = 50
        else:
            t4 = 42
        tree_predictions.append(t4)
        
        # Tree 5: temperature-based
        temp = features.get('temperature', 75)
        t5 = 20 + max(0, temp - 75) * 3
        tree_predictions.append(t5)
        
        # Average (bagging)
        forecast = np.mean(tree_predictions) + np.random.normal(0, 4)
        return max(-20, forecast)


class LinearModel(BaseModel):
    """
    Simple linear regression.
    Interpretable baseline. When this beats the fancy models,
    something is wrong with the fancy models.
    """
    
    def __init__(self):
        super().__init__("Linear")
        # Coefficients (would be learned from data in production)
        self.intercept = 25
        self.coefs = {
            'net_load_norm': 12,
            'temperature_cdh': 2.0,
            'wind_factor': -15,
            'solar_factor': -20,
            'momentum': 0.4,
            'hour_sin': -5,
            'hour_cos': 3,
        }
    
    def predict(self, features: dict) -> float:
        net_load = features.get('net_load_mw', 40000)
        temp = features.get('temperature', 75)
        wind = features.get('wind_speed', 15)
        solar = features.get('solar_ghi', 0)
        hour = features.get('hour', 12)
        momentum = features.get('price_momentum', 0)
        
        prediction = self.intercept
        prediction += self.coefs['net_load_norm'] * (net_load - 35000) / 15000
        prediction += self.coefs['temperature_cdh'] * max(0, temp - 75)
        prediction += self.coefs['wind_factor'] * min(1, max(0, (wind - 7) / 21)) ** 2
        prediction += self.coefs['solar_factor'] * solar / 1000
        prediction += self.coefs['momentum'] * momentum
        prediction += self.coefs['hour_sin'] * np.sin(2 * np.pi * hour / 24)
        prediction += self.coefs['hour_cos'] * np.cos(2 * np.pi * hour / 24)
        
        prediction += np.random.normal(0, 5)
        return max(-20, prediction)


class WeatherOnlyModel(BaseModel):
    """
    Predicts price ONLY from weather — ignores price history.
    
    This model's thesis: price is fundamentally determined by
    net load, which is determined by weather. Everything else
    is noise.
    
    When this model disagrees with price-based models, it often
    catches regime changes (like the solar-driven price inversion)
    before momentum models do.
    """
    
    def __init__(self):
        super().__init__("WeatherOnly")
    
    def predict(self, features: dict) -> float:
        temp = features.get('temperature', 75)
        wind = features.get('wind_speed', 15)
        solar = features.get('solar_ghi', 0)
        cloud = features.get('cloud_cover', 50)
        hour = features.get('hour', 12)
        
        # Demand from temperature
        cdh = max(0, temp - 75)
        hdh = max(0, 40 - temp)
        demand = 45000 + cdh * 800 + hdh * 400
        
        # Wind generation
        if wind < 7:
            wind_gen = 0
        elif wind < 28:
            wind_gen = ((wind - 7) / 21) ** 3 * 30000
        elif wind < 55:
            wind_gen = 30000
        else:
            wind_gen = 0
        
        # Solar generation
        if hour < 6 or hour > 19:
            solar_gen = 0
        else:
            solar_gen = solar / 1000 * 22000 * (1 - cloud / 200)
        
        # Net load → price via merit order
        net_load = demand - wind_gen - solar_gen
        net_load_norm = (net_load - 35000) / 15000
        
        price = 25 + 18 * net_load_norm + 10 * max(0, net_load_norm - 1) ** 2
        
        # Negative prices when oversupplied
        if net_load < 15000:
            price = -5 + net_load / 5000
        
        price += np.random.normal(0, 4)
        return max(-30, price)


class MomentumModel(BaseModel):
    """
    Predicts price ONLY from recent price action.
    
    This model's thesis: prices have momentum and mean-reversion.
    Short-term momentum (1-2 hours) tends to continue.
    Long-term (6-24 hours) tends to revert.
    
    When this model disagrees with weather models, it often
    catches intraday trading patterns that weather can't explain.
    """
    
    def __init__(self):
        super().__init__("Momentum")
        self.price_history = []
    
    def predict(self, features: dict) -> float:
        price = features.get('current_price', 30)
        self.price_history.append(price)
        
        if len(self.price_history) < 4:
            return price
        
        # Short-term momentum (last 2 intervals)
        short_momentum = self.price_history[-1] - self.price_history[-2]
        
        # Medium-term momentum (last 4 intervals)
        med_momentum = (self.price_history[-1] - self.price_history[-4]) / 3
        
        # Long-term mean
        if len(self.price_history) >= 24:
            long_mean = np.mean(self.price_history[-24:])
        else:
            long_mean = np.mean(self.price_history)
        
        # Mean reversion force
        reversion = (long_mean - price) * 0.1
        
        # Volatility scaling
        if len(self.price_history) >= 12:
            volatility = np.std(self.price_history[-12:])
        else:
            volatility = 10
        
        # Combine: short momentum + mean reversion
        forecast = price + short_momentum * 0.3 + med_momentum * 0.2 + reversion
        forecast += np.random.normal(0, volatility * 0.2)
        
        return max(-20, forecast)


class EnsembleForecaster:
    """
    Combines all 5 models into a weighted ensemble.
    
    The ensemble:
    1. Runs all 5 models
    2. Weights by recent accuracy (better models get more vote)
    3. Measures agreement (when models disagree, confidence drops)
    4. Provides uncertainty estimate (spread between models)
    """
    
    def __init__(self):
        self.models = [
            XGBoostModel(),
            RandomForestModel(),
            LinearModel(),
            WeatherOnlyModel(),
            MomentumModel(),
        ]
        self.ensemble_history = []
        self.tick_count = 0
    
    def forecast(self, features: dict) -> dict:
        """
        Generate ensemble forecast.
        
        Returns:
            forecast: weighted average prediction
            confidence: how much models agree (0-1)
            range_low: pessimistic estimate
            range_high: optimistic estimate
            model_predictions: individual model outputs
            disagreement_flag: True if models strongly disagree
        """
        self.tick_count += 1
        
        # Get all model predictions
        predictions = {}
        weights = {}
        
        for model in self.models:
            pred = model.predict(features)
            predictions[model.name] = pred
            weights[model.name] = model.weight
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            norm_weights = {k: v / total_weight for k, v in weights.items()}
        else:
            norm_weights = {k: 1.0 / len(weights) for k in weights}
        
        # Weighted ensemble prediction
        ensemble_price = sum(
            predictions[name] * norm_weights[name] 
            for name in predictions
        )
        
        # Model agreement (inverse of standard deviation)
        pred_values = list(predictions.values())
        pred_std = np.std(pred_values)
        pred_range = max(pred_values) - min(pred_values)
        
        # Confidence based on agreement
        # When all models agree (std < 5), confidence is high
        # When they disagree (std > 20), confidence is low
        confidence = max(0.1, min(0.95, 1.0 - pred_std / 30))
        
        # Disagreement flag
        disagreement = pred_range > 30
        
        # Uncertainty range
        range_low = ensemble_price - pred_std * 1.5
        range_high = ensemble_price + pred_std * 1.5
        
        result = {
            'forecast': round(ensemble_price, 2),
            'confidence': round(confidence, 3),
            'range_low': round(range_low, 2),
            'range_high': round(range_high, 2),
            'std': round(pred_std, 2),
            'disagreement_flag': disagreement,
            'model_predictions': {k: round(v, 2) for k, v in predictions.items()},
            'model_weights': {k: round(v, 3) for k, v in norm_weights.items()},
            'tick': self.tick_count,
        }
        
        self.ensemble_history.append(result)
        return result
    
    def update(self, actual_price: float):
        """Update all models with actual price for accuracy tracking."""
        if not self.ensemble_history:
            return
        
        latest = self.ensemble_history[-1]
        
        for model in self.models:
            pred = latest['model_predictions'].get(model.name, actual_price)
            model.update(pred, actual_price)
        
        # Track ensemble accuracy
        ensemble_error = abs(latest['forecast'] - actual_price)
        latest['actual'] = actual_price
        latest['ensemble_error'] = round(ensemble_error, 2)
    
    def get_model_leaderboard(self) -> list:
        """Rank models by recent accuracy."""
        leaderboard = []
        for model in self.models:
            leaderboard.append({
                'name': model.name,
                'recent_mae': round(model.recent_mae, 2),
                'weight': round(model.weight, 4),
                'predictions': len(model.predictions),
            })
        
        leaderboard.sort(key=lambda x: x['recent_mae'])
        return leaderboard


def demo():
    """Demonstrate the ensemble system."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Ensemble Price Forecasting")
    print("=" * 70)
    print()
    print("  5 models, each seeing the market differently.")
    print("  Agreement = confidence. Disagreement = caution.")
    print()
    
    ensemble = EnsembleForecaster()
    
    # Simulate 48 hours
    np.random.seed(42)
    
    total_ensemble_error = 0
    total_intervals = 0
    
    print(f"  {'Hour':<6} {'Actual':>8} {'Ensembl':>8} {'Conf':>6} {'Range':>14} {'XGB':>7} {'RF':>7} {'Lin':>7} {'Wthr':>7} {'Mom':>7} {'Agree':>6}")
    print(f"  {'-'*95}")
    
    for h in range(48):
        hour = h % 24
        
        # Simulated conditions
        temp = 72 + 15 * np.sin((hour - 6) / 24 * 2 * np.pi) + np.random.normal(0, 2)
        wind = max(0, 15 + 8 * np.sin((hour - 3) / 24 * 2 * np.pi) + np.random.normal(0, 4))
        solar = max(0, np.sin((hour - 6) / 13 * np.pi) * 900) if 6 < hour < 19 else 0
        
        # Net load
        cdh = max(0, temp - 75)
        demand = 45000 + cdh * 800
        wind_gen = min(1, max(0, (wind - 7) / 21)) ** 3 * 30000
        solar_gen = solar / 1000 * 22000
        net_load = demand - wind_gen - solar_gen
        
        # Actual price
        if hour < 6:
            actual = 42 + np.random.normal(0, 8)
        elif hour < 10:
            actual = 30 - (hour - 6) * 7 + np.random.normal(0, 5)
        elif hour < 16:
            actual = 3 + np.random.normal(0, 4)
        elif hour < 20:
            actual = 25 + (hour - 16) * 12 + np.random.normal(0, 8)
        else:
            actual = 45 + np.random.normal(0, 10)
        actual = max(-5, actual)
        
        # Price momentum
        if h > 0:
            momentum = actual - prev_price
        else:
            momentum = 0
        prev_price = actual
        
        features = {
            'current_price': actual,
            'temperature': temp,
            'wind_speed': wind,
            'solar_ghi': solar,
            'cloud_cover': 30,
            'hour': hour,
            'net_load_mw': net_load,
            'price_momentum': momentum,
        }
        
        # Get ensemble forecast
        result = ensemble.forecast(features)
        ensemble.update(actual)
        
        total_ensemble_error += abs(result['forecast'] - actual)
        total_intervals += 1
        
        # Display
        preds = result['model_predictions']
        agree = '✓' if not result['disagreement_flag'] else '✗'
        
        if h < 24 or h >= 40:  # show first and last day
            print(f"  {hour:02d}:00  ${actual:>6.1f}  ${result['forecast']:>6.1f}  "
                  f"{result['confidence']:>5.0%}  "
                  f"[${result['range_low']:>5.0f}-${result['range_high']:>5.0f}]  "
                  f"${preds['XGBoost']:>5.1f} ${preds['RandomForest']:>5.1f} "
                  f"${preds['Linear']:>5.1f} ${preds['WeatherOnly']:>5.1f} "
                  f"${preds['Momentum']:>5.1f}  {agree}")
        elif h == 24:
            print(f"  {'... (Day 2 hours 0-16 omitted) ...':^95}")
    
    # Leaderboard
    print(f"\n{'='*70}")
    print("MODEL LEADERBOARD (by recent accuracy)")
    print(f"{'='*70}")
    
    leaderboard = ensemble.get_model_leaderboard()
    print(f"\n  {'Rank':<6} {'Model':<20} {'MAE':>10} {'Weight':>10}")
    print(f"  {'-'*48}")
    for i, model in enumerate(leaderboard):
        bar = '█' * int(model['weight'] * 50)
        print(f"  #{i+1:<4} {model['name']:<20} ${model['recent_mae']:>8.2f} {model['weight']:>9.4f}  {bar}")
    
    ensemble_mae = total_ensemble_error / total_intervals
    print(f"\n  Ensemble MAE: ${ensemble_mae:.2f}/MWh")
    print(f"  Best single model MAE: ${leaderboard[0]['recent_mae']:.2f}/MWh ({leaderboard[0]['name']})")
    
    improvement = ((leaderboard[0]['recent_mae'] - ensemble_mae) / leaderboard[0]['recent_mae']) * 100
    print(f"  Ensemble improvement over best single: {improvement:+.1f}%")
    
    print(f"\n{'='*70}")
    print("WHY ENSEMBLE MATTERS:")
    print(f"{'='*70}")
    print("""
  1. REDUNDANCY: If one model breaks, four others still work.
     Gridmatic's single model failure = total system failure.
     
  2. CONFIDENCE SIGNAL: When all 5 agree, trade aggressively.
     When they disagree, reduce position or hold.
     No single model can tell you how confident to be.
     
  3. REGIME DETECTION: The WeatherOnly model catches solar-driven
     price inversions BEFORE the Momentum model does. The Momentum
     model catches intraday trading patterns weather can't explain.
     Together, they see everything.
     
  4. ANTI-OVERFITTING: Each model overfits to different things.
     The ensemble cancels out individual biases.
     
  5. ADAPTIVE WEIGHTING: Models that perform well get more weight.
     The ensemble automatically favors whoever is hot right now.
""")


if __name__ == '__main__':
    demo()
