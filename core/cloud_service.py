"""
VoltStream AI — Cloud Service (runs 24/7)
==========================================
This is the always-on brain of VoltStream. It:

1. Pulls live ERCOT prices every 15 minutes
2. Pulls weather forecasts every hour
3. Runs the 6-agent system
4. Logs every decision to a database
5. Serves a live API for the dashboard
6. Sends alerts via email/webhook

DEPLOYMENT OPTIONS (cheapest to most robust):
- PythonAnywhere: $5/month, easiest setup
- Railway: Free under $5/month
- AWS EC2 Free Tier: Free for 12 months
- DigitalOcean: $4/month droplet

TO RUN:
  pip install requests pandas flask apscheduler
  python voltstream_cloud.py
"""

import requests
import pandas as pd
import numpy as np
import json
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from threading import Thread
import time

# Optional imports — install if deploying with web dashboard
try:
    from flask import Flask, jsonify, render_template_string
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False


# ==================================================================
# CONFIGURATION
# ==================================================================

CONFIG = {
    'ercot_scrape_url': 'https://www.ercot.com/content/cdr/html/real_time_spp.html',
    'weather_api_url': 'https://api.open-meteo.com/v1/forecast',
    'database_path': 'voltstream.db',
    'log_file': 'voltstream.log',
    'port': 5000,
    
    # Weather locations
    'weather_locations': {
        'houston': {'lat': 29.76, 'lon': -95.37},
        'dallas': {'lat': 32.78, 'lon': -96.80},
        'west_tx_wind': {'lat': 32.00, 'lon': -101.00},
        'panhandle_wind': {'lat': 35.50, 'lon': -101.50},
        'west_tx_solar': {'lat': 31.50, 'lon': -103.00},
    },
    
    # Battery config (default — overridden per customer)
    'battery': {
        'power_mw': 100,
        'capacity_mwh': 400,
        'soc': 0.50,
        'min_soc': 0.05,
        'max_soc': 0.95,
        'rte': 0.87,
    },
    
    # Alert webhook (Slack, Discord, or email API)
    'alert_webhook': os.environ.get('VOLTSTREAM_WEBHOOK', ''),
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(CONFIG['log_file']),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger('voltstream')


# ==================================================================
# DATABASE — stores all decisions, prices, forecasts
# ==================================================================

class Database:
    """SQLite database for persistent storage."""
    
    def __init__(self, path=None):
        self.path = path or CONFIG['database_path']
        self.init_db()
    
    def init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            hub TEXT NOT NULL,
            rt_price REAL,
            source TEXT DEFAULT 'ercot_scrape',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            location TEXT NOT NULL,
            temperature REAL,
            wind_speed_100m REAL,
            solar_ghi REAL,
            cloud_cover REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            hub TEXT NOT NULL,
            forecast_1h REAL,
            forecast_4h REAL,
            confidence REAL,
            primary_driver TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            action TEXT NOT NULL,
            power_mw REAL,
            reason TEXT,
            current_price REAL,
            forecast_price REAL,
            soc_before REAL,
            soc_after REAL,
            expected_revenue REAL,
            market TEXT,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            actual_price REAL,
            forecasted_price REAL,
            forecast_error REAL,
            action TEXT,
            power_mw REAL,
            revenue REAL,
            cumulative_revenue REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            source TEXT,
            priority TEXT,
            reason TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        conn.close()
        log.info(f"Database initialized: {self.path}")
    
    def insert(self, table, data):
        """Insert a row into a table."""
        conn = sqlite3.connect(self.path)
        c = conn.cursor()
        
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?' for _ in data])
        values = list(data.values())
        
        c.execute(f'INSERT INTO {table} ({columns}) VALUES ({placeholders})', values)
        conn.commit()
        conn.close()
    
    def query(self, sql, params=None):
        """Run a query and return results as list of dicts."""
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        if params:
            c.execute(sql, params)
        else:
            c.execute(sql)
        
        results = [dict(row) for row in c.fetchall()]
        conn.close()
        return results
    
    def get_latest_prices(self, hub='HB_HOUSTON', n=96):
        """Get latest N price records for a hub."""
        return self.query(
            'SELECT * FROM prices WHERE hub = ? ORDER BY timestamp DESC LIMIT ?',
            (hub, n)
        )
    
    def get_latest_decisions(self, n=24):
        """Get latest N dispatch decisions."""
        return self.query(
            'SELECT * FROM decisions ORDER BY timestamp DESC LIMIT ?',
            (n,)
        )
    
    def get_daily_revenue(self, date=None):
        """Get total revenue for a day."""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        results = self.query(
            "SELECT SUM(revenue) as total FROM settlements WHERE timestamp LIKE ?",
            (f'{date}%',)
        )
        return results[0]['total'] if results and results[0]['total'] else 0


# ==================================================================
# DATA COLLECTORS
# ==================================================================

class ERCOTCollector:
    """Pulls real-time prices from ERCOT public page."""
    
    def __init__(self, db: Database):
        self.db = db
        self.last_prices = {}
    
    def pull(self):
        """Pull current ERCOT real-time prices."""
        try:
            tables = pd.read_html(CONFIG['ercot_scrape_url'])
            if not tables:
                log.warning("No tables found on ERCOT page")
                return None
            
            df = tables[0]
            now = datetime.now().isoformat()
            
            # Store all hub prices
            hubs = ['HB_HOUSTON', 'HB_NORTH', 'HB_SOUTH', 'HB_WEST', 'HB_PAN']
            
            for hub in hubs:
                if hub in df.columns:
                    latest_price = float(df[hub].iloc[-1])
                    self.last_prices[hub] = latest_price
                    
                    self.db.insert('prices', {
                        'timestamp': now,
                        'hub': hub,
                        'rt_price': latest_price,
                        'source': 'ercot_scrape',
                    })
            
            houston_price = self.last_prices.get('HB_HOUSTON', 0)
            log.info(f"ERCOT prices pulled — HB_HOUSTON: ${houston_price:.2f}/MWh")
            return self.last_prices
            
        except Exception as e:
            log.error(f"ERCOT pull failed: {e}")
            return None


class WeatherCollector:
    """Pulls weather forecasts from Open-Meteo."""
    
    def __init__(self, db: Database):
        self.db = db
        self.latest = {}
    
    def pull(self):
        """Pull weather for all ERCOT locations."""
        try:
            for name, loc in CONFIG['weather_locations'].items():
                params = {
                    'latitude': loc['lat'],
                    'longitude': loc['lon'],
                    'hourly': 'temperature_2m,wind_speed_100m,shortwave_radiation,cloud_cover',
                    'forecast_hours': 48,
                    'temperature_unit': 'fahrenheit',
                    'wind_speed_unit': 'mph',
                    'timezone': 'America/Chicago',
                }
                
                r = requests.get(CONFIG['weather_api_url'], params=params, timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    hourly = data.get('hourly', {})
                    
                    # Get current values (first index)
                    current = {
                        'temperature': hourly.get('temperature_2m', [75])[0],
                        'wind_speed_100m': hourly.get('wind_speed_100m', [15])[0],
                        'solar_ghi': hourly.get('shortwave_radiation', [0])[0],
                        'cloud_cover': hourly.get('cloud_cover', [50])[0],
                    }
                    
                    self.latest[name] = current
                    
                    self.db.insert('weather', {
                        'timestamp': datetime.now().isoformat(),
                        'location': name,
                        'temperature': current['temperature'],
                        'wind_speed_100m': current['wind_speed_100m'],
                        'solar_ghi': current['solar_ghi'],
                        'cloud_cover': current['cloud_cover'],
                    })
                else:
                    log.warning(f"Weather pull failed for {name}: {r.status_code}")
            
            log.info(f"Weather pulled for {len(self.latest)} locations")
            return self.latest
            
        except Exception as e:
            log.error(f"Weather pull failed: {e}")
            return None


# ==================================================================
# DISPATCH ENGINE (simplified for cloud)
# ==================================================================

class DispatchEngine:
    """Lightweight dispatch engine for cloud deployment."""
    
    def __init__(self, db: Database):
        self.db = db
        self.soc = CONFIG['battery']['soc']
        self.cumulative_revenue = 0
    
    def decide(self, price: float, weather: dict, price_history: list = None) -> dict:
        """Make a dispatch decision."""
        
        power = CONFIG['battery']['power_mw']
        capacity = CONFIG['battery']['capacity_mwh']
        eff = np.sqrt(CONFIG['battery']['rte'])
        
        # Simple forecast based on weather signals
        houston_temp = weather.get('houston', {}).get('temperature', 75)
        wind = weather.get('west_tx_wind', {}).get('wind_speed_100m', 15)
        solar = weather.get('houston', {}).get('solar_ghi', 0)
        
        # Net load proxy
        cdh = max(0, houston_temp - 75)
        demand = 45000 + cdh * 800
        wind_gen = min(1.0, max(0, (wind - 7) / 21)) ** 3 * 30000
        solar_gen = solar / 1000 * 22000
        net_load = demand - wind_gen - solar_gen
        
        # Price forecast (simple model)
        if net_load > 50000:
            forecast_1h = price * 1.15
        elif net_load < 20000:
            forecast_1h = price * 0.7
        else:
            forecast_1h = price * 1.02
        
        # Decision
        decision = {
            'timestamp': datetime.now().isoformat(),
            'action': 'HOLD',
            'power_mw': 0,
            'current_price': price,
            'forecast_price': round(forecast_1h, 2),
            'soc_before': round(self.soc, 4),
            'reason': '',
            'market': 'none',
            'confidence': 0.75,
            'expected_revenue': 0,
        }
        
        if price < 0:
            charge = min(power, (CONFIG['battery']['max_soc'] - self.soc) * capacity / eff)
            self.soc += charge * eff / capacity
            decision.update({
                'action': 'CHARGE', 'power_mw': round(charge, 1),
                'market': 'rt_energy',
                'reason': f'Negative price (${price:.2f}) — paid to charge',
                'expected_revenue': round(abs(price) * charge, 2),
            })
        
        elif price > 100 and self.soc > 0.15:
            discharge = min(power, (self.soc - CONFIG['battery']['min_soc']) * capacity * eff)
            self.soc -= discharge / eff / capacity
            decision.update({
                'action': 'DISCHARGE', 'power_mw': round(discharge, 1),
                'market': 'rt_energy',
                'reason': f'Price spike (${price:.2f}) — max discharge',
                'expected_revenue': round(price * discharge, 2),
            })
        
        elif price < 10 and forecast_1h > price + 15 and self.soc < 0.85:
            intensity = min(1.0, (forecast_1h - price) / 30)
            charge = min(power * intensity, (CONFIG['battery']['max_soc'] - self.soc) * capacity / eff)
            self.soc += charge * eff / capacity
            decision.update({
                'action': 'CHARGE', 'power_mw': round(charge, 1),
                'market': 'rt_energy',
                'reason': f'Low price (${price:.2f}), forecast ${forecast_1h:.2f} in 1h',
                'expected_revenue': round(-price * charge, 2),
            })
        
        elif price > 40 and forecast_1h < price - 10 and self.soc > 0.20:
            intensity = min(1.0, (price - 40) / 30)
            discharge = min(power * intensity, (self.soc - CONFIG['battery']['min_soc']) * capacity * eff)
            self.soc -= discharge / eff / capacity
            decision.update({
                'action': 'DISCHARGE', 'power_mw': round(discharge, 1),
                'market': 'rt_energy',
                'reason': f'High price (${price:.2f}), forecast dropping to ${forecast_1h:.2f}',
                'expected_revenue': round(price * discharge, 2),
            })
        
        elif self.soc > 0.90 and price > 20:
            discharge = power * 0.3
            self.soc -= discharge / eff / capacity
            decision.update({
                'action': 'DISCHARGE', 'power_mw': round(discharge, 1),
                'market': 'rt_energy',
                'reason': f'SOC high ({self.soc*100:.0f}%) — shedding charge',
            })
        
        elif self.soc < 0.15 and price < 25:
            charge = power * 0.3
            self.soc += charge * eff / capacity
            decision.update({
                'action': 'CHARGE', 'power_mw': round(charge, 1),
                'market': 'rt_energy',
                'reason': f'SOC low ({self.soc*100:.0f}%) — building reserve',
            })
        
        else:
            decision['reason'] = f'No signal — price ${price:.2f}, SOC {self.soc*100:.0f}%, net load {net_load:.0f}MW'
        
        self.soc = max(CONFIG['battery']['min_soc'], min(CONFIG['battery']['max_soc'], self.soc))
        decision['soc_after'] = round(self.soc, 4)
        
        # Calculate revenue
        if decision['action'] == 'DISCHARGE':
            rev = price * decision['power_mw'] * 0.25  # 15-min interval
        elif decision['action'] == 'CHARGE':
            rev = -price * decision['power_mw'] * 0.25
        else:
            rev = 0
        self.cumulative_revenue += rev
        
        # Save to database
        self.db.insert('decisions', decision)
        self.db.insert('settlements', {
            'timestamp': decision['timestamp'],
            'actual_price': price,
            'forecasted_price': decision['forecast_price'],
            'forecast_error': round(price - decision['forecast_price'], 2),
            'action': decision['action'],
            'power_mw': decision['power_mw'],
            'revenue': round(rev, 2),
            'cumulative_revenue': round(self.cumulative_revenue, 2),
        })
        
        log.info(f"DISPATCH: {decision['action']} {decision['power_mw']}MW @ ${price:.2f} | SOC: {self.soc*100:.0f}% | Rev: ${rev:.0f} | {decision['reason'][:50]}")
        
        return decision


# ==================================================================
# ALERT SYSTEM
# ==================================================================

class AlertSystem:
    """Sends alerts via webhook (Slack/Discord/email)."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def send(self, priority: str, reason: str, source: str = 'system'):
        """Send an alert."""
        self.db.insert('alerts', {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'priority': priority,
            'reason': reason,
        })
        
        log.warning(f"ALERT [{priority}]: {reason}")
        
        # Send webhook if configured
        webhook = CONFIG['alert_webhook']
        if webhook:
            try:
                requests.post(webhook, json={
                    'text': f'⚡ VoltStream Alert [{priority}]: {reason}',
                }, timeout=5)
            except Exception:
                pass


# ==================================================================
# WEB API — serves live data to the dashboard
# ==================================================================

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head><title>VoltStream AI — Live</title>
<style>
  body { font-family: system-ui; background: #0B0F14; color: #E8ECF1; padding: 20px; }
  .header { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
  .live { width: 8px; height: 8px; border-radius: 50%; background: #22C97A; animation: pulse 2s infinite; }
  @keyframes pulse { 50% { opacity: 0.4; } }
  .grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .card { background: #131920; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; padding: 16px; }
  .label { font-size: 11px; color: #4A5668; text-transform: uppercase; letter-spacing: 1px; }
  .value { font-size: 24px; font-weight: 700; margin-top: 4px; }
  .green { color: #22C97A; } .red { color: #EF4444; } .amber { color: #F59E0B; }
  .log { background: #131920; border-radius: 10px; padding: 16px; font-family: monospace; font-size: 12px; max-height: 400px; overflow-y: auto; }
  .log-entry { padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
  .charge { color: #22C97A; } .discharge { color: #F59E0B; } .hold { color: #4A5668; }
</style>
</head>
<body>
<div class="header">
  <div class="live"></div>
  <span style="font-size:18px;font-weight:700;">Volt<span style="color:#22C97A">Stream</span> AI</span>
  <span style="font-size:11px;color:#4A5668;margin-left:8px;">LIVE OPERATIONS</span>
</div>
<div class="grid" id="metrics"></div>
<h3 style="font-size:13px;color:#4A5668;margin-bottom:10px;">RECENT DECISIONS</h3>
<div class="log" id="log"></div>
<script>
async function refresh() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    document.getElementById('metrics').innerHTML = `
      <div class="card"><div class="label">Latest Price</div><div class="value">$${(d.latest_price||0).toFixed(2)}</div></div>
      <div class="card"><div class="label">SOC</div><div class="value">${((d.soc||0)*100).toFixed(0)}%</div></div>
      <div class="card"><div class="label">Today Revenue</div><div class="value green">$${(d.daily_revenue||0).toLocaleString()}</div></div>
      <div class="card"><div class="label">Decisions Today</div><div class="value">${d.decisions_today||0}</div></div>
    `;
    const log = (d.recent_decisions||[]).map(dec =>
      `<div class="log-entry"><span class="${dec.action?.toLowerCase()}">${dec.action}</span> ${dec.power_mw}MW @ $${(dec.current_price||0).toFixed(2)} | ${dec.reason||''}</div>`
    ).join('');
    document.getElementById('log').innerHTML = log || '<div style="color:#4A5668">Waiting for data...</div>';
  } catch(e) { console.error(e); }
}
refresh();
setInterval(refresh, 15000);
</script>
</body>
</html>
"""


def create_app(db, engine):
    """Create Flask web API."""
    app = Flask(__name__)
    
    @app.route('/')
    def dashboard():
        return render_template_string(DASHBOARD_HTML)
    
    @app.route('/api/status')
    def status():
        decisions = db.get_latest_decisions(20)
        daily_rev = db.get_daily_revenue()
        today = datetime.now().strftime('%Y-%m-%d')
        decisions_today = len(db.query(
            "SELECT id FROM decisions WHERE timestamp LIKE ?", (f'{today}%',)
        ))
        
        return jsonify({
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'latest_price': decisions[0]['current_price'] if decisions else 0,
            'soc': engine.soc,
            'daily_revenue': round(daily_rev, 2),
            'cumulative_revenue': round(engine.cumulative_revenue, 2),
            'decisions_today': decisions_today,
            'recent_decisions': decisions[:10],
        })
    
    @app.route('/api/prices')
    def prices():
        return jsonify(db.get_latest_prices())
    
    @app.route('/api/decisions')
    def decisions():
        return jsonify(db.get_latest_decisions(50))
    
    @app.route('/api/alerts')
    def alerts():
        return jsonify(db.query(
            "SELECT * FROM alerts WHERE status = 'active' ORDER BY timestamp DESC LIMIT 20"
        ))
    
    return app


# ==================================================================
# MAIN SERVICE LOOP
# ==================================================================

class VoltStreamService:
    """The main service that orchestrates everything."""
    
    def __init__(self):
        self.db = Database()
        self.ercot = ERCOTCollector(self.db)
        self.weather = WeatherCollector(self.db)
        self.engine = DispatchEngine(self.db)
        self.alerts = AlertSystem(self.db)
        self.tick_count = 0
    
    def tick(self):
        """Run one cycle: pull data → forecast → decide."""
        self.tick_count += 1
        log.info(f"--- Tick #{self.tick_count} ---")
        
        # Pull ERCOT prices
        prices = self.ercot.pull()
        if not prices:
            log.warning("No prices available, skipping tick")
            return
        
        houston_price = prices.get('HB_HOUSTON', 0)
        
        # Pull weather (less frequently)
        if self.tick_count % 4 == 1:  # every 4th tick (~hourly)
            self.weather.pull()
        
        # Run dispatch
        decision = self.engine.decide(houston_price, self.weather.latest)
        
        # Check for alerts
        if houston_price > 200:
            self.alerts.send('critical', f'Price spike: ${houston_price:.2f}/MWh')
        elif houston_price < -10:
            self.alerts.send('high', f'Deep negative price: ${houston_price:.2f}/MWh')
        
        if self.engine.soc < 0.10:
            self.alerts.send('high', f'SOC critically low: {self.engine.soc*100:.0f}%')
        elif self.engine.soc > 0.95:
            self.alerts.send('medium', f'SOC near max: {self.engine.soc*100:.0f}%')
    
    def run_scheduled(self):
        """Run with APScheduler (production mode)."""
        if not HAS_SCHEDULER:
            log.error("APScheduler not installed. Run: pip install apscheduler")
            return
        
        scheduler = BackgroundScheduler()
        scheduler.add_job(self.tick, 'interval', minutes=15, id='voltstream_tick')
        scheduler.start()
        
        log.info("VoltStream scheduled — running every 15 minutes")
        
        # Run first tick immediately
        self.tick()
        
        # Start web server if Flask is available
        if HAS_FLASK:
            app = create_app(self.db, self.engine)
            log.info(f"Dashboard available at http://localhost:{CONFIG['port']}")
            app.run(host='0.0.0.0', port=CONFIG['port'], debug=False)
        else:
            # Keep alive without Flask
            try:
                while True:
                    time.sleep(60)
            except KeyboardInterrupt:
                scheduler.shutdown()
    
    def run_simple(self):
        """Run with simple loop (no dependencies needed)."""
        log.info("VoltStream running in simple mode (Ctrl+C to stop)")
        
        # Start web server in background if available
        if HAS_FLASK:
            app = create_app(self.db, self.engine)
            thread = Thread(target=lambda: app.run(host='0.0.0.0', port=CONFIG['port'], debug=False), daemon=True)
            thread.start()
            log.info(f"Dashboard at http://localhost:{CONFIG['port']}")
        
        try:
            while True:
                self.tick()
                log.info("Sleeping 15 minutes until next tick...")
                time.sleep(900)  # 15 minutes
        except KeyboardInterrupt:
            log.info("VoltStream stopped.")


# ==================================================================
# ENTRY POINT
# ==================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("⚡ VoltStream AI — Cloud Service")
    print("=" * 60)
    print(f"  Database: {CONFIG['database_path']}")
    print(f"  Log file: {CONFIG['log_file']}")
    print(f"  Dashboard: http://localhost:{CONFIG['port']}")
    print()
    
    service = VoltStreamService()
    
    if HAS_SCHEDULER:
        print("  Mode: Scheduled (APScheduler)")
        print("  Interval: Every 15 minutes")
        service.run_scheduled()
    else:
        print("  Mode: Simple loop")
        print("  Interval: Every 15 minutes")
        print("  (Install apscheduler for production: pip install apscheduler)")
        service.run_simple()
