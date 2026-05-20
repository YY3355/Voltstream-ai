#!/usr/bin/env python3
"""
VoltStream AI — ERCOT Historical Data Puller
==============================================
Downloads settlement point prices from the ERCOT API.
One command, 90 days of data.

Usage:
  python pull_ercot_data.py                    # last 90 days
  python pull_ercot_data.py --days 30          # last 30 days  
  python pull_ercot_data.py --from 2026-04-01 --to 2026-05-18

Requirements:
  pip install requests pandas

Your ERCOT API credentials go in .env or environment variables:
  ERCOT_EMAIL=mikeoc1525@gmail.com
  ERCOT_KEY=your_api_key
"""

import os
import sys
import json
import time
import requests
import pandas as pd
from datetime import datetime, timedelta


# ERCOT API config
TOKEN_URL = "https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token"
API_BASE = "https://api.ercot.com/api/public-reports"
SPP_ENDPOINT = "/np6-905-cd/spp_node_zone_hub"

# Hub settlement points we care about
HUBS = ['HB_BUSAVG', 'HB_HOUSTON', 'HB_HUBAVG', 'HB_NORTH', 'HB_PAN', 'HB_SOUTH', 'HB_WEST']
LOAD_ZONES = ['LZ_AEN', 'LZ_CPS', 'LZ_HOUSTON', 'LZ_LCRA', 'LZ_NORTH', 'LZ_RAYBN', 'LZ_SOUTH', 'LZ_WEST']
ALL_POINTS = HUBS + LOAD_ZONES


def get_token(email: str, password: str) -> str:
    """Get OAuth token from ERCOT."""
    data = {
        'grant_type': 'password',
        'username': email,
        'password': password,
        'scope': 'openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access',
        'client_id': 'fec253ea-0d06-4272-a5e6-b478baeecd70',
        'response_type': 'id_token',
    }
    
    r = requests.post(TOKEN_URL, data=data, timeout=30)
    if r.status_code == 200:
        return r.json().get('access_token', '')
    else:
        print(f"Token error: {r.status_code} {r.text[:200]}")
        return ''


def pull_day_api(date_str: str, token: str, sub_key: str = '') -> pd.DataFrame:
    """Pull one day of SPP data from the ERCOT API."""
    
    headers = {
        'Authorization': f'Bearer {token}',
    }
    if sub_key:
        headers['Ocp-Apim-Subscription-Key'] = sub_key
    
    all_rows = []
    
    for point in ALL_POINTS:
        params = {
            'deliveryDateFrom': date_str,
            'deliveryDateTo': date_str,
            'settlementPoint': point,
        }
        
        try:
            r = requests.get(
                f"{API_BASE}{SPP_ENDPOINT}",
                headers=headers,
                params=params,
                timeout=30,
            )
            
            if r.status_code == 200:
                data = r.json()
                records = data.get('data', [])
                
                for record in records:
                    all_rows.append({
                        'date': date_str,
                        'hour': record.get('deliveryHour', 0),
                        'interval': record.get('deliveryInterval', 0),
                        'settlement_point': point,
                        'price': record.get('settlementPointPrice', 0),
                    })
            elif r.status_code == 429:
                print(f"  Rate limited, waiting 60s...")
                time.sleep(60)
            else:
                print(f"  API error for {point}: {r.status_code}")
                
        except requests.Timeout:
            print(f"  Timeout for {point}, skipping")
        except Exception as e:
            print(f"  Error for {point}: {e}")
        
        time.sleep(0.5)  # rate limit: 2 requests/sec
    
    if not all_rows:
        return pd.DataFrame()
    
    df = pd.DataFrame(all_rows)
    
    # Pivot from long to wide format (one column per settlement point)
    pivoted = df.pivot_table(
        index=['date', 'hour', 'interval'],
        columns='settlement_point',
        values='price',
        aggfunc='first',
    ).reset_index()
    
    # Create interval ending format (like ERCOT website)
    pivoted['Interval Ending'] = pivoted['hour'] * 100 + pivoted['interval'] * 15
    pivoted['Oper Day'] = pivoted['date'].apply(lambda d: datetime.strptime(d, '%Y-%m-%d').strftime('%m/%d/%Y'))
    
    # Reorder columns to match our CSV format
    cols = ['Oper Day', 'Interval Ending'] + [c for c in ALL_POINTS if c in pivoted.columns]
    result = pivoted[[c for c in cols if c in pivoted.columns]].sort_values(['Oper Day', 'Interval Ending'])
    
    return result


def pull_day_scrape(date_str: str) -> pd.DataFrame:
    """
    Fallback: scrape from ERCOT public webpage.
    Only works for current day or very recent days.
    """
    url = 'https://www.ercot.com/content/cdr/html/real_time_spp.html'
    
    try:
        tables = pd.read_html(url)
        if tables:
            df = tables[0]
            return df
    except Exception as e:
        print(f"  Scrape failed: {e}")
    
    return pd.DataFrame()


def pull_range(start_date: str, end_date: str, output_dir: str = 'data',
               email: str = None, password: str = None, sub_key: str = None) -> dict:
    """
    Pull a range of dates from the ERCOT API.
    Saves each day as a separate CSV in output_dir.
    """
    email = email or os.environ.get('ERCOT_EMAIL', '')
    password = password or os.environ.get('ERCOT_PASSWORD', '')
    sub_key = sub_key or os.environ.get('ERCOT_KEY', '')
    
    os.makedirs(output_dir, exist_ok=True)
    
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    
    total_days = (end - start).days + 1
    
    print(f"Pulling {total_days} days of ERCOT settlement point prices")
    print(f"  Range: {start_date} to {end_date}")
    print(f"  Output: {output_dir}/")
    print()
    
    # Get API token
    token = ''
    if email and password:
        print("  Authenticating with ERCOT API...")
        token = get_token(email, password)
        if token:
            print("  Token acquired")
        else:
            print("  Token failed, will try scraping")
    else:
        print("  No API credentials, will try scraping")
    
    results = {'success': [], 'failed': [], 'skipped': []}
    
    current = start
    while current <= end:
        date_str = current.strftime('%Y-%m-%d')
        date_fmt = current.strftime('%m_%d_%Y')
        month_day = current.strftime('may%d') if current.month == 5 else current.strftime('%b%d').lower()
        
        output_file = os.path.join(output_dir, f"ercot_{month_day}_{current.year}.csv")
        
        # Skip if already exists
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            if size > 1000:
                print(f"  {date_str}: already exists ({size:,} bytes), skipping")
                results['skipped'].append(date_str)
                current += timedelta(days=1)
                continue
        
        print(f"  {date_str}: pulling...", end=' ', flush=True)
        
        df = pd.DataFrame()
        
        if token:
            df = pull_day_api(date_str, token, sub_key)
        
        if df.empty:
            df = pull_day_scrape(date_str)
        
        if not df.empty and len(df) >= 90:
            df.to_csv(output_file, index=False)
            print(f"saved {len(df)} intervals to {output_file}")
            results['success'].append(date_str)
        elif not df.empty:
            print(f"partial data ({len(df)} intervals)")
            df.to_csv(output_file, index=False)
            results['success'].append(date_str)
        else:
            print(f"no data")
            results['failed'].append(date_str)
        
        time.sleep(1)  # be nice to the API
        current += timedelta(days=1)
    
    print()
    print(f"Done: {len(results['success'])} days pulled, "
          f"{len(results['skipped'])} skipped, "
          f"{len(results['failed'])} failed")
    
    return results


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Pull ERCOT historical price data')
    parser.add_argument('--days', type=int, default=90, help='Number of days to pull (default: 90)')
    parser.add_argument('--from-date', type=str, default=None, dest='from_date', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--to-date', type=str, default=None, dest='to_date', help='End date (YYYY-MM-DD)')
    parser.add_argument('--output', type=str, default='data', help='Output directory')
    parser.add_argument('--email', type=str, default=None, help='ERCOT API email')
    parser.add_argument('--password', type=str, default=None, help='ERCOT account password')
    parser.add_argument('--key', type=str, default=None, help='ERCOT API subscription key')
    
    args = parser.parse_args()
    
    if args.from_date and args.to_date:
        start = args.from_date
        end = args.to_date
    else:
        end_date = datetime.now() - timedelta(days=1)  # yesterday
        start_date = end_date - timedelta(days=args.days - 1)
        start = start_date.strftime('%Y-%m-%d')
        end = end_date.strftime('%Y-%m-%d')
    
    pull_range(start, end, args.output, args.email, args.password, args.key)
