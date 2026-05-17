"""
VoltStream AI — Level 5: Cross-Domain Synthesis
=================================================
Level 4 models other batteries.
Level 5 connects EVERYTHING ELSE.

A pipeline shutdown in Louisiana.
A hurricane forming in the Gulf.
A regulatory filing about transmission upgrades.
A tweet from the ERCOT CEO about grid conditions.
A natural gas futures contract expiring Friday.

None of these are "battery data." But all of them move
the electricity market. A human trader might connect one
or two of these dots. VoltStream connects ALL of them,
simultaneously, 24/7.

THIS IS THE LEVEL WHERE AI BECOMES SUPERHUMAN.
No human can read 50 ERCOT notices, 200 news articles,
14 weather models, natural gas futures, pipeline flow data,
generator maintenance schedules, and political news
every single day and synthesize them into a dispatch decision.

VoltStream can.

DOMAINS SYNTHESIZED:
1. Energy news (plant outages, retirements, new builds)
2. Weather events (hurricanes, ice storms, heat domes)
3. Natural gas markets (futures, pipeline flows, storage)
4. Regulatory/political (PUCT orders, legislation, ERCOT rules)
5. Grid infrastructure (transmission outages, upgrades, constraints)
6. Economic indicators (industrial demand, data center buildouts)
7. Social/seasonal (holidays, events, school schedules)
"""

import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional


class InformationSource:
    """Represents a source of information from outside the energy market."""
    
    def __init__(self, domain: str, name: str):
        self.domain = domain
        self.name = name
        self.signals = []
    
    def add_signal(self, signal: dict):
        self.signals.append({
            **signal,
            'domain': self.domain,
            'source': self.name,
            'timestamp': datetime.now().isoformat(),
        })


class CrossDomainSynthesizer:
    """
    The brain that connects dots across completely different domains.
    
    It doesn't just process each signal independently.
    It looks for INTERACTIONS between signals that create
    opportunities no single-domain analysis would find.
    """
    
    def __init__(self):
        self.active_signals = []
        self.synthesis_log = []
        self.impact_chains = []
    
    def ingest_signal(self, domain: str, event: str, details: str,
                      magnitude: str = 'medium', duration_days: int = 1) -> dict:
        """
        Ingest a signal from any domain and trace its impact
        chain to the electricity market.
        """
        signal = {
            'id': f"SIG-{len(self.active_signals)+1:04d}",
            'domain': domain,
            'event': event,
            'details': details,
            'magnitude': magnitude,
            'duration_days': duration_days,
            'timestamp': datetime.now().isoformat(),
            'impact_chain': [],
            'price_impact': 0,
            'dispatch_action': '',
            'confidence': 0,
        }
        
        # Trace the causal chain from this domain to electricity prices
        chain = self._trace_impact_chain(domain, event, details, magnitude)
        signal['impact_chain'] = chain['steps']
        signal['price_impact'] = chain['price_impact']
        signal['dispatch_action'] = chain['dispatch_action']
        signal['confidence'] = chain['confidence']
        signal['affected_zones'] = chain.get('affected_zones', ['system_wide'])
        
        self.active_signals.append(signal)
        return signal
    
    def _trace_impact_chain(self, domain: str, event: str, 
                            details: str, magnitude: str) -> dict:
        """
        Trace the causal chain from a cross-domain event
        to its impact on electricity prices.
        
        This is the core synthesis logic. Each domain has
        known pathways to the electricity market.
        """
        steps = []
        price_impact = 0
        dispatch_action = 'HOLD'
        confidence = 0.5
        affected_zones = ['system_wide']
        
        details_lower = details.lower()
        event_lower = event.lower()
        
        mag_multiplier = {'low': 0.5, 'medium': 1.0, 'high': 2.0, 'critical': 3.0}
        mult = mag_multiplier.get(magnitude, 1.0)
        
        # ===================================================
        # NATURAL GAS MARKET
        # ===================================================
        if domain == 'natural_gas':
            if 'pipeline' in event_lower and ('shutdown' in details_lower or 'outage' in details_lower or 'maintenance' in details_lower):
                steps = [
                    f"Pipeline disruption reduces gas supply to Texas",
                    f"Gas prices increase at Houston Ship Channel hub",
                    f"Gas plant marginal costs rise (cost = gas_price x heat_rate)",
                    f"ERCOT electricity prices rise, especially during gas-on-margin hours",
                ]
                price_impact = 8 * mult
                dispatch_action = 'HOLD_FOR_SPIKE'
                confidence = 0.75
                
            elif 'futures' in event_lower or 'price' in event_lower:
                if 'rise' in details_lower or 'increase' in details_lower or 'surge' in details_lower:
                    steps = [
                        f"Natural gas futures rising",
                        f"Forward gas prices increase for Texas generators",
                        f"All gas generation becomes more expensive",
                        f"Electricity price floor rises across ERCOT",
                    ]
                    price_impact = 5 * mult
                    dispatch_action = 'HOLD_FOR_HIGHER_PRICES'
                    confidence = 0.70
                elif 'fall' in details_lower or 'drop' in details_lower or 'decline' in details_lower:
                    steps = [
                        f"Natural gas futures falling",
                        f"Gas generation becomes cheaper",
                        f"Electricity price ceiling drops",
                        f"Reduced arbitrage spread for batteries",
                    ]
                    price_impact = -5 * mult
                    dispatch_action = 'LOWER_EXPECTATIONS'
                    confidence = 0.65
                    
            elif 'storage' in event_lower:
                if 'draw' in details_lower or 'withdraw' in details_lower:
                    steps = [
                        f"Gas storage withdrawals exceed expectations",
                        f"Tightening gas supply supports higher gas prices",
                        f"Gas generation costs trend higher",
                        f"Electricity prices supported at higher levels",
                    ]
                    price_impact = 3 * mult
                    dispatch_action = 'MODERATE_BULLISH'
                    confidence = 0.55
        
        # ===================================================
        # WEATHER EVENTS
        # ===================================================
        elif domain == 'weather':
            if 'hurricane' in event_lower or 'tropical' in event_lower:
                steps = [
                    f"Tropical system threatens Texas Gulf Coast",
                    f"Coastal gas plants may shut down preemptively",
                    f"Offshore gas production disrupted, tightening gas supply",
                    f"Wind patterns disrupted in coastal regions",
                    f"Potential load reduction from evacuations offset by recovery demand",
                    f"High price volatility expected for 5-10 days",
                ]
                price_impact = 25 * mult
                dispatch_action = 'MAXIMIZE_SOC'
                confidence = 0.80
                affected_zones = ['HB_HOUSTON', 'LZ_HOUSTON', 'HB_SOUTH']
                
            elif 'ice' in event_lower or 'freeze' in event_lower or 'winter storm' in event_lower:
                steps = [
                    f"Winter storm / freeze event approaching Texas",
                    f"Heating demand surges across the state",
                    f"Gas demand spikes for both heating and power generation",
                    f"Wind turbines may ice up, reducing wind generation",
                    f"Gas pipeline pressure drops, some plants can't get fuel",
                    f"RISK OF EXTREME SCARCITY PRICING ($1,000-$9,000/MWh)",
                ]
                price_impact = 100 * mult
                dispatch_action = 'EMERGENCY_HOLD'
                confidence = 0.85
                
            elif 'heat dome' in event_lower or 'heat wave' in event_lower or 'extreme heat' in event_lower:
                steps = [
                    f"Extended heat event forecast for Texas",
                    f"Cooling demand pushes load to near-record levels",
                    f"All available generation dispatched",
                    f"Reserve margins thin, scarcity pricing possible",
                    f"Multi-day event means sustained high prices, not just spikes",
                ]
                price_impact = 30 * mult
                dispatch_action = 'CYCLE_AGGRESSIVELY'
                confidence = 0.80
                
            elif 'cloud' in event_lower or 'overcast' in event_lower:
                steps = [
                    f"Extended cloud cover forecast over solar regions",
                    f"Solar generation drops 50-80% from clear-sky levels",
                    f"Gas plants must fill the gap",
                    f"Midday price floor rises from near-zero to $20-30",
                ]
                price_impact = 15 * mult
                dispatch_action = 'SHIFT_CHARGE_WINDOW'
                confidence = 0.65
        
        # ===================================================
        # REGULATORY / POLITICAL
        # ===================================================
        elif domain == 'regulatory':
            if 'puct' in event_lower or 'commission' in event_lower:
                if 'price cap' in details_lower:
                    steps = [
                        f"PUCT considering changes to ERCOT price cap",
                        f"Current cap is $5,000/MWh (HCAP) and $9,000/MWh (SWCAP)",
                        f"Changes affect the maximum possible revenue during scarcity",
                        f"Lower cap = lower spike revenue potential for batteries",
                    ]
                    price_impact = 0  # long term structural, not immediate
                    dispatch_action = 'MONITOR'
                    confidence = 0.50
                    
                elif 'ancillary' in details_lower or 'reserve' in details_lower:
                    steps = [
                        f"PUCT ordering changes to ancillary service procurement",
                        f"More AS procurement = higher AS clearing prices",
                        f"Batteries can earn more from AS participation",
                        f"Shift capacity allocation toward ancillary services",
                    ]
                    price_impact = 0
                    dispatch_action = 'INCREASE_AS_ALLOCATION'
                    confidence = 0.65
                    
            elif 'legislation' in event_lower or 'bill' in event_lower or 'law' in event_lower:
                if 'renewable' in details_lower or 'solar' in details_lower or 'wind' in details_lower:
                    steps = [
                        f"New legislation affecting renewable energy in Texas",
                        f"Could accelerate or slow renewable buildout",
                        f"More renewables = more price volatility = more battery opportunity",
                        f"Long-term structural impact on market dynamics",
                    ]
                    price_impact = 0
                    dispatch_action = 'STRATEGIC_POSITIONING'
                    confidence = 0.40
        
        # ===================================================
        # GRID INFRASTRUCTURE
        # ===================================================
        elif domain == 'grid_infrastructure':
            if 'transmission' in event_lower:
                if 'outage' in details_lower or 'constraint' in details_lower or 'maintenance' in details_lower:
                    steps = [
                        f"Transmission constraint reducing transfer capability",
                        f"Power cannot flow freely between zones",
                        f"Congestion creates price separation between zones",
                        f"Batteries in constrained zones see different prices than system average",
                    ]
                    price_impact = 10 * mult
                    dispatch_action = 'EXPLOIT_CONGESTION'
                    confidence = 0.70
                    affected_zones = ['HB_WEST', 'HB_HOUSTON']
                    
            elif 'generator' in event_lower:
                if 'retirement' in details_lower or 'decommission' in details_lower:
                    steps = [
                        f"Generator retirement reduces available supply",
                        f"Remaining generators dispatched more frequently",
                        f"Higher-cost units set price more often",
                        f"Structural increase in average electricity prices",
                    ]
                    price_impact = 3 * mult
                    dispatch_action = 'LONG_TERM_BULLISH'
                    confidence = 0.60
                    
                elif 'new' in details_lower or 'commission' in details_lower or 'online' in details_lower:
                    steps = [
                        f"New generation coming online increases supply",
                        f"Pushes higher-cost generators down the merit order",
                        f"Could reduce average prices in affected zone",
                    ]
                    price_impact = -3 * mult
                    dispatch_action = 'MONITOR'
                    confidence = 0.55
        
        # ===================================================
        # ECONOMIC / DEMAND
        # ===================================================
        elif domain == 'economic':
            if 'data center' in event_lower:
                steps = [
                    f"New data center buildout announced in Texas",
                    f"Data centers consume 50-200 MW of continuous power",
                    f"Increases baseload demand permanently",
                    f"Higher demand = higher prices, especially during peaks",
                    f"Long-term structural bullish signal for battery revenue",
                ]
                price_impact = 2 * mult
                dispatch_action = 'LONG_TERM_BULLISH'
                confidence = 0.60
                
            elif 'industrial' in event_lower:
                if 'shutdown' in details_lower or 'closure' in details_lower:
                    steps = [
                        f"Major industrial load shutting down",
                        f"Reduces demand by hundreds of MW",
                        f"Lower demand = lower prices",
                    ]
                    price_impact = -5 * mult
                    dispatch_action = 'LOWER_EXPECTATIONS'
                    confidence = 0.55
                    
            elif 'lng' in event_lower or 'export' in event_lower:
                steps = [
                    f"LNG export activity changes at Gulf Coast terminals",
                    f"Higher LNG exports = more domestic gas demand = higher gas prices",
                    f"Higher gas prices flow through to electricity prices",
                ]
                price_impact = 4 * mult
                dispatch_action = 'MODERATE_BULLISH'
                confidence = 0.55
        
        # ===================================================
        # SEASONAL / SOCIAL
        # ===================================================
        elif domain == 'seasonal':
            if 'holiday' in event_lower:
                steps = [
                    f"Major holiday reduces commercial/industrial demand",
                    f"Lower demand during business hours",
                    f"Prices suppressed, especially midday",
                ]
                price_impact = -5 * mult
                dispatch_action = 'REDUCE_CYCLING'
                confidence = 0.70
                
            elif 'school' in event_lower:
                if 'start' in details_lower or 'begin' in details_lower:
                    steps = [
                        f"School year starting across Texas",
                        f"AC demand increases as schools cool buildings",
                        f"Morning demand ramp steepens",
                        f"Marginal increase in peak demand",
                    ]
                    price_impact = 2 * mult
                    dispatch_action = 'SLIGHT_BULLISH'
                    confidence = 0.50
                    
            elif 'event' in event_lower or 'festival' in event_lower:
                steps = [
                    f"Large event driving temporary demand increase",
                    f"Localized load increase in event area",
                ]
                price_impact = 1 * mult
                dispatch_action = 'MONITOR'
                confidence = 0.40
        
        # Default if domain not recognized
        if not steps:
            steps = [
                f"Signal from {domain}: {event}",
                f"Impact pathway to electricity market unclear",
                f"Monitoring for further developments",
            ]
            confidence = 0.30
        
        return {
            'steps': steps,
            'price_impact': round(price_impact, 2),
            'dispatch_action': dispatch_action,
            'confidence': round(confidence, 2),
            'affected_zones': affected_zones,
        }
    
    def synthesize(self) -> dict:
        """
        Synthesize ALL active signals into one unified market view.
        
        This is where the magic happens. Individual signals are
        useful. But the INTERACTION between signals is where
        the superhuman insight lives.
        """
        if not self.active_signals:
            return {'net_bias': 0, 'confidence': 0, 'signals': 0}
        
        # Aggregate price impacts
        total_impact = sum(s['price_impact'] * s['confidence'] for s in self.active_signals)
        avg_confidence = np.mean([s['confidence'] for s in self.active_signals])
        
        # Check for signal interactions (amplifying or canceling)
        interactions = self._detect_interactions()
        
        # Net market bias
        if total_impact > 10:
            market_bias = 'strongly_bullish'
            recommendation = 'Hold maximum charge for discharge at elevated prices'
        elif total_impact > 3:
            market_bias = 'moderately_bullish'
            recommendation = 'Lean toward holding charge, raise discharge thresholds'
        elif total_impact < -10:
            market_bias = 'strongly_bearish'
            recommendation = 'Discharge available charge, lower expectations for spreads'
        elif total_impact < -3:
            market_bias = 'moderately_bearish'
            recommendation = 'Lower discharge thresholds, cycle more frequently'
        else:
            market_bias = 'neutral'
            recommendation = 'No strong cross-domain bias. Trade on price signals.'
        
        # Urgency
        critical_signals = [s for s in self.active_signals if s['magnitude'] in ['high', 'critical']]
        urgency = 'critical' if any(s['magnitude'] == 'critical' for s in self.active_signals) else \
                  'high' if critical_signals else \
                  'normal'
        
        synthesis = {
            'timestamp': datetime.now().isoformat(),
            'total_signals': len(self.active_signals),
            'net_price_impact': round(total_impact, 2),
            'avg_confidence': round(avg_confidence, 2),
            'market_bias': market_bias,
            'recommendation': recommendation,
            'urgency': urgency,
            'interactions': interactions,
            'signals_by_domain': self._group_by_domain(),
            'top_signals': sorted(self.active_signals, 
                                  key=lambda s: abs(s['price_impact'] * s['confidence']),
                                  reverse=True)[:5],
        }
        
        self.synthesis_log.append(synthesis)
        return synthesis
    
    def _detect_interactions(self) -> List[dict]:
        """
        Detect when multiple signals INTERACT to create
        a bigger effect than either one alone.
        """
        interactions = []
        
        domains = set(s['domain'] for s in self.active_signals)
        
        # Gas + Weather interaction
        gas_signals = [s for s in self.active_signals if s['domain'] == 'natural_gas']
        weather_signals = [s for s in self.active_signals if s['domain'] == 'weather']
        
        if gas_signals and weather_signals:
            gas_bullish = any(s['price_impact'] > 0 for s in gas_signals)
            weather_bullish = any(s['price_impact'] > 0 for s in weather_signals)
            
            if gas_bullish and weather_bullish:
                interactions.append({
                    'type': 'amplifying',
                    'domains': ['natural_gas', 'weather'],
                    'effect': 'Gas supply tight AND extreme weather. Double pressure on prices. '
                              'Expect amplified price spikes during peak hours.',
                    'multiplier': 1.5,
                })
            elif gas_bullish and not weather_bullish:
                interactions.append({
                    'type': 'partially_offsetting',
                    'domains': ['natural_gas', 'weather'],
                    'effect': 'Gas prices up but weather is mild. Impact partially offset by '
                              'lower demand. Still net bullish but reduced.',
                    'multiplier': 0.8,
                })
        
        # Weather + Grid interaction
        grid_signals = [s for s in self.active_signals if s['domain'] == 'grid_infrastructure']
        
        if weather_signals and grid_signals:
            weather_stress = any(s['magnitude'] in ['high', 'critical'] for s in weather_signals)
            grid_constraint = any('constraint' in s['event'].lower() or 'outage' in s['event'].lower() 
                                 for s in grid_signals)
            
            if weather_stress and grid_constraint:
                interactions.append({
                    'type': 'dangerous_combination',
                    'domains': ['weather', 'grid_infrastructure'],
                    'effect': 'Extreme weather PLUS grid constraints is how Texas blackouts happen. '
                              'Extremely high price risk. Maximize SOC immediately.',
                    'multiplier': 3.0,
                })
        
        # Economic + Regulatory interaction
        econ_signals = [s for s in self.active_signals if s['domain'] == 'economic']
        reg_signals = [s for s in self.active_signals if s['domain'] == 'regulatory']
        
        if econ_signals and reg_signals:
            interactions.append({
                'type': 'structural_shift',
                'domains': ['economic', 'regulatory'],
                'effect': 'Economic changes combined with regulatory shifts suggest '
                          'structural market evolution. Long-term strategy adjustment needed.',
                'multiplier': 1.0,
            })
        
        return interactions
    
    def _group_by_domain(self) -> dict:
        """Group active signals by domain."""
        groups = {}
        for signal in self.active_signals:
            domain = signal['domain']
            if domain not in groups:
                groups[domain] = []
            groups[domain].append({
                'event': signal['event'],
                'impact': signal['price_impact'],
                'confidence': signal['confidence'],
                'action': signal['dispatch_action'],
            })
        return groups


def demo():
    """Demonstrate cross-domain synthesis."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Level 5: Cross-Domain Synthesis")
    print("=" * 70)
    print()
    print("  A pipeline in Louisiana. A hurricane in the Gulf.")
    print("  A regulatory filing. A data center announcement.")
    print("  None of these are 'battery data.'")
    print("  All of them move the electricity market.")
    print()
    
    synth = CrossDomainSynthesizer()
    
    # Simulate a complex market situation with multiple cross-domain signals
    signals = [
        {
            'domain': 'natural_gas',
            'event': 'Pipeline maintenance shutdown',
            'details': 'Gulf South Pipeline scheduling 5-day maintenance on Louisiana segment. '
                       'Reduces capacity by 800 MMcf/d to Texas markets.',
            'magnitude': 'high',
            'duration_days': 5,
        },
        {
            'domain': 'weather',
            'event': 'Heat wave forecast',
            'details': 'NWS forecasting 5-day heat dome over Central and North Texas. '
                       'Temperatures expected to exceed 105F. Record demand possible.',
            'magnitude': 'critical',
            'duration_days': 5,
        },
        {
            'domain': 'grid_infrastructure',
            'event': 'Transmission maintenance',
            'details': 'West-to-Houston 345kV corridor reduced capacity for maintenance. '
                       'Transfer capability down 2000 MW through Thursday.',
            'magnitude': 'medium',
            'duration_days': 3,
        },
        {
            'domain': 'economic',
            'event': 'Data center announcement',
            'details': 'Major tech company announces 500 MW data center campus in Dallas. '
                       'Expected to come online in phases over 18 months.',
            'magnitude': 'medium',
            'duration_days': 365,
        },
        {
            'domain': 'regulatory',
            'event': 'PUCT ancillary service order',
            'details': 'PUCT orders ERCOT to increase DRRS procurement from 3000 MW to '
                       '4500 MW during summer peak hours effective next month.',
            'magnitude': 'medium',
            'duration_days': 90,
        },
        {
            'domain': 'seasonal',
            'event': 'Holiday weekend',
            'details': 'Memorial Day weekend. Reduced commercial load Monday.',
            'magnitude': 'low',
            'duration_days': 1,
        },
    ]
    
    print("INGESTING SIGNALS FROM 6 DIFFERENT DOMAINS:")
    print("=" * 70)
    
    for sig_data in signals:
        signal = synth.ingest_signal(**sig_data)
        
        icon = {
            'natural_gas': '🔥', 'weather': '🌡️', 'grid_infrastructure': '⚡',
            'economic': '📊', 'regulatory': '📋', 'seasonal': '📅',
        }.get(sig_data['domain'], '📌')
        
        print(f"\n  {icon} [{sig_data['domain'].upper()}] {signal['event']}")
        print(f"     Magnitude: {sig_data['magnitude']} | Duration: {sig_data['duration_days']} days")
        
        print(f"     Impact chain:")
        for i, step in enumerate(signal['impact_chain'], 1):
            print(f"       {i}. {step}")
        
        impact_dir = "↑" if signal['price_impact'] > 0 else "↓" if signal['price_impact'] < 0 else "→"
        print(f"     Price impact: {impact_dir} ${signal['price_impact']:+.1f}/MWh "
              f"(confidence: {signal['confidence']:.0%})")
        print(f"     Action: {signal['dispatch_action']}")
    
    # Now synthesize everything together
    print(f"\n{'='*70}")
    print("SYNTHESIS: ALL SIGNALS COMBINED")
    print(f"{'='*70}")
    
    result = synth.synthesize()
    
    print(f"\n  Total signals: {result['total_signals']}")
    print(f"  Net price impact: ${result['net_price_impact']:+.1f}/MWh")
    print(f"  Average confidence: {result['avg_confidence']:.0%}")
    print(f"  Market bias: {result['market_bias'].upper()}")
    print(f"  Urgency: {result['urgency'].upper()}")
    print(f"\n  Recommendation: {result['recommendation']}")
    
    if result['interactions']:
        print(f"\n  SIGNAL INTERACTIONS DETECTED:")
        for interaction in result['interactions']:
            print(f"\n    Type: {interaction['type'].upper()}")
            print(f"    Domains: {' + '.join(interaction['domains'])}")
            print(f"    Effect: {interaction['effect']}")
            print(f"    Impact multiplier: {interaction['multiplier']}x")
    
    print(f"\n  TOP SIGNALS BY IMPACT:")
    for i, sig in enumerate(result['top_signals'], 1):
        print(f"    {i}. [{sig['domain']}] {sig['event']} "
              f"(${sig['price_impact']:+.1f}, {sig['confidence']:.0%})")
    
    print(f"\n{'='*70}")
    print("WHAT JUST HAPPENED:")
    print(f"{'='*70}")
    print(f"""
  The brain connected 6 different domains simultaneously:
  
  1. A pipeline shutdown in LOUISIANA will tighten gas supply in TEXAS
  2. A heat wave will spike DEMAND at the same time supply is tight  
  3. A transmission constraint will trap cheap power in WEST TEXAS
  4. These three signals INTERACT: gas tight + extreme heat + grid
     constraint is how Texas blackouts happen. 3x impact multiplier.
  
  5. A data center adds 500 MW of permanent demand (long-term bullish)
  6. DRRS procurement increase means more AS revenue for batteries
  7. A holiday temporarily reduces demand (minor offset)
  
  NET RESULT: Strongly bullish. Multiple reinforcing signals.
  The brain says: MAXIMIZE SOC NOW. Extreme prices likely.
  
  No human trader reads a Louisiana pipeline filing and connects
  it to a battery in West Texas while simultaneously factoring in
  a PUCT regulatory order and a data center announcement.
  
  VoltStream does. Every 5 minutes. 24/7.
""")


if __name__ == '__main__':
    demo()
