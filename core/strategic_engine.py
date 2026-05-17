"""
VoltStream AI — Level 7: Strategic Positioning
================================================
Level 6 looks inward to fix weaknesses.
Level 7 looks FORWARD across months and years.

This is the highest level of intelligence. The brain stops
thinking about the next interval and starts thinking about
the next quarter.

KEY QUESTIONS LEVEL 7 ANSWERS:
1. If we keep discharging at 6 PM every day, will other
   batteries copy us and destroy the 6 PM premium?
2. Should we sacrifice today's revenue to build a data
   advantage that pays off for the next 12 months?
3. Which ERCOT nodes will be most profitable next year
   based on planned generation and transmission buildout?
4. How should we position across ancillary service markets
   as ERCOT rules evolve?
5. When should we recommend our customer build MORE storage
   vs optimize what they have?

THIS IS CEO-LEVEL THINKING, NOT TRADER-LEVEL THINKING.
The brain manages the battery like a business, not just a trade.
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from collections import defaultdict


class MarketImpactModel:
    """
    Models VoltStream's own impact on the market.
    
    As VoltStream grows from 100 MW to 1 GW under management,
    its own trading starts moving prices. The brain needs to
    account for this.
    """
    
    def __init__(self, managed_mw: float = 100):
        self.managed_mw = managed_mw
        self.ercot_total_battery_mw = 5000
        self.market_share = managed_mw / self.ercot_total_battery_mw
        self.trade_history = []
    
    def estimate_self_impact(self, action_mw: float, current_price: float) -> dict:
        """
        How much does OUR OWN trading move the price?
        At 100 MW this is negligible. At 1 GW it's significant.
        """
        # Price impact roughly $0.5-1.0 per 1000 MW of battery action
        impact_per_mw = 0.001 * (1 + current_price / 100)
        price_impact = action_mw * impact_per_mw
        
        # Slippage: the price moves AGAINST us as we trade
        slippage_cost = abs(price_impact) * action_mw * 0.25  # per interval
        
        # At what size does our impact become material?
        material_threshold = 500  # MW where impact > $1/MWh
        is_material = self.managed_mw > material_threshold
        
        return {
            'price_impact': round(price_impact, 3),
            'slippage_cost': round(slippage_cost, 2),
            'is_material': is_material,
            'market_share': round(self.market_share * 100, 1),
            'recommendation': (
                'Trade freely, impact negligible' if not is_material else
                'Spread trades across intervals to reduce impact'
            ),
        }
    
    def strategy_decay_risk(self, strategy_pattern: dict) -> dict:
        """
        If we always discharge at 6 PM, will the signal get crowded?
        
        Assess the risk that our profitable patterns become
        unprofitable as others copy them or the market adapts.
        """
        # How predictable is our trading pattern?
        predictability = strategy_pattern.get('pattern_consistency', 0.5)
        
        # How many other batteries could observe and copy?
        copycat_risk = predictability * self.market_share * 10
        
        # How much would crowding reduce the premium?
        peak_hour = strategy_pattern.get('peak_discharge_hour', 18)
        typical_premium = strategy_pattern.get('avg_discharge_price', 50)
        
        if copycat_risk > 0.3:
            premium_erosion = typical_premium * copycat_risk * 0.2
            time_to_decay = max(1, int(12 / copycat_risk))
        else:
            premium_erosion = 0
            time_to_decay = 999
        
        return {
            'predictability': round(predictability, 2),
            'copycat_risk': round(copycat_risk, 2),
            'premium_erosion': round(premium_erosion, 2),
            'months_until_decay': time_to_decay,
            'recommendation': (
                'Diversify discharge timing to avoid pattern detection'
                if copycat_risk > 0.3 else
                'Current pattern is sustainable'
            ),
        }


class LongTermPositioner:
    """
    Thinks in quarters and years, not minutes and hours.
    
    Makes strategic decisions about:
    - Which markets to focus on
    - When to sacrifice short-term revenue for long-term advantage
    - Where to position as the grid evolves
    """
    
    def __init__(self):
        self.strategic_log = []
    
    def analyze_market_evolution(self) -> dict:
        """
        Where is the ERCOT battery market heading?
        Position VoltStream for the future, not just today.
        """
        trends = {
            'solar_buildout': {
                'direction': 'accelerating',
                'impact': 'Midday prices will continue falling toward zero. '
                          'Morning and evening ramps will steepen. '
                          'The charge window shifts earlier and the discharge window gets narrower.',
                'positioning': 'Optimize for the 4-7 PM discharge window. '
                               'Build capability for sub-hourly trading during ramp periods.',
                'timeline': '2026-2028',
                'confidence': 0.85,
            },
            'battery_saturation': {
                'direction': 'growing',
                'impact': 'More batteries means more competition for the same arbitrage spreads. '
                          'Simple strategies will earn less as more batteries chase the same signals.',
                'positioning': 'Differentiate through ancillary services, nodal optimization, '
                               'and faster reaction times. Sophistication becomes the moat.',
                'timeline': '2027-2030',
                'confidence': 0.75,
            },
            'drrs_expansion': {
                'direction': 'expanding',
                'impact': 'DRRS procurement increasing. 4-hour batteries have exclusive access. '
                          'Revenue from DRRS will grow as a percentage of total battery revenue.',
                'positioning': 'Build deep DRRS optimization expertise NOW while the market is young. '
                               'First-mover advantage in DRRS strategy is worth 12+ months of lead time.',
                'timeline': '2026-2027',
                'confidence': 0.80,
            },
            'data_center_demand': {
                'direction': 'surging',
                'impact': 'Data centers adding 5-10 GW of baseload demand to Texas. '
                          'Raises the floor on electricity prices. '
                          'Increases the value of flexible resources like batteries.',
                'positioning': 'Target data center operators as customers. '
                               'They need batteries for reliability and price hedging. '
                               'They have money and they understand AI.',
                'timeline': '2025-2030',
                'confidence': 0.80,
            },
            'transmission_buildout': {
                'direction': 'slow',
                'impact': 'Transmission takes 5-10 years to build. '
                          'West Texas congestion will persist. '
                          'Nodal price spreads remain profitable.',
                'positioning': 'Invest in GNN nodal price modeling. '
                               'Congestion prediction is a durable advantage.',
                'timeline': '2026-2035',
                'confidence': 0.70,
            },
        }
        
        return trends
    
    def strategic_recommendations(self, current_portfolio: dict) -> dict:
        """
        Generate strategic recommendations for the next quarter.
        """
        managed_mw = current_portfolio.get('managed_mw', 100)
        n_assets = current_portfolio.get('n_assets', 1)
        avg_revenue_per_mw = current_portfolio.get('avg_revenue_per_mw', 150)
        primary_market = current_portfolio.get('primary_market', 'energy_arbitrage')
        
        recommendations = []
        
        # Revenue diversification
        if primary_market == 'energy_arbitrage':
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Revenue Diversification',
                'action': 'Shift 30-40% of capacity to ancillary services',
                'reasoning': 'Energy arbitrage spreads are compressing as more batteries enter. '
                             'AS revenue is more stable and less competitive. '
                             'DRRS in particular is underpriced relative to its value.',
                'expected_impact': '+15-25% total revenue',
                'timeline': '30 days',
            })
        
        # Growth strategy
        if n_assets < 5:
            recommendations.append({
                'priority': 'HIGH',
                'category': 'Growth',
                'action': 'Prioritize signing assets in congestion-prone zones',
                'reasoning': 'Batteries in West Texas and Panhandle earn 20-50% more '
                             'due to congestion premiums. Target developers with '
                             'interconnection at high-spread nodes.',
                'expected_impact': '+30% revenue per asset vs average node',
                'timeline': '90 days',
            })
        
        # Data advantage
        if managed_mw < 500:
            recommendations.append({
                'priority': 'MEDIUM',
                'category': 'Data Moat',
                'action': 'Accept lower margins on initial assets to build data faster',
                'reasoning': 'Every asset generates training data that improves all assets. '
                             'The 5th asset benefits from the data of assets 1-4. '
                             'Revenue per asset increases with fleet size.',
                'expected_impact': 'Compounding model improvement',
                'timeline': '6 months',
            })
        
        # Technology investment
        recommendations.append({
            'priority': 'MEDIUM',
            'category': 'Technology',
            'action': 'Build real-time 5-minute SCED dispatch capability',
            'reasoning': 'Most competitors trade on 15-minute or hourly intervals. '
                         '5-minute dispatch captures intra-interval volatility '
                         'worth $5-10K per asset per month.',
            'expected_impact': '+$60-120K annual revenue per asset',
            'timeline': '60 days',
        })
        
        # Market expansion readiness
        recommendations.append({
            'priority': 'LOW',
            'category': 'Expansion',
            'action': 'Begin studying PJM and CAISO market structures',
            'reasoning': 'ERCOT expertise translates to other ISOs with modifications. '
                         'PJM has 4x the battery pipeline of ERCOT. '
                         'Being ready to expand when ERCOT growth is proven.',
            'expected_impact': '3x addressable market',
            'timeline': '12 months',
        })
        
        return {
            'portfolio': current_portfolio,
            'recommendations': recommendations,
            'strategic_focus': 'Build DRRS expertise + sign congestion-zone assets',
        }
    
    def node_attractiveness_ranking(self) -> list:
        """
        Rank ERCOT nodes by FUTURE attractiveness for batteries,
        considering planned buildout and market evolution.
        """
        nodes = [
            {
                'node': 'West Texas (Permian)',
                'current_revenue_rank': 1,
                'future_outlook': 'Strong',
                'reasons': [
                    'Massive wind + solar buildout = extreme price volatility',
                    'Persistent transmission congestion (5+ year buildout)',
                    'DRRS demand growing as grid relies more on batteries',
                ],
                'risks': ['Eventual transmission buildout reduces spreads'],
                'score': 92,
            },
            {
                'node': 'Houston Hub',
                'current_revenue_rank': 2,
                'future_outlook': 'Stable',
                'reasons': [
                    'Largest load center in ERCOT',
                    'Data center demand growing rapidly',
                    'Less congestion risk (demand matches supply locally)',
                ],
                'risks': ['New gas plants nearby could reduce prices'],
                'score': 85,
            },
            {
                'node': 'Panhandle',
                'current_revenue_rank': 3,
                'future_outlook': 'Volatile',
                'reasons': [
                    'Extreme wind generation creates wild price swings',
                    'Excellent for batteries that can handle volatility',
                ],
                'risks': ['Transmission expansion planned to reduce congestion',
                          'Population is sparse, limited local demand'],
                'score': 78,
            },
            {
                'node': 'North (Dallas)',
                'current_revenue_rank': 4,
                'future_outlook': 'Growing',
                'reasons': [
                    'Data center buildout in DFW area',
                    'Large population driving cooling demand growth',
                ],
                'risks': ['Well-connected node, less congestion premium'],
                'score': 75,
            },
            {
                'node': 'South (San Antonio)',
                'current_revenue_rank': 5,
                'future_outlook': 'Moderate',
                'reasons': [
                    'Solar buildout increasing local supply',
                    'Good for solar-arbitrage strategies',
                ],
                'risks': ['Solar saturation could reduce arbitrage value'],
                'score': 68,
            },
        ]
        
        return sorted(nodes, key=lambda n: n['score'], reverse=True)


class StrategicPositioner:
    """
    The highest level of the VoltStream brain.
    
    Thinks like a CEO, not a trader.
    Manages the battery fleet as a business.
    Positions for the future of the Texas grid.
    """
    
    def __init__(self, managed_mw: float = 100, n_assets: int = 1):
        self.impact_model = MarketImpactModel(managed_mw)
        self.positioner = LongTermPositioner()
        self.managed_mw = managed_mw
        self.n_assets = n_assets
    
    def full_strategic_review(self) -> dict:
        """
        Comprehensive strategic review. Run monthly.
        """
        # Market evolution
        trends = self.positioner.analyze_market_evolution()
        
        # Portfolio recommendations
        portfolio = {
            'managed_mw': self.managed_mw,
            'n_assets': self.n_assets,
            'avg_revenue_per_mw': 150,
            'primary_market': 'energy_arbitrage',
        }
        recommendations = self.positioner.strategic_recommendations(portfolio)
        
        # Node rankings
        node_rankings = self.positioner.node_attractiveness_ranking()
        
        # Market impact assessment
        impact = self.impact_model.estimate_self_impact(
            self.managed_mw * 0.8, 50
        )
        
        # Strategy decay
        decay = self.impact_model.strategy_decay_risk({
            'pattern_consistency': 0.6,
            'peak_discharge_hour': 18,
            'avg_discharge_price': 50,
        })
        
        return {
            'timestamp': datetime.now().isoformat(),
            'portfolio': portfolio,
            'market_trends': trends,
            'recommendations': recommendations,
            'node_rankings': node_rankings,
            'self_impact': impact,
            'strategy_decay': decay,
        }


def demo():
    """Demonstrate strategic positioning."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Level 7: Strategic Positioning")
    print("=" * 70)
    print()
    print("  Not 'what should I trade this interval?'")
    print("  But 'where should this company be in 12 months?'")
    print()
    
    strategist = StrategicPositioner(managed_mw=100, n_assets=1)
    review = strategist.full_strategic_review()
    
    # Market trends
    print(f"  {'='*60}")
    print(f"  MARKET EVOLUTION (where is ERCOT heading?)")
    print(f"  {'='*60}")
    
    for name, trend in review['market_trends'].items():
        print(f"\n  {name.replace('_', ' ').upper()} [{trend['direction']}] "
              f"(confidence: {trend['confidence']:.0%})")
        print(f"    Impact: {trend['impact'][:100]}")
        print(f"    Our move: {trend['positioning'][:100]}")
        print(f"    Timeline: {trend['timeline']}")
    
    # Strategic recommendations
    print(f"\n  {'='*60}")
    print(f"  STRATEGIC RECOMMENDATIONS (next quarter)")
    print(f"  {'='*60}")
    
    recs = review['recommendations']['recommendations']
    for rec in recs:
        icon = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
        print(f"\n  {icon.get(rec['priority'], '⚪')} [{rec['priority']}] {rec['category']}")
        print(f"    Action: {rec['action']}")
        print(f"    Why: {rec['reasoning'][:120]}")
        print(f"    Impact: {rec['expected_impact']}")
        print(f"    Timeline: {rec['timeline']}")
    
    print(f"\n  Strategic focus: {review['recommendations']['strategic_focus']}")
    
    # Node rankings
    print(f"\n  {'='*60}")
    print(f"  WHERE TO PUT THE NEXT BATTERY")
    print(f"  {'='*60}")
    
    print(f"\n  {'Rank':<6} {'Node':<25} {'Score':>6} {'Outlook':<12} {'Top Reason'}")
    print(f"  {'-'*75}")
    
    for i, node in enumerate(review['node_rankings'], 1):
        print(f"  #{i:<4} {node['node']:<25} {node['score']:>5}  {node['future_outlook']:<12} {node['reasons'][0][:40]}")
    
    # Market impact
    print(f"\n  {'='*60}")
    print(f"  OUR OWN MARKET IMPACT")
    print(f"  {'='*60}")
    
    impact = review['self_impact']
    print(f"\n  Market share: {impact['market_share']}%")
    print(f"  Price impact per trade: ${impact['price_impact']:.3f}/MWh")
    print(f"  Impact material? {impact['is_material']}")
    print(f"  Recommendation: {impact['recommendation']}")
    
    # Strategy decay
    decay = review['strategy_decay']
    print(f"\n  {'='*60}")
    print(f"  STRATEGY SUSTAINABILITY")
    print(f"  {'='*60}")
    
    print(f"\n  Pattern predictability: {decay['predictability']:.0%}")
    print(f"  Copycat risk: {decay['copycat_risk']:.0%}")
    print(f"  Premium erosion: ${decay['premium_erosion']:.1f}/MWh")
    print(f"  Months until strategy decay: {decay['months_until_decay']}")
    print(f"  Recommendation: {decay['recommendation']}")
    
    # The big picture
    print(f"\n{'='*70}")
    print("LEVEL 7 CAPABILITY:")
    print(f"{'='*70}")
    print("""
  The brain just thought like a CEO:
  
  1. MARKET EVOLUTION: "Solar buildout will keep compressing
     midday prices. Position for the 4-7 PM window NOW before
     everyone else figures this out."
  
  2. COMPETITIVE MOAT: "Accept lower margins on early assets
     to build the data advantage faster. Asset #5 benefits
     from the data of assets 1-4. Compound the moat."
  
  3. SITE SELECTION: "West Texas scores 92/100 for next battery.
     Congestion premiums persist for 5+ years because transmission
     takes that long to build. The spread is structural, not temporary."
  
  4. REVENUE DIVERSIFICATION: "Shift 30-40% to ancillary services.
     Energy arbitrage is getting crowded. DRRS is underpriced
     and we have first-mover advantage with 4-hour batteries."
  
  5. SELF-AWARENESS: "At 100 MW we don't move the market.
     At 1 GW we will. Start building execution algorithms
     that spread trades across intervals to minimize slippage."
  
  6. STRATEGY PRESERVATION: "Our 6 PM discharge pattern is
     sustainable for now, but at scale others will copy it.
     Diversify timing before the signal degrades."
  
  This is the final level. VoltStream doesn't just trade
  batteries. It manages a battery portfolio like a business,
  positioning for where the market is going, not where it's been.
  
  ALL 7 LEVELS COMPLETE.
  Pattern Memory → Causal Reasoning → Anticipatory Planning →
  Game Theory → Cross-Domain Synthesis → Self-Directed Learning →
  Strategic Positioning
  
  This is the brain.
""")


if __name__ == '__main__':
    demo()
