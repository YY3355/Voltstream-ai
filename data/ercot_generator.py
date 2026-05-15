"""
ERCOT Synthetic Data Generator
===============================
Generates realistic ERCOT market data based on actual market patterns:
- Settlement Point Prices (SPPs) for Houston Hub (HB_HOUSTON)
- Day-Ahead and Real-Time prices
- Load data (system-wide)
- Wind and Solar generation
- Temperature data

Patterns modeled from real ERCOT behavior:
- Diurnal price curves (low overnight, peak afternoon)
- Seasonal load variation (Texas summer peaks)
- Wind generation anti-correlation with load
- Solar generation bell curve
- Price spikes during scarcity events
- Negative prices during wind/solar oversupply
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_ercot_data(start_date='2023-01-01', end_date='2025-12-31', freq='1h'):
    """Generate realistic hourly ERCOT market data."""
    
    np.random.seed(42)
    
    # Create hourly datetime index
    dates = pd.date_range(start=start_date, end=end_date, freq=freq)
    n = len(dates)
    
    # === TEMPERATURE (Houston area) ===
    # Seasonal pattern: hot summers (95-105F), mild winters (40-65F)
    day_of_year = dates.dayofyear.values.astype(float)
    hour = dates.hour.values.astype(float)
    
    # Base seasonal temperature
    temp_seasonal = 72 + 20 * np.sin(2 * np.pi * (day_of_year - 100) / 365)
    # Daily variation: cooler at night, warmer afternoon
    temp_diurnal = 8 * np.sin(2 * np.pi * (hour - 6) / 24)
    # Random weather variation
    temp_noise = np.cumsum(np.random.normal(0, 0.5, n))
    temp_noise = temp_noise - np.convolve(temp_noise, np.ones(168)/168, mode='same')  # detrend
    temp_noise = np.clip(temp_noise, -15, 15)
    
    temperature = temp_seasonal + temp_diurnal + temp_noise
    
    # === SYSTEM LOAD (MW) ===
    # ERCOT system load typically 30-80 GW
    # Strong correlation with temperature (cooling load dominates)
    
    # Base load pattern
    load_base = 45000  # MW base
    
    # Temperature-driven load (cooling kicks in above 75F, heating below 40F)
    cooling_load = np.maximum(0, (temperature - 75)) * 800  # MW per degree above 75
    heating_load = np.maximum(0, (40 - temperature)) * 400  # MW per degree below 40
    
    # Hourly demand shape (commercial/industrial ramp)
    hourly_shape = np.array([
        0.82, 0.78, 0.76, 0.75, 0.76, 0.80,  # 0-5 AM
        0.88, 0.95, 1.00, 1.02, 1.04, 1.05,  # 6-11 AM
        1.06, 1.07, 1.08, 1.09, 1.08, 1.05,  # 12-5 PM
        1.00, 0.96, 0.93, 0.90, 0.88, 0.85   # 6-11 PM
    ])
    load_hourly_factor = hourly_shape[hour.astype(int)]
    
    # Day of week effect (weekends ~8% lower)
    dow = dates.dayofweek.values
    weekend_factor = np.where(dow >= 5, 0.92, 1.0)
    
    system_load = (load_base + cooling_load + heating_load) * load_hourly_factor * weekend_factor
    system_load += np.random.normal(0, 1000, n)  # noise
    system_load = np.maximum(system_load, 25000)  # floor
    
    # === WIND GENERATION (MW) ===
    # ERCOT wind: ~30-40 GW installed capacity, typically produces 5-25 GW
    # Wind tends to blow more at night in Texas (nocturnal low-level jet)
    wind_capacity = 38000  # MW
    
    # Seasonal wind pattern (windier in spring, less in summer)
    wind_seasonal = 0.35 + 0.15 * np.cos(2 * np.pi * (day_of_year - 90) / 365)
    
    # Nocturnal enhancement
    wind_nocturnal = 0.05 * np.cos(2 * np.pi * (hour - 3) / 24)
    
    # Multi-day weather patterns (wind comes in fronts)
    wind_weather = np.zeros(n)
    front_arrivals = np.random.poisson(0.15, n)  # fronts every ~7 days
    for i in range(n):
        if front_arrivals[i] > 0:
            # Wind ramps up over 6-12 hours then gradually dies
            ramp_length = np.random.randint(24, 72)
            peak = np.random.uniform(0.5, 0.9)
            for j in range(min(ramp_length, n - i)):
                wind_weather[i + j] = max(wind_weather[i + j], 
                    peak * np.exp(-j / (ramp_length * 0.4)))
    
    wind_cf = wind_seasonal + wind_nocturnal + wind_weather * 0.3
    wind_cf += np.random.normal(0, 0.08, n)
    wind_cf = np.clip(wind_cf, 0.02, 0.95)
    
    wind_generation = wind_capacity * wind_cf
    
    # === SOLAR GENERATION (MW) ===
    # ERCOT solar: ~20 GW installed (growing), bell curve during day
    solar_capacity = 22000  # MW
    
    # Solar follows sun position
    solar_elevation = np.maximum(0, np.sin(2 * np.pi * (hour - 6) / 24))
    solar_elevation = np.where((hour >= 6) & (hour <= 20), solar_elevation, 0)
    
    # Seasonal day length and intensity
    solar_seasonal = 0.7 + 0.3 * np.sin(2 * np.pi * (day_of_year - 80) / 365)
    
    # Cloud cover (random)
    cloud_factor = 1 - np.random.beta(2, 5, n) * 0.6
    
    solar_generation = solar_capacity * solar_elevation * solar_seasonal * cloud_factor
    solar_generation = np.maximum(solar_generation, 0)
    
    # === NET LOAD (Load - Wind - Solar) ===
    net_load = system_load - wind_generation - solar_generation
    
    # === SETTLEMENT POINT PRICES ($/MWh) ===
    # Price is fundamentally driven by net load (supply-demand balance)
    
    # Base price from net load (merit order approximation)
    # Low net load -> gas CC at ~$20-30, high net load -> peakers at $50-200+
    net_load_normalized = (net_load - net_load.mean()) / net_load.std()
    
    base_price = 25 + 15 * net_load_normalized + 5 * np.maximum(0, net_load_normalized - 1)**2
    
    # Natural gas price variation ($/MMBtu -> $/MWh conversion, ~7 heat rate)
    gas_price_base = 3.5  # $/MMBtu base
    gas_seasonal = 0.8 * np.sin(2 * np.pi * (day_of_year - 15) / 365)  # winter premium
    gas_price = gas_price_base + gas_seasonal + np.cumsum(np.random.normal(0, 0.02, n))
    gas_price = np.clip(gas_price - np.convolve(gas_price, np.ones(720)/720, mode='same') + gas_price_base, 2, 8)
    
    fuel_component = gas_price * 7  # heat rate ~7 MMBtu/MWh for marginal gas
    
    # Real-time price with scarcity events
    rt_price = base_price + fuel_component
    
    # SCARCITY SPIKES: When reserves are tight, prices can hit $2000-5000+
    reserve_margin = (system_load * 1.15 - net_load) / system_load  # rough proxy
    scarcity_mask = reserve_margin < 0.05
    # Random extreme events (equipment failures, sudden demand)
    extreme_events = np.random.uniform(0, 1, n) < 0.003  # ~0.3% of hours
    spike_hours = scarcity_mask | extreme_events
    
    # Generate spikes
    spike_values = np.random.exponential(500, n) + 200
    rt_price = np.where(spike_hours, np.maximum(rt_price, spike_values), rt_price)
    
    # NEGATIVE PRICES: When wind/solar oversupply
    oversupply = (wind_generation + solar_generation) > system_load * 0.6
    negative_mask = oversupply & (np.random.uniform(0, 1, n) < 0.4)
    rt_price = np.where(negative_mask, np.random.uniform(-20, 5, n), rt_price)
    
    # Add noise
    rt_price += np.random.normal(0, 3, n)
    
    # Cap at ERCOT system-wide offer cap ($5000)
    rt_price = np.clip(rt_price, -50, 5000)
    
    # Day-Ahead prices: smoother, less volatile version of RT
    # DA tends to under-predict spikes and over-predict lows
    da_price = np.convolve(rt_price, np.ones(3)/3, mode='same')  # smoothed
    da_price += np.random.normal(0, 5, n)
    da_price = np.clip(da_price, -30, 3000)
    
    # === ANCILLARY SERVICE PRICES ===
    # Reg Up, Reg Down, RRS, ECRS
    reg_up_price = np.maximum(0, 8 + 5 * net_load_normalized + np.random.exponential(3, n))
    reg_down_price = np.maximum(0, 5 + 2 * net_load_normalized + np.random.exponential(2, n))
    rrs_price = np.maximum(0, 6 + 4 * net_load_normalized + np.random.exponential(2.5, n))
    
    # === BUILD DATAFRAME ===
    df = pd.DataFrame({
        'timestamp': dates,
        'rt_price': np.round(rt_price, 2),
        'da_price': np.round(da_price, 2),
        'system_load_mw': np.round(system_load, 0),
        'wind_generation_mw': np.round(wind_generation, 0),
        'solar_generation_mw': np.round(solar_generation, 0),
        'net_load_mw': np.round(net_load, 0),
        'temperature_f': np.round(temperature, 1),
        'gas_price_mmbtu': np.round(gas_price, 2),
        'reg_up_price': np.round(reg_up_price, 2),
        'reg_down_price': np.round(reg_down_price, 2),
        'rrs_price': np.round(rrs_price, 2),
    })
    
    df.set_index('timestamp', inplace=True)
    
    return df


def print_data_summary(df):
    """Print summary statistics matching real ERCOT patterns."""
    print("=" * 70)
    print("ERCOT MARKET DATA SUMMARY")
    print("=" * 70)
    print(f"\nDate Range: {df.index[0]} to {df.index[-1]}")
    print(f"Total Hours: {len(df):,}")
    print(f"\n{'Metric':<30} {'Mean':>10} {'Min':>10} {'Max':>10} {'Std':>10}")
    print("-" * 70)
    
    metrics = {
        'RT Price ($/MWh)': 'rt_price',
        'DA Price ($/MWh)': 'da_price',
        'System Load (MW)': 'system_load_mw',
        'Wind Gen (MW)': 'wind_generation_mw',
        'Solar Gen (MW)': 'solar_generation_mw',
        'Net Load (MW)': 'net_load_mw',
        'Temperature (°F)': 'temperature_f',
        'Gas Price ($/MMBtu)': 'gas_price_mmbtu',
        'Reg Up ($/MW)': 'reg_up_price',
    }
    
    for name, col in metrics.items():
        s = df[col]
        print(f"{name:<30} {s.mean():>10.1f} {s.min():>10.1f} {s.max():>10.1f} {s.std():>10.1f}")
    
    # Price distribution
    print(f"\n{'PRICE DISTRIBUTION':=^70}")
    print(f"Hours with negative prices: {(df['rt_price'] < 0).sum():,} ({(df['rt_price'] < 0).mean()*100:.1f}%)")
    print(f"Hours above $100/MWh: {(df['rt_price'] > 100).sum():,} ({(df['rt_price'] > 100).mean()*100:.1f}%)")
    print(f"Hours above $500/MWh: {(df['rt_price'] > 500).sum():,} ({(df['rt_price'] > 500).mean()*100:.1f}%)")
    print(f"Hours above $1000/MWh: {(df['rt_price'] > 1000).sum():,} ({(df['rt_price'] > 1000).mean()*100:.1f}%)")
    
    # Seasonal averages
    print(f"\n{'SEASONAL RT PRICE AVERAGES':=^70}")
    monthly = df['rt_price'].groupby(df.index.month).mean()
    months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    for m, name in enumerate(months, 1):
        if m in monthly.index:
            print(f"  {name}: ${monthly[m]:.2f}/MWh")


if __name__ == '__main__':
    print("Generating 3 years of synthetic ERCOT market data...")
    df = generate_ercot_data()
    print_data_summary(df)
    
    # Save to CSV
    df.to_csv('/home/claude/ercot_market_data.csv')
    print(f"\nData saved to ercot_market_data.csv ({len(df):,} rows)")
