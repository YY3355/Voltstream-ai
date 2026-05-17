"""
VoltStream AI — Ancillary Service Co-Optimization
===================================================
Real battery revenue comes from SIMULTANEOUSLY optimizing across:
- Energy arbitrage (buy low, sell high)
- Regulation Up (get paid to be available to increase output)
- Regulation Down (get paid to be available to decrease output)
- Responsive Reserve Service (RRS) — fast frequency response
- ERCOT Contingency Reserve Service (ECRS)
- Dispatchable Reliability Reserve (DRRS) — NEW, 4-hour sustained

Each MW can only be committed to ONE market at a time.
The question every interval is: where is this MW most valuable?

Example:
  Energy price: $25/MWh → $25/MW for 1 hour of discharge
  Reg Up price: $30/MW → $30/MW just for being AVAILABLE
  → Commit to Reg Up, don't discharge

But:
  Energy price: $200/MWh → $200/MW for discharge
  Reg Up price: $30/MW → $30/MW
  → Discharge into energy market, skip Reg Up

The optimizer solves this EVERY 5 MINUTES across ALL markets.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List


class AncillaryServiceOptimizer:
    """
    Co-optimizes battery dispatch across energy and ancillary services.
    
    Decides how to split battery capacity across:
    - Energy arbitrage (charge/discharge)
    - Reg Up (available to increase output on signal)
    - Reg Down (available to decrease output on signal)
    - RRS (fast frequency response)
    - ECRS (contingency reserve)
    - DRRS (4-hour reliability reserve — new for 2+ hour batteries)
    """
    
    # ERCOT ancillary service requirements
    AS_SPECS = {
        'reg_up': {
            'name': 'Regulation Up',
            'response_time': '4 seconds',
            'duration': '1 hour',
            'min_soc_required': 0.15,  # need charge to deliver
            'description': 'Increase output on AGC signal',
        },
        'reg_down': {
            'name': 'Regulation Down',
            'response_time': '4 seconds',
            'duration': '1 hour',
            'min_headroom_required': 0.15,  # need charging headroom
            'description': 'Decrease output / increase consumption on AGC signal',
        },
        'rrs': {
            'name': 'Responsive Reserve',
            'response_time': '0.5 seconds',
            'duration': '1 hour',
            'min_soc_required': 0.10,
            'description': 'Fast frequency response for grid stability',
        },
        'ecrs': {
            'name': 'ERCOT Contingency Reserve',
            'response_time': '10 minutes',
            'duration': '1 hour',
            'min_soc_required': 0.10,
            'description': 'Backup for contingency events',
        },
        'drrs': {
            'name': 'Dispatchable Reliability Reserve',
            'response_time': '30 minutes',
            'duration': '4 hours',
            'min_soc_required': 0.50,  # need LOTS of charge for 4h
            'description': '4-hour sustained discharge for grid emergencies',
            'premium': True,  # new service, higher value
        },
    }
    
    def __init__(self, battery_config: dict = None):
        self.battery = battery_config or {
            'power_mw': 100,
            'capacity_mwh': 400,
            'duration_hours': 4,  # 400 MWh / 100 MW
            'soc': 0.50,
            'min_soc': 0.05,
            'max_soc': 0.95,
            'rte': 0.87,
        }
        self.allocation_history = []
    
    def optimize(self, energy_price: float, energy_forecast: float,
                 as_prices: dict, hour: int = None) -> dict:
        """
        Solve the co-optimization problem:
        Given current prices for energy and all AS products,
        how should we split our battery capacity?
        
        Returns optimal allocation of MW across all markets.
        """
        soc = self.battery['soc']
        power = self.battery['power_mw']
        capacity = self.battery['capacity_mwh']
        eff = np.sqrt(self.battery['rte'])
        duration = self.battery['duration_hours']
        
        if hour is None:
            hour = datetime.now().hour
        
        # === CALCULATE VALUE OF EACH MARKET ===
        
        market_values = {}
        
        # Energy arbitrage value
        if energy_price > 30 and soc > 0.15:
            energy_discharge_value = energy_price  # $/MW for 1 hour
            market_values['energy_discharge'] = energy_discharge_value
        elif energy_price < 15 and soc < 0.85:
            # Value of charging = expected future discharge price - current charge cost
            charge_value = max(0, energy_forecast - energy_price) * eff
            market_values['energy_charge'] = charge_value
        
        if energy_price < 0:
            # Negative prices: get PAID to charge
            market_values['energy_charge'] = abs(energy_price) + max(0, energy_forecast) * eff
        
        # Reg Up value (need SOC to deliver)
        reg_up_price = as_prices.get('reg_up', 0)
        if reg_up_price > 0 and soc > self.AS_SPECS['reg_up']['min_soc_required']:
            # Reg Up value = clearing price + expected deployment revenue
            # Batteries get deployed ~10-20% of Reg Up hours
            deployment_rate = 0.15
            expected_deployment_rev = energy_price * deployment_rate
            market_values['reg_up'] = reg_up_price + expected_deployment_rev
        
        # Reg Down value (need charging headroom)
        reg_down_price = as_prices.get('reg_down', 0)
        if reg_down_price > 0 and soc < (1 - self.AS_SPECS['reg_down']['min_headroom_required']):
            deployment_rate = 0.15
            # When deployed for Reg Down, you get paid to charge (or reduce discharge)
            expected_deployment_benefit = max(0, energy_forecast - energy_price) * deployment_rate
            market_values['reg_down'] = reg_down_price + expected_deployment_benefit
        
        # RRS value
        rrs_price = as_prices.get('rrs', 0)
        if rrs_price > 0 and soc > self.AS_SPECS['rrs']['min_soc_required']:
            # RRS rarely deploys (<1% of hours) but pays well
            market_values['rrs'] = rrs_price
        
        # ECRS value
        ecrs_price = as_prices.get('ecrs', 0)
        if ecrs_price > 0 and soc > self.AS_SPECS['ecrs']['min_soc_required']:
            market_values['ecrs'] = ecrs_price
        
        # DRRS value (only for 2+ hour batteries)
        drrs_price = as_prices.get('drrs', 0)
        if drrs_price > 0 and duration >= 2 and soc > self.AS_SPECS['drrs']['min_soc_required']:
            # DRRS is premium because few resources can provide 4 hours
            # Must maintain enough SOC to sustain for 4 hours
            market_values['drrs'] = drrs_price * 1.2  # premium multiplier
        
        # === ALLOCATE MW TO HIGHEST-VALUE MARKETS ===
        
        # Sort markets by value (highest first)
        sorted_markets = sorted(market_values.items(), key=lambda x: x[1], reverse=True)
        
        remaining_mw = power
        allocation = {}
        total_expected_revenue = 0
        
        for market, value in sorted_markets:
            if remaining_mw <= 0:
                break
            
            # Determine how much MW to allocate
            if market == 'energy_discharge':
                # Allocate based on confidence and price level
                if energy_price > 100:
                    alloc = remaining_mw  # spike: go all in
                elif energy_price > 50:
                    alloc = remaining_mw * 0.7
                else:
                    alloc = remaining_mw * 0.5
                
                # Cap by available energy
                max_discharge = (soc - self.battery['min_soc']) * capacity * eff
                alloc = min(alloc, max_discharge)
            
            elif market == 'energy_charge':
                if energy_price < 0:
                    alloc = remaining_mw  # negative price: charge everything
                else:
                    alloc = remaining_mw * 0.6
                
                max_charge = (self.battery['max_soc'] - soc) * capacity / eff
                alloc = min(alloc, max_charge)
            
            elif market == 'drrs':
                # DRRS requires sustained delivery — commit carefully
                # Need SOC for 4 hours at committed power
                max_drrs = (soc - 0.10) * capacity / 4  # MW sustainable for 4h
                alloc = min(remaining_mw * 0.4, max_drrs)
            
            else:
                # AS products: typically commit 20-40% of capacity
                alloc = remaining_mw * 0.3
            
            alloc = max(0, round(alloc, 1))
            
            if alloc > 0:
                allocation[market] = {
                    'mw': alloc,
                    'value_per_mw': round(value, 2),
                    'expected_revenue': round(alloc * value * 0.25, 2),  # 15-min interval
                }
                total_expected_revenue += alloc * value * 0.25
                remaining_mw -= alloc
        
        # Anything unallocated stays in HOLD
        if remaining_mw > 0:
            allocation['hold'] = {
                'mw': round(remaining_mw, 1),
                'value_per_mw': 0,
                'expected_revenue': 0,
            }
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'hour': hour,
            'energy_price': energy_price,
            'energy_forecast': energy_forecast,
            'as_prices': as_prices,
            'soc': soc,
            'allocation': allocation,
            'total_expected_revenue': round(total_expected_revenue, 2),
            'market_values': {k: round(v, 2) for k, v in market_values.items()},
            'sorted_markets': [(k, round(v, 2)) for k, v in sorted_markets],
            'primary_market': sorted_markets[0][0] if sorted_markets else 'hold',
        }
        
        self.allocation_history.append(result)
        return result
    
    def revenue_attribution(self) -> dict:
        """Break down revenue by market."""
        if not self.allocation_history:
            return {}
        
        by_market = {}
        for alloc_result in self.allocation_history:
            for market, data in alloc_result['allocation'].items():
                if market not in by_market:
                    by_market[market] = {'total_revenue': 0, 'total_mw_hours': 0, 'intervals': 0}
                by_market[market]['total_revenue'] += data['expected_revenue']
                by_market[market]['total_mw_hours'] += data['mw'] * 0.25
                by_market[market]['intervals'] += 1
        
        return by_market


def demo():
    """Demonstrate ancillary service co-optimization."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Ancillary Service Co-Optimization")
    print("=" * 70)
    print()
    print("  Each MW can only serve ONE market at a time.")
    print("  The optimizer finds the highest-value split every interval.")
    print()
    
    optimizer = AncillaryServiceOptimizer()
    np.random.seed(42)
    
    total_coopt_revenue = 0
    total_energy_only_revenue = 0
    
    print(f"  {'Hour':<6} {'E-Price':>8} {'RegUp':>6} {'RRS':>6} {'DRRS':>6} "
          f"{'Primary':>15} {'Allocation':>40} {'CoOpt$':>8} {'E-Only$':>8}")
    print(f"  {'-'*110}")
    
    for hour in range(24):
        # Simulated prices
        if hour < 6:
            e_price = 42 + np.random.normal(0, 8)
        elif hour < 10:
            e_price = 30 - (hour - 6) * 7 + np.random.normal(0, 5)
        elif hour < 16:
            e_price = 3 + np.random.normal(0, 4)
        elif hour < 20:
            e_price = 25 + (hour - 16) * 12 + np.random.normal(0, 8)
        else:
            e_price = 45 + np.random.normal(0, 10)
        e_price = max(-5, e_price)
        
        e_forecast = e_price * 1.1 + np.random.normal(0, 5)
        
        as_prices = {
            'reg_up': 8 + np.random.uniform(0, 15),
            'reg_down': 4 + np.random.uniform(0, 8),
            'rrs': 5 + np.random.uniform(0, 10),
            'ecrs': 3 + np.random.uniform(0, 5),
            'drrs': 12 + np.random.uniform(0, 15),
        }
        
        result = optimizer.optimize(e_price, e_forecast, as_prices, hour)
        
        coopt_rev = result['total_expected_revenue']
        total_coopt_revenue += coopt_rev
        
        # Energy-only comparison
        if e_price > 30 and optimizer.battery['soc'] > 0.15:
            e_only_rev = e_price * 80 * 0.25  # 80 MW discharge
        elif e_price < 10 and optimizer.battery['soc'] < 0.85:
            e_only_rev = -e_price * 80 * 0.25
        else:
            e_only_rev = 0
        total_energy_only_revenue += e_only_rev
        
        # Format allocation
        alloc_str = ', '.join(f"{m}:{d['mw']:.0f}MW" for m, d in result['allocation'].items() if d['mw'] > 0)
        if len(alloc_str) > 40:
            alloc_str = alloc_str[:37] + '...'
        
        print(f"  {hour:02d}:00  ${e_price:>6.1f}  ${as_prices['reg_up']:>4.1f}  "
              f"${as_prices['rrs']:>4.1f}  ${as_prices['drrs']:>4.1f}  "
              f"{result['primary_market']:>15}  {alloc_str:<40}  "
              f"${coopt_rev:>6.0f}  ${e_only_rev:>6.0f}")
    
    # Revenue attribution
    attribution = optimizer.revenue_attribution()
    
    print(f"\n{'='*70}")
    print("REVENUE ATTRIBUTION BY MARKET")
    print(f"{'='*70}")
    
    print(f"\n  {'Market':<20} {'Revenue':>12} {'MW-Hours':>10} {'Intervals':>10}")
    print(f"  {'-'*55}")
    
    for market, data in sorted(attribution.items(), key=lambda x: x[1]['total_revenue'], reverse=True):
        print(f"  {market:<20} ${data['total_revenue']:>10,.0f}  {data['total_mw_hours']:>8.0f}  {data['intervals']:>8}")
    
    print(f"\n  {'TOTAL CO-OPTIMIZED':>20} ${total_coopt_revenue:>10,.0f}")
    print(f"  {'ENERGY-ONLY':>20} ${total_energy_only_revenue:>10,.0f}")
    
    uplift = total_coopt_revenue - total_energy_only_revenue
    uplift_pct = (uplift / abs(total_energy_only_revenue) * 100) if total_energy_only_revenue != 0 else 0
    
    print(f"\n  Co-optimization uplift: ${uplift:,.0f} ({uplift_pct:+.0f}%)")
    print(f"  Annualized uplift: ${uplift * 365:,.0f}")
    
    print(f"\n{'='*70}")
    print("WHY CO-OPTIMIZATION MATTERS:")
    print(f"{'='*70}")
    print("""
  During low-price hours (midday solar), energy arbitrage earns
  almost nothing. But Reg Up and DRRS still pay $10-25/MW just
  for being AVAILABLE. Co-optimization captures this revenue
  that energy-only strategies leave on the table.

  During price spikes, energy arbitrage dominates and the
  optimizer shifts MW from AS to energy discharge.

  The optimizer dynamically rebalances every 5 minutes based
  on which market is paying the most RIGHT NOW.
  
  Typical uplift from AS co-optimization: 15-40% over energy-only.
""")


if __name__ == '__main__':
    demo()
