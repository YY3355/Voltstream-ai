import requests, csv, time, os
from datetime import datetime, timedelta

# Auth
r = requests.post('https://ercotb2c.b2clogin.com/ercotb2c.onmicrosoft.com/B2C_1_PUBAPI-ROPC-FLOW/oauth2/v2.0/token', data={
    'grant_type': 'password', 'username': 'mikeoc1525@gmail.com', 'password': 'Tom2mike',
    'scope': 'openid fec253ea-0d06-4272-a5e6-b478baeecd70 offline_access',
    'client_id': 'fec253ea-0d06-4272-a5e6-b478baeecd70', 'response_type': 'id_token',
}, timeout=30)
token = r.json()['access_token']
print('Token acquired')

headers = {
    'Authorization': f'Bearer {token}',
    'Ocp-Apim-Subscription-Key': '70a3d89042904356859de81c24f07cc1',
}
hubs = ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'HB_BUSAVG', 'HB_HUBAVG', 'HB_PAN']
url = 'https://api.ercot.com/api/public-reports/np6-905-cd/spp_node_zone_hub'

start = datetime(2025, 5, 21)
end = datetime(2026, 5, 19)
current = start
total_saved = 0

while current <= end:
    date_str = current.strftime('%Y-%m-%d')
    fname = f'data/ercot_api_{date_str}.csv'
    
    if os.path.exists(fname) and os.path.getsize(fname) > 1000:
        current += timedelta(days=1)
        continue
    
    day_data = {}
    for hub in hubs:
        params = {'deliveryDateFrom': date_str, 'deliveryDateTo': date_str,
                  'settlementPoint': hub, 'size': 100}
        try:
            r = requests.get(url, params=params, headers=headers, timeout=30)
            if r.status_code == 200:
                records = r.json().get('data', [])
                for rec in records:
                    # rec = [date, hour, interval, point, type, price, dst]
                    hour = rec[1]
                    interval = rec[2]
                    price = rec[5]
                    minute = (interval - 1) * 15
                    key = (hour, minute)
                    if key not in day_data:
                        day_data[key] = {'hour': hour, 'minute': minute}
                    day_data[key][hub] = price
            elif r.status_code == 429:
                print(f'  Rate limited, waiting 30s...')
                time.sleep(30)
            time.sleep(0.3)
        except Exception as e:
            print(f'  {hub}: {e}')
    
    if len(day_data) >= 90:
        rows = sorted(day_data.values(), key=lambda x: (x['hour'], x['minute']))
        with open(fname, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['hour', 'minute'] + hubs)
            w.writeheader()
            w.writerows(rows)
        total_saved += 1
        print(f'{date_str}: {len(rows)} intervals saved ({total_saved} days total)')
    elif day_data:
        print(f'{date_str}: partial ({len(day_data)} intervals)')
    else:
        print(f'{date_str}: no data')
    
    current += timedelta(days=1)

print(f'\nDONE: {total_saved} days saved')
