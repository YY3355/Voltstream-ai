"""
VoltStream AI — Autonomous Market Notice Reader
=================================================
ERCOT publishes dozens of market notices daily:
- Generator outages (planned and forced)
- Transmission constraints
- Protocol changes
- Weather advisories
- Conservation appeals
- Emergency operations

ML models can't read these. Claude can.

This agent:
1. Pulls ERCOT market notices automatically
2. Sends each to Claude for analysis
3. Determines if it impacts battery dispatch
4. Adjusts the dispatch strategy accordingly

Example:
  Notice: "Unit X (500MW gas plant) forced outage effective immediately"
  Claude analysis: "Loss of 500MW baseload in North zone. Expect prices
  to increase $5-15/MWh in HB_NORTH for next 24-48 hours."
  Action: Hold charge for discharge during expected price increase.
"""

import requests
import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

log = logging.getLogger('voltstream.notices')


# Sample ERCOT notices for demo (real ones pulled from ERCOT in production)
SAMPLE_NOTICES = [
    {
        'id': 'N20260502-001',
        'timestamp': '2026-05-02T08:15:00',
        'type': 'FORCED_OUTAGE',
        'title': 'Forced Outage: Limestone Unit 2 (900MW coal)',
        'body': 'Limestone Electric Generating Station Unit 2 has experienced a forced '
                'outage due to boiler tube leak. Unit capacity: 900MW. Expected return: '
                '5-7 days. Location: Jewett, TX (Load Zone North).',
    },
    {
        'id': 'N20260502-002',
        'timestamp': '2026-05-02T10:30:00',
        'type': 'TRANSMISSION_CONSTRAINT',
        'title': 'Transmission Constraint: West to Houston 345kV',
        'body': 'Due to scheduled maintenance on the West-Houston 345kV transmission '
                'corridor, transfer capability reduced by 2,000MW from 05/03 0600 to '
                '05/05 1800. Expect increased congestion and price separation between '
                'HB_WEST and HB_HOUSTON during this period.',
    },
    {
        'id': 'N20260502-003',
        'timestamp': '2026-05-02T14:00:00',
        'type': 'WEATHER_ADVISORY',
        'title': 'Hot Weather Advisory: Extreme Heat Expected',
        'body': 'ERCOT is issuing a Weather Watch for May 5-7 due to forecast '
                'temperatures exceeding 100°F across Central and North Texas. '
                'Peak demand forecast: 78,000MW. All generation resources should '
                'ensure maximum availability. Conservation appeal may be issued.',
    },
    {
        'id': 'N20260502-004',
        'timestamp': '2026-05-02T16:45:00',
        'type': 'PROTOCOL_CHANGE',
        'title': 'DRRS Procurement Increase Effective May 10',
        'body': 'Effective May 10, 2026, ERCOT will increase DRRS procurement from '
                '3,000MW to 4,500MW during summer peak hours (14:00-20:00 CDT). '
                'Resources qualified for DRRS should update their offers accordingly. '
                'This change is in response to increasing grid reliability requirements.',
    },
    {
        'id': 'N20260502-005',
        'timestamp': '2026-05-02T18:00:00',
        'type': 'WIND_FORECAST',
        'title': 'Significant Wind Ramp Expected Overnight',
        'body': 'Meteorological data indicates a significant wind ramp event beginning '
                'approximately 2200 CDT tonight. West Texas wind generation expected to '
                'increase from 8,000MW to 25,000MW by 0400 CDT. Real-time prices may '
                'be significantly depressed during this period.',
    },
]


class MarketNoticeReader:
    """
    Reads and interprets ERCOT market notices using Claude.
    Translates unstructured text into dispatch-relevant signals.
    """
    
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.enabled = bool(self.api_key)
        self.analyzed_notices = []
        self.active_impacts = []
    
    def _call_claude(self, system: str, prompt: str) -> str:
        """Call Claude API for notice analysis."""
        if not self.enabled:
            return ""
        
        try:
            r = requests.post(
                self.CLAUDE_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=15,
            )
            
            if r.status_code == 200:
                return r.json()['content'][0]['text']
            return ""
        except Exception as e:
            log.error(f"Claude API error: {e}")
            return ""
    
    def analyze_notice(self, notice: dict) -> dict:
        """
        Have Claude analyze a market notice and determine
        its impact on battery dispatch.
        """
        system = """You are VoltStream AI's market intelligence analyst.
Analyze ERCOT market notices and determine their impact on battery
storage dispatch. Respond ONLY in valid JSON with these fields:
- impacts_battery: boolean
- impact_severity: "none", "low", "medium", "high", "critical"
- affected_zones: list of affected ERCOT zones/hubs
- price_impact_direction: "up", "down", or "neutral"
- price_impact_estimate: estimated $/MWh change
- duration_hours: how long the impact will last
- dispatch_action: what the battery should do
- reasoning: 2-3 sentence explanation
- opportunity: any revenue opportunity this creates"""
        
        prompt = f"""Analyze this ERCOT market notice:

Type: {notice.get('type', 'UNKNOWN')}
Title: {notice.get('title', '')}
Body: {notice.get('body', '')}
Timestamp: {notice.get('timestamp', '')}

How does this affect a 100MW/400MWh battery storage asset in ERCOT?"""
        
        response = self._call_claude(system, prompt)
        
        if response:
            try:
                clean = response.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1].rsplit('```', 1)[0]
                analysis = json.loads(clean)
            except json.JSONDecodeError:
                analysis = self._rule_based_analysis(notice)
        else:
            analysis = self._rule_based_analysis(notice)
        
        result = {
            'notice_id': notice.get('id', ''),
            'notice_type': notice.get('type', ''),
            'title': notice.get('title', ''),
            'timestamp': notice.get('timestamp', ''),
            'analysis': analysis,
            'analyzed_at': datetime.now().isoformat(),
        }
        
        self.analyzed_notices.append(result)
        
        if analysis.get('impacts_battery', False):
            self.active_impacts.append(result)
        
        return result
    
    def _rule_based_analysis(self, notice: dict) -> dict:
        """
        Fallback rule-based analysis when Claude is unavailable.
        Catches the most common notice types.
        """
        notice_type = notice.get('type', '')
        body = notice.get('body', '').lower()
        
        if notice_type == 'FORCED_OUTAGE':
            # Extract MW if possible
            mw = 0
            for word in body.split():
                if 'mw' in word.lower():
                    try:
                        mw = int(''.join(c for c in body.split('mw')[0].split()[-1] if c.isdigit()))
                    except ValueError:
                        pass
            
            severity = 'high' if mw > 500 else 'medium' if mw > 200 else 'low'
            
            return {
                'impacts_battery': True,
                'impact_severity': severity,
                'affected_zones': ['system_wide'],
                'price_impact_direction': 'up',
                'price_impact_estimate': min(30, mw * 0.02),
                'duration_hours': 72,
                'dispatch_action': 'Hold charge for expected price increase. Discharge during peak hours.',
                'reasoning': f'{mw}MW generation loss reduces supply, likely increasing prices. '
                            f'Battery should preserve charge for higher-value discharge opportunities.',
                'opportunity': f'Potential ${mw * 0.02:.0f}/MWh price uplift for next 3-5 days.',
            }
        
        elif notice_type == 'TRANSMISSION_CONSTRAINT':
            return {
                'impacts_battery': True,
                'impact_severity': 'medium',
                'affected_zones': ['HB_WEST', 'HB_HOUSTON'],
                'price_impact_direction': 'up',
                'price_impact_estimate': 15,
                'duration_hours': 48,
                'dispatch_action': 'Expect price separation between West and Houston. '
                                  'If battery is in West TX, discharge during constraint. '
                                  'If in Houston, prices may decrease — charge opportunity.',
                'reasoning': 'Transmission constraint creates congestion and price separation. '
                            'West TX prices increase, Houston may decrease.',
                'opportunity': 'Congestion-driven spread between zones creates arbitrage opportunity.',
            }
        
        elif notice_type == 'WEATHER_ADVISORY':
            return {
                'impacts_battery': True,
                'impact_severity': 'high',
                'affected_zones': ['system_wide'],
                'price_impact_direction': 'up',
                'price_impact_estimate': 25,
                'duration_hours': 72,
                'dispatch_action': 'CRITICAL: Preserve maximum SOC for discharge during heat event. '
                                  'Charge overnight, discharge during afternoon peak (14:00-20:00). '
                                  'Price spikes of $200+ possible.',
                'reasoning': 'Extreme heat drives massive cooling demand. '
                            'Peak demand approaching system capacity means scarcity pricing likely.',
                'opportunity': 'Heat events produce the highest-revenue hours of the year. '
                              'A well-positioned battery can earn $50K+ in a single afternoon.',
            }
        
        elif notice_type == 'PROTOCOL_CHANGE':
            if 'drrs' in body.lower():
                return {
                    'impacts_battery': True,
                    'impact_severity': 'medium',
                    'affected_zones': ['system_wide'],
                    'price_impact_direction': 'neutral',
                    'price_impact_estimate': 0,
                    'duration_hours': 0,
                    'dispatch_action': 'Increase DRRS offer quantity. Higher procurement = higher clearing prices.',
                    'reasoning': 'DRRS procurement increase means more revenue for qualified batteries.',
                    'opportunity': 'DRRS revenue opportunity increases by ~50% with higher procurement.',
                }
            return {'impacts_battery': False, 'impact_severity': 'none', 'reasoning': 'Protocol change not directly relevant.'}
        
        elif notice_type == 'WIND_FORECAST':
            return {
                'impacts_battery': True,
                'impact_severity': 'medium',
                'affected_zones': ['HB_WEST', 'system_wide'],
                'price_impact_direction': 'down',
                'price_impact_estimate': -15,
                'duration_hours': 8,
                'dispatch_action': 'Prepare for charging opportunity. Wind ramp will depress prices '
                                  'significantly overnight. Charge at near-zero or negative prices.',
                'reasoning': 'Major wind ramp will flood the grid with cheap power overnight.',
                'opportunity': 'Charge at $0-5/MWh overnight, discharge at $30-50/MWh in morning.',
            }
        
        return {
            'impacts_battery': False,
            'impact_severity': 'none',
            'reasoning': 'Notice type not recognized as battery-relevant.',
        }
    
    def get_active_dispatch_adjustments(self) -> List[dict]:
        """
        Get all currently active impacts that should modify dispatch.
        This feeds into the dispatch agent's decision logic.
        """
        now = datetime.now()
        active = []
        
        for impact in self.active_impacts:
            analysis = impact['analysis']
            notice_time = datetime.fromisoformat(impact['timestamp'])
            duration = analysis.get('duration_hours', 0)
            
            if notice_time + timedelta(hours=duration) > now:
                active.append({
                    'source': 'market_notice',
                    'notice_id': impact['notice_id'],
                    'severity': analysis.get('impact_severity', 'low'),
                    'price_direction': analysis.get('price_impact_direction', 'neutral'),
                    'price_estimate': analysis.get('price_impact_estimate', 0),
                    'dispatch_action': analysis.get('dispatch_action', ''),
                    'expires': (notice_time + timedelta(hours=duration)).isoformat(),
                })
        
        return active
    
    def get_dispatch_bias(self) -> dict:
        """
        Aggregate all active notices into a single dispatch bias.
        This modifies the base dispatch agent's behavior.
        """
        active = self.get_active_dispatch_adjustments()
        
        if not active:
            return {'price_bias': 0, 'hold_bias': 0, 'severity': 'none', 'active_notices': 0}
        
        # Aggregate price bias
        total_price_bias = sum(
            a['price_estimate'] * (1 if a['price_direction'] == 'up' else -1 if a['price_direction'] == 'down' else 0)
            for a in active
        )
        
        # If any critical notices, increase hold bias (conserve charge)
        max_severity = max(
            ['none', 'low', 'medium', 'high', 'critical'].index(a['severity'])
            for a in active
        )
        hold_bias = max_severity * 0.1  # 0-0.4 bias toward holding
        
        return {
            'price_bias': round(total_price_bias, 2),
            'hold_bias': round(hold_bias, 2),
            'severity': ['none', 'low', 'medium', 'high', 'critical'][max_severity],
            'active_notices': len(active),
        }


def demo():
    """Demonstrate market notice reading."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Autonomous Market Notice Reader")
    print("=" * 70)
    print()
    print("  ML can't read PDFs. Claude can.")
    print("  Every ERCOT notice gets analyzed for battery dispatch impact.")
    print()
    
    reader = MarketNoticeReader()
    
    for notice in SAMPLE_NOTICES:
        result = reader.analyze_notice(notice)
        analysis = result['analysis']
        
        impacts = '⚠' if analysis.get('impacts_battery') else ' '
        severity = analysis.get('impact_severity', 'none')
        
        print(f"  {impacts} [{severity.upper():<8}] {notice['title']}")
        
        if analysis.get('impacts_battery'):
            print(f"    Price impact: {analysis.get('price_impact_direction', '?')} "
                  f"${analysis.get('price_impact_estimate', 0):+.0f}/MWh")
            print(f"    Duration: {analysis.get('duration_hours', 0)}h")
            print(f"    Action: {analysis.get('dispatch_action', 'N/A')[:80]}")
            if analysis.get('opportunity'):
                print(f"    Opportunity: {analysis['opportunity'][:80]}")
        print()
    
    # Show aggregated dispatch bias
    bias = reader.get_dispatch_bias()
    
    print(f"{'='*70}")
    print("AGGREGATED DISPATCH BIAS FROM ALL NOTICES")
    print(f"{'='*70}")
    print(f"\n  Active notices: {bias['active_notices']}")
    print(f"  Price bias: ${bias['price_bias']:+.0f}/MWh (adjust forecast up/down)")
    print(f"  Hold bias: {bias['hold_bias']:.1f} (0=normal, 0.4=very conservative)")
    print(f"  Overall severity: {bias['severity']}")
    
    print(f"\n  This bias feeds directly into the dispatch agent:")
    print(f"  - Forecast adjusted by ${bias['price_bias']:+.0f}/MWh")
    print(f"  - Discharge threshold raised by {bias['hold_bias']*100:.0f}%")
    print(f"  - Conservation mode: {'YES' if bias['severity'] in ['high', 'critical'] else 'NO'}")
    
    print(f"\n{'='*70}")
    print("WHY THIS MATTERS:")
    print(f"{'='*70}")
    print("""
  A generator outage notice at 8 AM changes the market for days.
  A weather advisory changes it for a week.
  A protocol change changes it permanently.
  
  Systems that only look at price history CANNOT see these coming.
  VoltStream reads every notice, analyzes the impact, and adjusts
  dispatch strategy BEFORE the market moves.
  
  This is intelligence that no amount of ML training data can replace.
  It requires READING and REASONING — which is why Claude exists
  in the architecture.
""")


if __name__ == '__main__':
    demo()
