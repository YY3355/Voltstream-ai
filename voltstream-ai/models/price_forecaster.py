"""
ERCOT Price Forecasting Model
===============================
XGBoost-based model to forecast real-time settlement point prices.
This is the core IP of the battery optimization startup.

Features engineered:
- Temporal: hour, day of week, month, season
- Load: system load, net load, load ramps
- Generation: wind, solar, renewable penetration
- Weather: temperature, cooling/heating degree hours
- Market: lagged prices, price momentum, volatility
- Gas: natural gas price proxy

Target: Next-hour real-time price
"""

import pandas as pd
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error
import xgboost as xgb
import warnings
import json
warnings.filterwarnings('ignore')


def engineer_features(df):
    """Create features for price forecasting."""
    
    feat = df.copy()
    
    # === TEMPORAL FEATURES ===
    feat['hour'] = feat.index.hour
    feat['day_of_week'] = feat.index.dayofweek
    feat['month'] = feat.index.month
    feat['is_weekend'] = (feat['day_of_week'] >= 5).astype(int)
    feat['quarter'] = feat.index.quarter
    
    # Cyclical encoding (important for time features)
    feat['hour_sin'] = np.sin(2 * np.pi * feat['hour'] / 24)
    feat['hour_cos'] = np.cos(2 * np.pi * feat['hour'] / 24)
    feat['month_sin'] = np.sin(2 * np.pi * feat['month'] / 12)
    feat['month_cos'] = np.cos(2 * np.pi * feat['month'] / 12)
    
    # === LOAD FEATURES ===
    feat['load_ramp_1h'] = feat['system_load_mw'].diff(1)
    feat['load_ramp_4h'] = feat['system_load_mw'].diff(4)
    feat['load_rolling_mean_6h'] = feat['system_load_mw'].rolling(6).mean()
    feat['load_rolling_mean_24h'] = feat['system_load_mw'].rolling(24).mean()
    feat['load_vs_24h_avg'] = feat['system_load_mw'] / feat['load_rolling_mean_24h']
    
    # === NET LOAD FEATURES ===
    feat['net_load_ramp_1h'] = feat['net_load_mw'].diff(1)
    feat['net_load_pct_of_total'] = feat['net_load_mw'] / feat['system_load_mw']
    
    # === RENEWABLE FEATURES ===
    feat['renewable_penetration'] = (feat['wind_generation_mw'] + feat['solar_generation_mw']) / feat['system_load_mw']
    feat['wind_ramp_1h'] = feat['wind_generation_mw'].diff(1)
    feat['solar_ramp_1h'] = feat['solar_generation_mw'].diff(1)
    feat['wind_rolling_4h'] = feat['wind_generation_mw'].rolling(4).mean()
    
    # === WEATHER FEATURES ===
    feat['cooling_degree_hours'] = np.maximum(0, feat['temperature_f'] - 75)
    feat['heating_degree_hours'] = np.maximum(0, 40 - feat['temperature_f'])
    feat['temp_ramp_4h'] = feat['temperature_f'].diff(4)
    
    # === PRICE LAG FEATURES (critical for short-term forecasting) ===
    for lag in [1, 2, 3, 4, 6, 12, 24, 48, 168]:  # 168 = 1 week
        feat[f'rt_price_lag_{lag}h'] = feat['rt_price'].shift(lag)
    
    # Price momentum
    feat['price_momentum_4h'] = feat['rt_price'].rolling(4).mean() - feat['rt_price'].rolling(12).mean()
    feat['price_volatility_24h'] = feat['rt_price'].rolling(24).std()
    feat['price_max_24h'] = feat['rt_price'].rolling(24).max()
    feat['price_min_24h'] = feat['rt_price'].rolling(24).min()
    feat['price_range_24h'] = feat['price_max_24h'] - feat['price_min_24h']
    
    # Same hour yesterday and last week
    feat['price_same_hour_yesterday'] = feat['rt_price'].shift(24)
    feat['price_same_hour_last_week'] = feat['rt_price'].shift(168)
    
    # DA-RT spread (if DA is available before RT)
    feat['da_rt_spread_lag1'] = feat['da_price'].shift(1) - feat['rt_price'].shift(1)
    
    # === GAS PRICE ===
    feat['gas_x_load'] = feat['gas_price_mmbtu'] * feat['net_load_mw'] / 1e6  # interaction
    
    # === ANCILLARY SERVICE FEATURES ===
    feat['reg_up_lag1'] = feat['reg_up_price'].shift(1)
    feat['as_total_lag1'] = (feat['reg_up_price'] + feat['reg_down_price'] + feat['rrs_price']).shift(1)
    
    return feat


def build_forecasting_model(df, forecast_horizon=1):
    """
    Build and evaluate XGBoost price forecasting model.
    
    Args:
        df: DataFrame with ERCOT market data
        forecast_horizon: hours ahead to forecast (1 = next hour)
    
    Returns:
        model, feature_names, metrics
    """
    
    print(f"\n{'='*70}")
    print(f"BUILDING ERCOT PRICE FORECASTING MODEL")
    print(f"Forecast Horizon: {forecast_horizon} hour(s) ahead")
    print(f"{'='*70}")
    
    # Engineer features
    print("\nEngineering features...")
    feat = engineer_features(df)
    
    # Target: price N hours ahead
    feat['target'] = feat['rt_price'].shift(-forecast_horizon)
    
    # Drop rows with NaN (from lagging/rolling)
    feat = feat.dropna()
    
    # Define feature columns (exclude target, raw prices, timestamps)
    exclude_cols = ['target', 'rt_price', 'da_price', 'reg_up_price', 
                    'reg_down_price', 'rrs_price']
    feature_cols = [c for c in feat.columns if c not in exclude_cols]
    
    X = feat[feature_cols]
    y = feat['target']
    
    print(f"Features: {len(feature_cols)}")
    print(f"Samples: {len(X):,}")
    
    # Time series cross-validation
    print("\nRunning time-series cross-validation (5 folds)...")
    tscv = TimeSeriesSplit(n_splits=5)
    
    fold_metrics = []
    
    for fold, (train_idx, test_idx) in enumerate(tscv.split(X)):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        model = xgb.XGBRegressor(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
        )
        
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False,
        )
        
        y_pred = model.predict(X_test)
        
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        
        # Direction accuracy (did we predict price going up/down correctly?)
        y_test_direction = np.sign(y_test.values - y.iloc[test_idx - 1].values)
        y_pred_direction = np.sign(y_pred - y.iloc[test_idx - 1].values)
        direction_accuracy = np.mean(y_test_direction == y_pred_direction) * 100
        
        # Revenue-weighted accuracy (how good are we when it matters most?)
        high_price_mask = np.abs(y_test) > 50
        if high_price_mask.sum() > 0:
            high_price_mae = mean_absolute_error(y_test[high_price_mask], y_pred[high_price_mask])
        else:
            high_price_mae = 0
        
        fold_metrics.append({
            'fold': fold + 1,
            'mae': mae,
            'rmse': rmse,
            'direction_accuracy': direction_accuracy,
            'high_price_mae': high_price_mae,
            'test_size': len(test_idx)
        })
        
        print(f"  Fold {fold+1}: MAE=${mae:.2f}/MWh | RMSE=${rmse:.2f} | "
              f"Direction={direction_accuracy:.1f}% | High-Price MAE=${high_price_mae:.2f}")
    
    # Train final model on all data
    print("\nTraining final model on full dataset...")
    final_model = xgb.XGBRegressor(
        n_estimators=500,
        max_depth=8,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
    )
    final_model.fit(X, y, verbose=False)
    
    # Feature importance
    importance = pd.Series(
        final_model.feature_importances_, 
        index=feature_cols
    ).sort_values(ascending=False)
    
    print(f"\n{'TOP 15 MOST IMPORTANT FEATURES':=^70}")
    for feat_name, imp in importance.head(15).items():
        bar = '█' * int(imp * 200)
        print(f"  {feat_name:<35} {imp:.4f} {bar}")
    
    # Summary metrics
    avg_metrics = {
        'avg_mae': np.mean([m['mae'] for m in fold_metrics]),
        'avg_rmse': np.mean([m['rmse'] for m in fold_metrics]),
        'avg_direction_accuracy': np.mean([m['direction_accuracy'] for m in fold_metrics]),
        'avg_high_price_mae': np.mean([m['high_price_mae'] for m in fold_metrics]),
    }
    
    print(f"\n{'AVERAGE CROSS-VALIDATION METRICS':=^70}")
    print(f"  Mean Absolute Error:     ${avg_metrics['avg_mae']:.2f}/MWh")
    print(f"  Root Mean Squared Error: ${avg_metrics['avg_rmse']:.2f}/MWh")
    print(f"  Direction Accuracy:      {avg_metrics['avg_direction_accuracy']:.1f}%")
    print(f"  High-Price MAE:          ${avg_metrics['avg_high_price_mae']:.2f}/MWh")
    
    # Save model
    final_model.save_model('/home/claude/price_forecast_model.json')
    print(f"\nModel saved to price_forecast_model.json")
    
    return final_model, feature_cols, avg_metrics, importance


if __name__ == '__main__':
    # Load data
    print("Loading ERCOT market data...")
    df = pd.read_csv('/home/claude/ercot_market_data.csv', index_col='timestamp', parse_dates=True)
    
    # Build 1-hour ahead forecast
    model, features, metrics, importance = build_forecasting_model(df, forecast_horizon=1)
    
    # Also build 4-hour ahead forecast for longer planning
    print("\n\n" + "=" * 70)
    model_4h, features_4h, metrics_4h, _ = build_forecasting_model(df, forecast_horizon=4)
    
    # Save feature list
    with open('/home/claude/model_features.json', 'w') as f:
        json.dump({'features_1h': features, 'features_4h': features_4h}, f)
    
    print("\n\n" + "=" * 70)
    print("PHASE 1 FORECASTING MODELS COMPLETE")
    print("=" * 70)
    print(f"\n1-Hour Ahead: MAE=${metrics['avg_mae']:.2f}/MWh, Direction={metrics['avg_direction_accuracy']:.1f}%")
    print(f"4-Hour Ahead: MAE=${metrics_4h['avg_mae']:.2f}/MWh, Direction={metrics_4h['avg_direction_accuracy']:.1f}%")
    print(f"\nThese models form the 'brain' of your battery dispatch system.")
