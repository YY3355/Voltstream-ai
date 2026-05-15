"""
VoltStream AI — ERCOT Real Data Pipeline
==========================================
This script connects to ERCOT's public data and pulls real market data.

SETUP (do this Friday night):
1. Go to https://apiexplorer.ercot.com/
2. Click "Sign In/Sign Up" → enter email → verify → create password
3. Go to Products tab → subscribe to "Public API"
4. Go to Profile → copy your "Primary key" (this is your subscription key)
5. Fill in YOUR_EMAIL, YOUR_PASSWORD, YOUR_SUBSCRIPTION_KEY below
6. Run this script

The script pulls:
- Real-time Settlement Point Prices (15-min intervals)
- Day-ahead prices
- System load
- Wind & solar generation

Total setup time: ~15 minutes
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta

# ================================================================
# FILL THESE IN AFTER YOU REGISTER AT apiexplorer.ercot.com
# ================================================================
ERCOT_USERNAME = "YOUR_EMAIL@example.com"
ERCOT_PASSWORD = "YOUR_PASSWORD"
ERCOT_SUBSCRIPTION_KEY = "YOUR_SUBSCRIPTION_KEY"
# ================================================================


class ERCOTDataPipeline:
    """Pulls real ERCOT market data via their public API."""
    
    AUTH_URL = (
        "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/"
        "B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
    )
    API_BASE = "https://api.ercot.com/api/public-reports"
    
    # Key ERCOT data product endpoints
    ENDPOINTS = {
        # Real-time SPPs (15-min settlement intervals)
        'rt_spp': '/np6-905-cd/spp_node_zone_hub',
        # Day-ahead SPPs  
        'da_spp': '/np4-190-cd/dam_stlmnt_pnt_prices',
        # System load by weather zone
        'load': '/np6-345-cd/act_sys_load_by_wzn',
        # Wind generation (hourly actual + forecast)
        'wind': '/np4-732-cd/wpp_hrly_avrg_actl_fcast',
        # Solar generation (hourly actual + forecast)
        'solar': '/np4-737-cd/spp_hrly_actual_fcast',
        # Ancillary service clearing prices
        'as_prices': '/np6-905-cd/spp_node_zone_hub',
    }
    
    def __init__(self, username=None, password=None, subscription_key=None):
        self.username = username or ERCOT_USERNAME
        self.password = password or ERCOT_PASSWORD
        self.subscription_key = subscription_key or ERCOT_SUBSCRIPTION_KEY
        self.access_token = None
    
    def authenticate(self):
        """Get access token from ERCOT B2C auth."""
        print("Authenticating with ERCOT...")
        
        auth_params = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password',
            'scope': 'openid+fec253ea-0d06-4272-a5e6-b478baeecd70+offline_access',
            'client_id': 'fec253ea-0d06-4272-a5e6-b478baeecd70',
            'response_type': 'id_token',
        }
        
        response = requests.post(
            self.AUTH_URL,
            data=auth_params,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get('access_token')
            print("✓ Authentication successful!")
            return True
        else:
            print(f"✗ Authentication failed: {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
    
    def _api_headers(self):
        """Headers for API requests."""
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Ocp-Apim-Subscription-Key': self.subscription_key,
        }
    
    def fetch_data(self, endpoint, params=None, max_pages=5):
        """Fetch data from an ERCOT API endpoint with pagination."""
        
        url = f"{self.API_BASE}{endpoint}"
        all_data = []
        page = 1
        
        default_params = {
            'size': 1000,  # records per page
        }
        if params:
            default_params.update(params)
        
        while page <= max_pages:
            default_params['page'] = page
            
            response = requests.get(
                url,
                headers=self._api_headers(),
                params=default_params
            )
            
            if response.status_code != 200:
                print(f"  API error on page {page}: {response.status_code}")
                break
            
            data = response.json()
            records = data.get('data', [])
            
            if not records:
                break
            
            all_data.extend(records)
            
            # Check if more pages exist
            meta = data.get('_meta', {})
            total_pages = meta.get('totalPages', 1)
            
            if page >= total_pages:
                break
            
            page += 1
        
        return all_data
    
    def get_realtime_prices(self, date_str=None):
        """
        Get real-time Settlement Point Prices for Houston Hub.
        
        Args:
            date_str: Date in 'YYYY-MM-DD' format (default: today)
        """
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\nFetching RT prices for {date_str}...")
        
        params = {
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
            'settlementPoint': 'HB_HOUSTON',
        }
        
        data = self.fetch_data(self.ENDPOINTS['rt_spp'], params)
        
        if data:
            df = pd.DataFrame(data)
            print(f"  ✓ Got {len(df)} RT price records")
            return df
        else:
            print("  ✗ No RT price data returned")
            return pd.DataFrame()
    
    def get_dayahead_prices(self, date_str=None):
        """Get day-ahead Settlement Point Prices."""
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\nFetching DA prices for {date_str}...")
        
        params = {
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
            'settlementPoint': 'HB_HOUSTON',
        }
        
        data = self.fetch_data(self.ENDPOINTS['da_spp'], params)
        
        if data:
            df = pd.DataFrame(data)
            print(f"  ✓ Got {len(df)} DA price records")
            return df
        else:
            print("  ✗ No DA price data returned")
            return pd.DataFrame()
    
    def get_system_load(self, date_str=None):
        """Get actual system load by weather zone."""
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"\nFetching system load for {date_str}...")
        
        params = {
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
        }
        
        data = self.fetch_data(self.ENDPOINTS['load'], params)
        
        if data:
            df = pd.DataFrame(data)
            print(f"  ✓ Got {len(df)} load records")
            return df
        else:
            print("  ✗ No load data returned")
            return pd.DataFrame()
    
    def pull_full_dataset(self, start_date, end_date):
        """
        Pull complete dataset for backtesting.
        Iterates day by day to handle API pagination limits.
        """
        if not self.authenticate():
            return None
        
        print(f"\n{'='*60}")
        print(f"Pulling ERCOT data: {start_date} to {end_date}")
        print(f"{'='*60}")
        
        all_rt_prices = []
        all_da_prices = []
        all_loads = []
        
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            date_str = current.strftime('%Y-%m-%d')
            
            rt = self.get_realtime_prices(date_str)
            if not rt.empty:
                all_rt_prices.append(rt)
            
            da = self.get_dayahead_prices(date_str)
            if not da.empty:
                all_da_prices.append(da)
            
            load = self.get_system_load(date_str)
            if not load.empty:
                all_loads.append(load)
            
            current += timedelta(days=1)
        
        result = {}
        
        if all_rt_prices:
            result['rt_prices'] = pd.concat(all_rt_prices, ignore_index=True)
            print(f"\nTotal RT price records: {len(result['rt_prices']):,}")
        
        if all_da_prices:
            result['da_prices'] = pd.concat(all_da_prices, ignore_index=True)
            print(f"Total DA price records: {len(result['da_prices']):,}")
        
        if all_loads:
            result['load'] = pd.concat(all_loads, ignore_index=True)
            print(f"Total load records: {len(result['load']):,}")
        
        return result
    
    def quick_test(self):
        """Quick test to verify your API credentials work."""
        print("\n" + "="*60)
        print("ERCOT API CONNECTION TEST")
        print("="*60)
        
        if not self.authenticate():
            print("\n⚠ Check your credentials:")
            print("  1. Is your email/password correct?")
            print("  2. Did you subscribe to 'Public API' on the Products page?")
            print("  3. Is your subscription key correct?")
            return False
        
        # Try pulling today's RT prices
        today = datetime.now().strftime('%Y-%m-%d')
        rt = self.get_realtime_prices(today)
        
        if not rt.empty:
            print(f"\n{'='*60}")
            print("✓ SUCCESS! Your ERCOT API connection is working!")
            print(f"{'='*60}")
            print(f"  Got {len(rt)} real-time price records for today")
            print(f"  You're ready to pull historical data for backtesting")
            return True
        else:
            print("\n⚠ Auth worked but no data returned.")
            print("  This might be normal if the API is lagging.")
            print("  Try again in a few minutes.")
            return False


# ================================================================
# ALTERNATIVE: Scrape the public ERCOT webpage (no API key needed)
# This pulls real-time SPP data from the public display page
# ================================================================

def scrape_ercot_realtime_prices():
    """
    Scrape current real-time prices from ERCOT's public webpage.
    No API key required — this is publicly available data.
    """
    url = "https://www.ercot.com/content/cdr/html/real_time_spp.html"
    
    print("Scraping ERCOT real-time SPP page...")
    
    try:
        tables = pd.read_html(url)
        if tables:
            df = tables[0]
            print(f"✓ Got {len(df)} price intervals from ERCOT")
            
            # The table has columns like:
            # Oper Day, Interval Ending, HB_BUSAVG, HB_HOUSTON, HB_NORTH, etc.
            return df
        else:
            print("✗ No tables found on page")
            return pd.DataFrame()
    except Exception as e:
        print(f"✗ Error scraping: {e}")
        return pd.DataFrame()


# ================================================================
# USAGE
# ================================================================

if __name__ == '__main__':
    print("VoltStream AI — ERCOT Data Pipeline")
    print("="*50)
    
    # Check if credentials are configured
    if ERCOT_USERNAME == "YOUR_EMAIL@example.com":
        print("\n⚠ API credentials not configured yet!")
        print("\nTo set up:")
        print("  1. Go to https://apiexplorer.ercot.com/")
        print("  2. Click 'Sign In/Sign Up' in top right")
        print("  3. Enter your email → verify → create password")
        print("  4. Go to 'Products' tab → click 'Public API'")
        print("  5. Enter subscription name → click 'Subscribe'")
        print("  6. Go to 'Profile' → click 'Show' next to Primary key")
        print("  7. Copy the key and paste it in this script")
        print("\n  Total time: ~10 minutes")
        print("\n  Then fill in ERCOT_USERNAME, ERCOT_PASSWORD,")
        print("  and ERCOT_SUBSCRIPTION_KEY at the top of this file.")
        
        print("\n" + "="*50)
        print("Meanwhile, here's live data from ERCOT's public page:")
        print("="*50)
        
        # We can still show real data from the public page
        df = scrape_ercot_realtime_prices()
        if not df.empty:
            print(f"\nToday's Houston Hub prices (HB_HOUSTON):")
            print(f"{'Time':<10} {'Price ($/MWh)':>15}")
            print("-" * 28)
            for _, row in df.iterrows():
                try:
                    time = str(row.get('Interval Ending', row.iloc[1]))
                    price = float(row.get('HB_HOUSTON', row.iloc[3]))
                    print(f"{time:<10} ${price:>13.2f}")
                except:
                    pass
    else:
        # Credentials are set — run the full pipeline
        pipeline = ERCOTDataPipeline()
        pipeline.quick_test()
