"""
VoltStream AI — ERCOT Data Pipeline
Ready to run on YOUR laptop.

INSTRUCTIONS:
1. Make sure Python is installed (python.org if you don't have it)
2. Open terminal/command prompt
3. Run: pip install requests pandas
4. Fill in your ERCOT password below (line 15)
5. Run: python voltstream_ercot_live.py

That's it. It will pull real ERCOT prices and show you the market.
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import json
import time

# =====================================================
# YOUR CREDENTIALS (subscription key already set!)
# =====================================================
ERCOT_EMAIL = "mikeoc1525@gmail.com"
ERCOT_PASSWORD = "PASTE_YOUR_ERCOT_PASSWORD_HERE"  # <-- Fill this in
ERCOT_SUBSCRIPTION_KEY = "1fff599a108b4da6888d88bb964ba37a"
# =====================================================

AUTH_URL = (
    "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/"
    "B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
)
API_BASE = "https://api.ercot.com/api/public-reports"


def authenticate():
    """Get access token from ERCOT."""
    print("\n🔑 Authenticating with ERCOT...")
    
    response = requests.post(
        AUTH_URL,
        data={
            'username': ERCOT_EMAIL,
            'password': ERCOT_PASSWORD,
            'grant_type': 'password',
            'scope': 'openid+fec253ea-0d06-4272-a5e6-b478baeecd70+offline_access',
            'client_id': 'fec253ea-0d06-4272-a5e6-b478baeecd70',
            'response_type': 'id_token',
        },
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    
    if response.status_code == 200:
        token = response.json().get('access_token')
        print("   ✅ Authentication successful!")
        return token
    else:
        print(f"   ❌ Authentication failed: {response.status_code}")
        print(f"   Response: {response.text[:300]}")
        print("\n   Check: Is your password correct on line 15?")
        return None


def api_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Ocp-Apim-Subscription-Key': ERCOT_SUBSCRIPTION_KEY,
    }


def fetch_ercot(endpoint, token, params=None, max_pages=10):
    """Fetch data from ERCOT API with pagination."""
    url = f"{API_BASE}{endpoint}"
    all_records = []
    
    base_params = {'size': 1000}
    if params:
        base_params.update(params)
    
    for page in range(1, max_pages + 1):
        base_params['page'] = page
        
        r = requests.get(url, headers=api_headers(token), params=base_params)
        
        if r.status_code == 401:
            print("   ⚠️  Token expired, re-authenticating...")
            token = authenticate()
            if not token:
                break
            r = requests.get(url, headers=api_headers(token), params=base_params)
        
        if r.status_code != 200:
            print(f"   API error: {r.status_code} - {r.text[:200]}")
            break
        
        data = r.json()
        records = data.get('data', [])
        
        if not records:
            break
        
        all_records.extend(records)
        
        total_pages = data.get('_meta', {}).get('totalPages', 1)
        if page >= total_pages:
            break
        
        time.sleep(0.3)  # Be nice to the API
    
    return all_records, token


def pull_realtime_prices(token, date_str):
    """Pull RT Settlement Point Prices for Houston Hub."""
    print(f"\n📊 Pulling RT prices for {date_str}...")
    
    records, token = fetch_ercot(
        '/np6-905-cd/spp_node_zone_hub',
        token,
        params={
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
            'settlementPoint': 'HB_HOUSTON',
        }
    )
    
    if records:
        df = pd.DataFrame(records)
        print(f"   ✅ Got {len(df)} RT price records")
        return df, token
    else:
        print("   ⚠️  No RT data returned")
        return pd.DataFrame(), token


def pull_dayahead_prices(token, date_str):
    """Pull DA Settlement Point Prices for Houston Hub."""
    print(f"\n📊 Pulling DA prices for {date_str}...")
    
    records, token = fetch_ercot(
        '/np4-190-cd/dam_stlmnt_pnt_prices',
        token,
        params={
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
            'settlementPoint': 'HB_HOUSTON',
        }
    )
    
    if records:
        df = pd.DataFrame(records)
        print(f"   ✅ Got {len(df)} DA price records")
        return df, token
    else:
        print("   ⚠️  No DA data returned")
        return pd.DataFrame(), token


def pull_system_load(token, date_str):
    """Pull actual system load."""
    print(f"\n📊 Pulling system load for {date_str}...")
    
    records, token = fetch_ercot(
        '/np6-345-cd/act_sys_load_by_wzn',
        token,
        params={
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
        }
    )
    
    if records:
        df = pd.DataFrame(records)
        print(f"   ✅ Got {len(df)} load records")
        return df, token
    else:
        print("   ⚠️  No load data returned")
        return pd.DataFrame(), token


def pull_wind_generation(token, date_str):
    """Pull wind generation data."""
    print(f"\n📊 Pulling wind generation for {date_str}...")
    
    records, token = fetch_ercot(
        '/np4-732-cd/wpp_hrly_avrg_actl_fcast',
        token,
        params={
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
        }
    )
    
    if records:
        df = pd.DataFrame(records)
        print(f"   ✅ Got {len(df)} wind records")
        return df, token
    else:
        print("   ⚠️  No wind data returned")
        return pd.DataFrame(), token


def pull_solar_generation(token, date_str):
    """Pull solar generation data."""
    print(f"\n📊 Pulling solar generation for {date_str}...")
    
    records, token = fetch_ercot(
        '/np4-737-cd/spp_hrly_actual_fcast',
        token,
        params={
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
        }
    )
    
    if records:
        df = pd.DataFrame(records)
        print(f"   ✅ Got {len(df)} solar records")
        return df, token
    else:
        print("   ⚠️  No solar data returned")
        return pd.DataFrame(), token


def main():
    print("=" * 60)
    print("⚡ VoltStream AI — ERCOT Live Data Pipeline")
    print("=" * 60)
    
    if ERCOT_PASSWORD == "PASTE_YOUR_ERCOT_PASSWORD_HERE":
        print("\n❌ You need to fill in your ERCOT password on line 15!")
        print("   Open this file and replace PASTE_YOUR_ERCOT_PASSWORD_HERE")
        print("   with the password you used at apiexplorer.ercot.com")
        return
    
    # Step 1: Authenticate
    token = authenticate()
    if not token:
        return
    
    # Step 2: Pull today's data as a test
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"\n{'=' * 60}")
    print(f"Testing with yesterday's data: {yesterday}")
    print(f"{'=' * 60}")
    
    rt_df, token = pull_realtime_prices(token, yesterday)
    da_df, token = pull_dayahead_prices(token, yesterday)
    load_df, token = pull_system_load(token, yesterday)
    wind_df, token = pull_wind_generation(token, yesterday)
    solar_df, token = pull_solar_generation(token, yesterday)
    
    # Step 3: Show what we got
    if not rt_df.empty:
        print(f"\n{'=' * 60}")
        print(f"✅ SUCCESS! Here's real ERCOT data:")
        print(f"{'=' * 60}")
        print(f"\nRT Price columns: {list(rt_df.columns)}")
        print(f"\nFirst 5 rows:")
        print(rt_df.head().to_string())
        
        # Save everything
        rt_df.to_csv('ercot_rt_prices_real.csv', index=False)
        print(f"\n💾 Saved to ercot_rt_prices_real.csv")
        
        if not da_df.empty:
            da_df.to_csv('ercot_da_prices_real.csv', index=False)
            print(f"💾 Saved to ercot_da_prices_real.csv")
        
        if not load_df.empty:
            load_df.to_csv('ercot_load_real.csv', index=False)
            print(f"💾 Saved to ercot_load_real.csv")
        
        if not wind_df.empty:
            wind_df.to_csv('ercot_wind_real.csv', index=False)
            print(f"💾 Saved to ercot_wind_real.csv")
        
        if not solar_df.empty:
            solar_df.to_csv('ercot_solar_real.csv', index=False)
            print(f"💾 Saved to ercot_solar_real.csv")
    
    # Step 4: Pull 30 days for backtesting
    print(f"\n{'=' * 60}")
    print("Now pulling 30 days of historical data for backtesting...")
    print("This may take a few minutes...")
    print(f"{'=' * 60}")
    
    all_rt = []
    all_da = []
    
    start = datetime.now() - timedelta(days=30)
    end = datetime.now() - timedelta(days=1)
    current = start
    
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        
        rt, token = pull_realtime_prices(token, date_str)
        if not rt.empty:
            all_rt.append(rt)
        
        da, token = pull_dayahead_prices(token, date_str)
        if not da.empty:
            all_da.append(da)
        
        current += timedelta(days=1)
        time.sleep(0.5)  # Rate limiting
    
    if all_rt:
        full_rt = pd.concat(all_rt, ignore_index=True)
        full_rt.to_csv('ercot_30day_rt_prices.csv', index=False)
        print(f"\n💾 30-day RT prices: {len(full_rt)} records → ercot_30day_rt_prices.csv")
    
    if all_da:
        full_da = pd.concat(all_da, ignore_index=True)
        full_da.to_csv('ercot_30day_da_prices.csv', index=False)
        print(f"💾 30-day DA prices: {len(full_da)} records → ercot_30day_da_prices.csv")
    
    print(f"\n{'=' * 60}")
    print("🎉 DATA PULL COMPLETE!")
    print(f"{'=' * 60}")
    print("\nNext steps:")
    print("  1. Come back to Claude with the CSV files")
    print("  2. We'll retrain the model on real data")
    print("  3. We'll generate a backtest with actual ERCOT prices")
    print("  4. That becomes your demo for validation meetings")


if __name__ == '__main__':
    main()
