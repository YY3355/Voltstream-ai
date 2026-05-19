"""
VoltStream AI — Observability System
======================================
The brain runs 24/7. You need to know:
- Is it healthy right now?
- What did it do while you were sleeping?
- When did something go wrong and why?
- Is performance getting better or worse over time?

COMPONENTS:
1. Structured Logger — every tick as searchable JSON
2. Metrics Tracker — accuracy, revenue, latency over time
3. Alert System — pings you when something is wrong
4. Error Tracker — captures exceptions with full context
5. Health Monitor — is the brain alive and performing?
"""

import json
import os
import time
import logging
import traceback
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict
import numpy as np


# ==================================================================
# STRUCTURED LOGGER
# ==================================================================

class StructuredLogger:
    """
    Every tick produces one structured JSON log line.
    Searchable. Filterable. Parseable by any log tool.
    
    Format:
    {"ts":"2026-05-18T20:15:00","tick":42,"price":67.75,"action":"DISCHARGE",
     "confidence":0.85,"modules_voted":5,"latency_ms":312,"soc":0.65,...}
    """
    
    def __init__(self, log_path: str = 'logs/voltstream.jsonl',
                 console: bool = True):
        self.log_path = log_path
        self.console = console
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else '.', exist_ok=True)
        
        # Standard Python logger for console
        self.logger = logging.getLogger('voltstream')
        if console and not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def log_tick(self, tick_data: dict):
        """Log a complete tick as structured JSON."""
        entry = {
            'type': 'tick',
            'ts': datetime.now().isoformat(),
            **tick_data,
        }
        
        self._write_json(entry)
        
        if self.console:
            action = tick_data.get('action', '?')
            price = tick_data.get('price', 0)
            conf = tick_data.get('confidence', 0)
            latency = tick_data.get('latency_ms', 0)
            self.logger.info(
                f"Tick {tick_data.get('tick', '?')} | ${price:.2f} | {action} "
                f"| conf={conf:.0%} | {latency:.0f}ms"
            )
    
    def log_event(self, event_type: str, message: str, data: dict = None):
        """Log a system event."""
        entry = {
            'type': 'event',
            'ts': datetime.now().isoformat(),
            'event': event_type,
            'message': message,
            **(data or {}),
        }
        self._write_json(entry)
        
        if self.console:
            self.logger.info(f"[{event_type}] {message}")
    
    def log_error(self, error: Exception, context: dict = None):
        """Log an error with full context."""
        entry = {
            'type': 'error',
            'ts': datetime.now().isoformat(),
            'error_class': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'context': context or {},
        }
        self._write_json(entry)
        
        if self.console:
            self.logger.error(f"ERROR: {type(error).__name__}: {error}")
    
    def log_module(self, module_name: str, action: str, 
                   latency_ms: float, success: bool, details: dict = None):
        """Log individual module execution."""
        entry = {
            'type': 'module',
            'ts': datetime.now().isoformat(),
            'module': module_name,
            'action': action,
            'latency_ms': round(latency_ms, 1),
            'success': success,
            **(details or {}),
        }
        self._write_json(entry)
    
    def _write_json(self, entry: dict):
        """Write one JSON line to the log file."""
        try:
            with open(self.log_path, 'a') as f:
                f.write(json.dumps(entry, default=str) + '\n')
        except Exception:
            pass  # logging should never crash the system
    
    def query(self, log_type: str = None, last_n: int = 50,
              since: str = None) -> List[dict]:
        """Query the log file. Simple but works."""
        if not os.path.exists(self.log_path):
            return []
        
        entries = []
        try:
            with open(self.log_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        if log_type and entry.get('type') != log_type:
                            continue
                        if since and entry.get('ts', '') < since:
                            continue
                        entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception:
            pass
        
        return entries[-last_n:]


# ==================================================================
# METRICS TRACKER
# ==================================================================

class MetricsTracker:
    """
    Tracks numerical metrics over time.
    Revenue, accuracy, latency, error rate, etc.
    """
    
    def __init__(self):
        self.metrics = defaultdict(list)  # metric_name -> [(timestamp, value)]
        self.counters = defaultdict(int)
        self.gauges = {}
    
    def record(self, name: str, value: float):
        """Record a time-series metric."""
        self.metrics[name].append((datetime.now().isoformat(), value))
        
        # Keep bounded
        if len(self.metrics[name]) > 10000:
            self.metrics[name] = self.metrics[name][-10000:]
    
    def increment(self, name: str, amount: int = 1):
        """Increment a counter."""
        self.counters[name] += amount
    
    def set_gauge(self, name: str, value: float):
        """Set a gauge (current value)."""
        self.gauges[name] = (datetime.now().isoformat(), value)
    
    def get_recent(self, name: str, last_n: int = 100) -> List[tuple]:
        """Get recent values for a metric."""
        return self.metrics.get(name, [])[-last_n:]
    
    def get_summary(self, name: str, window: int = 100) -> dict:
        """Get summary statistics for a metric."""
        values = [v for _, v in self.metrics.get(name, [])[-window:]]
        if not values:
            return {'count': 0}
        
        return {
            'count': len(values),
            'mean': round(np.mean(values), 4),
            'std': round(np.std(values), 4),
            'min': round(min(values), 4),
            'max': round(max(values), 4),
            'latest': round(values[-1], 4),
            'trend': 'up' if len(values) >= 10 and np.mean(values[-5:]) > np.mean(values[-10:-5]) else 'down' if len(values) >= 10 and np.mean(values[-5:]) < np.mean(values[-10:-5]) else 'stable',
        }
    
    def get_dashboard(self) -> dict:
        """Get all metrics for dashboard display."""
        dashboard = {
            'gauges': {k: {'value': v[1], 'updated': v[0]} for k, v in self.gauges.items()},
            'counters': dict(self.counters),
            'time_series': {},
        }
        
        for name in self.metrics:
            dashboard['time_series'][name] = self.get_summary(name)
        
        return dashboard


# ==================================================================
# ALERT SYSTEM
# ==================================================================

class AlertSystem:
    """
    Sends alerts when something needs attention.
    
    Supports: webhook (Slack/Discord), console, log file.
    In production: add PagerDuty, email, SMS.
    """
    
    # Alert severity levels
    INFO = 'info'
    WARNING = 'warning'
    CRITICAL = 'critical'
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url or os.environ.get('VOLTSTREAM_WEBHOOK', '')
        self.alert_history = []
        self.suppressed = {}  # alert_key -> suppressed_until
        self.suppress_minutes = 30  # don't repeat same alert for 30 min
    
    def alert(self, severity: str, title: str, message: str,
              data: dict = None):
        """Send an alert."""
        alert_key = f"{severity}:{title}"
        
        # Check suppression
        if alert_key in self.suppressed:
            if datetime.now() < self.suppressed[alert_key]:
                return  # suppressed, skip
        
        alert = {
            'severity': severity,
            'title': title,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'data': data or {},
        }
        
        self.alert_history.append(alert)
        
        # Suppress repeats
        self.suppressed[alert_key] = datetime.now() + timedelta(minutes=self.suppress_minutes)
        
        # Send to webhook
        if self.webhook_url and severity in [self.WARNING, self.CRITICAL]:
            self._send_webhook(alert)
        
        # Always log
        level = {'info': 'INFO', 'warning': 'WARNING', 'critical': 'CRITICAL'}
        print(f"  ALERT [{level.get(severity, 'INFO')}] {title}: {message}")
    
    def _send_webhook(self, alert: dict):
        """Send alert to webhook (Slack/Discord compatible)."""
        try:
            icon = {'info': 'information_source', 'warning': 'warning', 'critical': 'rotating_light'}
            payload = {
                'text': f":{icon.get(alert['severity'], 'bell')}: *{alert['title']}*\n{alert['message']}",
            }
            requests.post(self.webhook_url, json=payload, timeout=5)
        except Exception:
            pass  # alerting should never crash the system
    
    def get_recent(self, severity: str = None, last_n: int = 20) -> List[dict]:
        """Get recent alerts."""
        alerts = self.alert_history
        if severity:
            alerts = [a for a in alerts if a['severity'] == severity]
        return alerts[-last_n:]


# ==================================================================
# ERROR TRACKER
# ==================================================================

class ErrorTracker:
    """
    Captures every exception with full context so you can
    reproduce the exact conditions that caused the failure.
    """
    
    def __init__(self):
        self.errors = []
        self.error_counts = defaultdict(int)
        self.module_errors = defaultdict(int)
    
    def capture(self, error: Exception, module: str = 'unknown',
                tick: int = 0, price: float = 0, soc: float = 0,
                extra: dict = None):
        """Capture an error with full context."""
        error_entry = {
            'timestamp': datetime.now().isoformat(),
            'error_class': type(error).__name__,
            'error_message': str(error),
            'traceback': traceback.format_exc(),
            'module': module,
            'tick': tick,
            'price': price,
            'soc': soc,
            'extra': extra or {},
        }
        
        self.errors.append(error_entry)
        self.error_counts[type(error).__name__] += 1
        self.module_errors[module] += 1
        
        # Keep bounded
        if len(self.errors) > 1000:
            self.errors = self.errors[-1000:]
    
    def get_summary(self) -> dict:
        """Error summary for dashboard."""
        recent = self.errors[-50:] if self.errors else []
        
        return {
            'total_errors': sum(self.error_counts.values()),
            'unique_errors': len(self.error_counts),
            'by_type': dict(self.error_counts),
            'by_module': dict(self.module_errors),
            'recent': recent[-5:],
            'most_common': max(self.error_counts.items(), key=lambda x: x[1])[0] if self.error_counts else 'none',
            'most_failing_module': max(self.module_errors.items(), key=lambda x: x[1])[0] if self.module_errors else 'none',
        }


# ==================================================================
# HEALTH MONITOR
# ==================================================================

class HealthMonitor:
    """
    Monitors the overall health of the brain.
    Checks all systems every tick and raises alerts
    when something is degraded.
    """
    
    def __init__(self, alerts: AlertSystem, metrics: MetricsTracker,
                 errors: ErrorTracker):
        self.alerts = alerts
        self.metrics = metrics
        self.errors = errors
        self.last_tick_time = None
        self.consecutive_failures = 0
        self.max_tick_latency_ms = 5000
        self.max_consecutive_failures = 3
        self.data_stale_minutes = 10
    
    def check(self, tick: int, tick_data: dict) -> dict:
        """Run all health checks after a tick."""
        health = {
            'status': 'healthy',
            'checks': {},
            'timestamp': datetime.now().isoformat(),
        }
        
        # Check 1: Tick latency
        latency = tick_data.get('latency_ms', 0)
        if latency > self.max_tick_latency_ms:
            health['checks']['latency'] = 'degraded'
            self.alerts.alert(
                AlertSystem.WARNING,
                'High tick latency',
                f'Tick {tick} took {latency:.0f}ms (threshold: {self.max_tick_latency_ms}ms)',
            )
        else:
            health['checks']['latency'] = 'ok'
        
        # Check 2: Data freshness
        data_source = tick_data.get('price_source', 'unknown')
        if data_source == 'synthetic':
            health['checks']['data_feed'] = 'degraded'
            self.alerts.alert(
                AlertSystem.WARNING,
                'Using synthetic data',
                'ERCOT live feed unavailable. Running on synthetic prices.',
            )
        else:
            health['checks']['data_feed'] = 'ok'
        
        # Check 3: Module failures
        modules_failed = tick_data.get('modules_failed', [])
        if modules_failed:
            health['checks']['modules'] = 'degraded'
            if len(modules_failed) >= 3:
                self.alerts.alert(
                    AlertSystem.CRITICAL,
                    'Multiple modules failing',
                    f'{len(modules_failed)} modules failed: {", ".join(modules_failed)}',
                )
        else:
            health['checks']['modules'] = 'ok'
        
        # Check 4: Decision quality
        confidence = tick_data.get('confidence', 0)
        if confidence < 0.3:
            health['checks']['decision_quality'] = 'degraded'
            self.metrics.increment('low_confidence_ticks')
        else:
            health['checks']['decision_quality'] = 'ok'
        
        # Check 5: SOC bounds
        soc = tick_data.get('soc', 0.5)
        if soc < 0.08 or soc > 0.97:
            health['checks']['soc'] = 'warning'
            self.alerts.alert(
                AlertSystem.WARNING,
                'SOC near limits',
                f'Battery SOC at {soc*100:.1f}%. Risk of hitting hard limits.',
            )
        else:
            health['checks']['soc'] = 'ok'
        
        # Check 6: Error rate
        error_summary = self.errors.get_summary()
        recent_errors = len([e for e in self.errors.errors[-20:] 
                           if e.get('tick', 0) >= tick - 10])
        if recent_errors > 5:
            health['checks']['error_rate'] = 'critical'
            self.alerts.alert(
                AlertSystem.CRITICAL,
                'High error rate',
                f'{recent_errors} errors in last 10 ticks',
            )
        elif recent_errors > 2:
            health['checks']['error_rate'] = 'degraded'
        else:
            health['checks']['error_rate'] = 'ok'
        
        # Check 7: Tick frequency
        now = datetime.now()
        if self.last_tick_time:
            gap = (now - self.last_tick_time).total_seconds()
            if gap > 600:  # more than 10 minutes between ticks
                health['checks']['tick_frequency'] = 'degraded'
                self.alerts.alert(
                    AlertSystem.WARNING,
                    'Tick gap detected',
                    f'{gap:.0f}s since last tick (expected 300s)',
                )
            else:
                health['checks']['tick_frequency'] = 'ok'
        self.last_tick_time = now
        
        # Overall status
        statuses = list(health['checks'].values())
        if 'critical' in statuses:
            health['status'] = 'critical'
        elif 'degraded' in statuses:
            health['status'] = 'degraded'
        else:
            health['status'] = 'healthy'
        
        # Record health metric
        health_score = statuses.count('ok') / max(len(statuses), 1)
        self.metrics.record('health_score', health_score)
        self.metrics.set_gauge('system_status', 1.0 if health['status'] == 'healthy' else 0.5 if health['status'] == 'degraded' else 0.0)
        
        return health


# ==================================================================
# OBSERVABILITY (ties everything together)
# ==================================================================

class Observability:
    """
    One object to rule them all.
    Pass this to the orchestrator and everything gets tracked.
    """
    
    def __init__(self, log_path: str = 'logs/voltstream.jsonl',
                 webhook_url: str = None):
        self.logger = StructuredLogger(log_path)
        self.metrics = MetricsTracker()
        self.alerts = AlertSystem(webhook_url)
        self.errors = ErrorTracker()
        self.health = HealthMonitor(self.alerts, self.metrics, self.errors)
        self.start_time = datetime.now()
    
    def on_tick_start(self, tick: int):
        """Called at the start of every tick."""
        self.metrics.increment('total_ticks')
        self.metrics.set_gauge('current_tick', tick)
    
    def on_tick_complete(self, tick: int, tick_data: dict):
        """Called after every tick completes."""
        # Log the tick
        self.logger.log_tick(tick_data)
        
        # Record metrics
        self.metrics.record('tick_latency_ms', tick_data.get('latency_ms', 0))
        self.metrics.record('price', tick_data.get('price', 0))
        self.metrics.record('soc', tick_data.get('soc', 0))
        self.metrics.record('confidence', tick_data.get('confidence', 0))
        self.metrics.set_gauge('last_price', tick_data.get('price', 0))
        self.metrics.set_gauge('last_action', tick_data.get('action', 'HOLD'))
        self.metrics.set_gauge('last_soc', tick_data.get('soc', 0))
        
        if tick_data.get('revenue'):
            self.metrics.record('tick_revenue', tick_data['revenue'])
            self.metrics.increment('total_revenue_cents', int(tick_data['revenue'] * 100))
        
        # Run health checks
        health = self.health.check(tick, tick_data)
        
        return health
    
    def on_module_run(self, module: str, latency_ms: float, success: bool,
                      details: dict = None):
        """Called after each module runs."""
        self.logger.log_module(module, 'run', latency_ms, success, details)
        self.metrics.record(f'module_{module}_latency', latency_ms)
        
        if success:
            self.metrics.increment(f'module_{module}_success')
        else:
            self.metrics.increment(f'module_{module}_failure')
    
    def on_error(self, error: Exception, module: str = 'unknown',
                 tick: int = 0, context: dict = None):
        """Called when any error occurs."""
        self.errors.capture(error, module, tick, extra=context)
        self.logger.log_error(error, {'module': module, 'tick': tick, **(context or {})})
        self.metrics.increment('total_errors')
    
    def on_event(self, event_type: str, message: str, data: dict = None):
        """Log a significant event."""
        self.logger.log_event(event_type, message, data)
    
    def get_status(self) -> dict:
        """Get complete system status."""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        return {
            'uptime_seconds': round(uptime),
            'uptime_human': f"{uptime/3600:.1f} hours",
            'dashboard': self.metrics.get_dashboard(),
            'errors': self.errors.get_summary(),
            'recent_alerts': self.alerts.get_recent(last_n=10),
            'key_metrics': {
                'tick_latency': self.metrics.get_summary('tick_latency_ms'),
                'price': self.metrics.get_summary('price'),
                'confidence': self.metrics.get_summary('confidence'),
                'health': self.metrics.get_summary('health_score'),
            },
        }


def demo():
    """Demonstrate the observability system."""
    
    print("=" * 70)
    print("VoltStream AI — Observability System")
    print("=" * 70)
    print()
    print("  Structured logging + Metrics + Alerting + Error tracking")
    print("  Everything the brain does is tracked and searchable.")
    print()
    
    obs = Observability(log_path='/tmp/voltstream_demo.jsonl')
    np.random.seed(42)
    
    print("  Simulating 50 ticks with various conditions...\n")
    
    for tick in range(50):
        obs.on_tick_start(tick)
        start = time.time()
        
        hour = (tick * 5 // 60) % 24
        price = 30 + np.random.normal(0, 15)
        if np.random.random() < 0.05:
            price = 150 + np.random.exponential(50)
        price = max(-5, price)
        
        soc = 0.5 + np.random.normal(0, 0.15)
        soc = max(0.05, min(0.95, soc))
        
        # Simulate module runs
        modules_failed = []
        for module in ['ml_forecast', 'causal', 'planning', 'game_theory', 'rag']:
            mod_start = time.time()
            success = np.random.random() > 0.1  # 90% success rate
            
            if not success:
                modules_failed.append(module)
                obs.on_error(
                    RuntimeError(f"{module} failed to produce output"),
                    module=module, tick=tick,
                    context={'price': price, 'soc': soc},
                )
            
            obs.on_module_run(module, (time.time() - mod_start) * 1000 + np.random.uniform(10, 100), success)
        
        # Simulate decision
        action = 'DISCHARGE' if price > 40 else 'CHARGE' if price < 15 else 'HOLD'
        confidence = 0.8 if abs(price - 30) > 20 else 0.5
        
        latency = (time.time() - start) * 1000 + np.random.uniform(50, 300)
        
        tick_data = {
            'tick': tick,
            'price': round(price, 2),
            'action': action,
            'confidence': round(confidence, 2),
            'soc': round(soc, 3),
            'hour': hour,
            'latency_ms': round(latency, 1),
            'modules_voted': 5 - len(modules_failed),
            'modules_failed': modules_failed,
            'price_source': 'synthetic' if np.random.random() < 0.1 else 'ercot_live',
        }
        
        health = obs.on_tick_complete(tick, tick_data)
        
        # Log some events
        if price > 100:
            obs.on_event('price_spike', f'Price spiked to ${price:.0f}', {'price': price})
        
        if tick == 25:
            obs.on_event('data_feed_recovery', 'ERCOT live feed restored after outage')
    
    # Show results
    status = obs.get_status()
    
    print(f"\n  {'='*58}")
    print(f"  SYSTEM STATUS")
    print(f"  {'='*58}")
    print(f"  Uptime: {status['uptime_human']}")
    
    print(f"\n  KEY METRICS:")
    for name, summary in status['key_metrics'].items():
        if summary.get('count', 0) > 0:
            print(f"    {name:<20} avg={summary['mean']:.1f}  min={summary['min']:.1f}  "
                  f"max={summary['max']:.1f}  trend={summary['trend']}")
    
    print(f"\n  COUNTERS:")
    for name, value in sorted(status['dashboard']['counters'].items()):
        print(f"    {name:<30} {value}")
    
    print(f"\n  ERRORS:")
    err = status['errors']
    print(f"    Total: {err['total_errors']}")
    print(f"    Unique types: {err['unique_errors']}")
    if err['by_module']:
        print(f"    By module: {dict(err['by_module'])}")
    
    print(f"\n  RECENT ALERTS:")
    for alert in status['recent_alerts'][-5:]:
        print(f"    [{alert['severity'].upper()}] {alert['title']}: {alert['message']}")
    
    # Show what the log file looks like
    recent_logs = obs.logger.query(log_type='tick', last_n=3)
    if recent_logs:
        print(f"\n  SAMPLE LOG ENTRIES (structured JSON):")
        for entry in recent_logs:
            compact = {k: v for k, v in entry.items() if k in ['tick', 'price', 'action', 'confidence', 'latency_ms', 'soc']}
            print(f"    {json.dumps(compact)}")
    
    # Cleanup
    try:
        os.remove('/tmp/voltstream_demo.jsonl')
    except Exception:
        pass
    
    print(f"\n{'='*70}")
    print("OBSERVABILITY GIVES YOU:")
    print(f"{'='*70}")
    print()
    print("  1. STRUCTURED LOGS: Every tick as searchable JSON.")
    print("     grep for price spikes, failed modules, low confidence.")
    print()
    print("  2. METRICS: Track latency, accuracy, revenue over time.")
    print("     See trends. Spot degradation before it costs money.")
    print()
    print("  3. ALERTS: Phone pings when modules fail, data goes stale,")
    print("     or the brain makes low-confidence decisions.")
    print()
    print("  4. ERROR TRACKING: Every exception has full context.")
    print("     Price, SOC, tick, module. Reproduce any failure.")
    print()
    print("  5. HEALTH MONITOR: One status check tells you if the brain")
    print("     is healthy, degraded, or critical. At a glance.")
    print()
    print("  This is what lets you sleep while the brain trades.")


if __name__ == '__main__':
    demo()
