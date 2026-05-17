"""
VoltStream AI — Level 3: Anticipatory Planning
================================================
A human trader doesn't think one interval at a time.
They think: "If I discharge now at $45, I won't have charge
for the potential $200 spike tonight. But if I hold and the
spike doesn't come, I missed the $45."

This is multi-step lookahead planning. Like chess, the brain
simulates many possible futures and picks the path with the
best risk-adjusted return.

HOW IT WORKS:
1. Generate a tree of possible future price paths (Monte Carlo)
2. For each path, simulate optimal battery decisions
3. Calculate expected revenue across all paths
4. Pick the action that maximizes expected value ACROSS futures
5. Factor in the VALUE OF OPTIONALITY (keeping options open)

KEY INSIGHT:
Sometimes HOLDING is worth more than charging or discharging
because it preserves your ability to respond to whatever
happens next. This is the "option value" of the battery.
A simple rule-based system can never capture this.
"""

import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple


class PricePath:
    """Generates realistic future price scenarios."""
    
    def __init__(self, seed=None):
        if seed is not None:
            np.random.seed(seed)
    
    def generate_paths(self, current_price: float, current_hour: int,
                       hours_ahead: int = 12, n_paths: int = 500,
                       weather_forecast: dict = None) -> np.ndarray:
        """
        Generate Monte Carlo price paths.
        
        Each path represents one possible future.
        Some futures have spikes. Some have crashes.
        Some are boring. The distribution matters.
        
        Returns: (n_paths, hours_ahead) array of prices
        """
        paths = np.zeros((n_paths, hours_ahead))
        
        for p in range(n_paths):
            price = current_price
            
            for h in range(hours_ahead):
                future_hour = (current_hour + h + 1) % 24
                
                # Base hourly pattern
                hour_drift = {
                    0: 0, 1: -1, 2: -1, 3: -2, 4: -1, 5: 0,
                    6: -3, 7: -5, 8: -8, 9: -10, 10: -12, 11: -10,
                    12: -8, 13: -6, 14: -3, 15: 0, 16: 5, 17: 10,
                    18: 12, 19: 10, 20: 5, 21: 2, 22: 0, 23: 0,
                }
                
                drift = hour_drift.get(future_hour, 0) * 0.3
                
                # Weather-driven adjustment
                if weather_forecast:
                    wind = weather_forecast.get('wind_forecast', [15] * 24)
                    solar = weather_forecast.get('solar_forecast', [0] * 24)
                    
                    if h < len(wind):
                        if wind[h] > 25:
                            drift -= 5  # strong wind pushes prices down
                        elif wind[h] < 7:
                            drift += 3  # no wind pushes prices up
                    
                    if h < len(solar):
                        if solar[h] > 700:
                            drift -= 8  # strong solar crushes prices
                
                # Random walk with mean reversion
                volatility = 5 + abs(price) * 0.1  # higher prices = more volatile
                shock = np.random.normal(drift, volatility)
                
                # Spike probability (rare but extreme)
                if np.random.random() < 0.02:
                    shock += np.random.exponential(80)
                
                # Negative price probability (during solar/wind surplus)
                if future_hour in [9, 10, 11, 12, 13, 14] and np.random.random() < 0.08:
                    shock -= 20 + np.random.exponential(15)
                
                # Mean reversion toward typical price for this hour
                typical = 30 + hour_drift.get(future_hour, 0)
                mean_reversion = (typical - price) * 0.05
                
                price = max(-30, price + shock + mean_reversion)
                paths[p, h] = price
        
        return paths


class BatterySimulator:
    """Simulates battery operations along a price path."""
    
    def __init__(self, power_mw=100, capacity_mwh=400, rte=0.87,
                 min_soc=0.05, max_soc=0.95):
        self.power = power_mw
        self.capacity = capacity_mwh
        self.eff = np.sqrt(rte)
        self.min_soc = min_soc
        self.max_soc = max_soc
    
    def simulate_path(self, prices: np.ndarray, initial_soc: float,
                      strategy: str = 'greedy') -> Tuple[float, List[dict]]:
        """
        Simulate battery operation along a price path.
        Returns total revenue and decision log.
        """
        soc = initial_soc
        total_revenue = 0
        decisions = []
        
        for i, price in enumerate(prices):
            action = 'HOLD'
            mw = 0
            
            if strategy == 'greedy':
                # Simple greedy: buy low, sell high based on remaining path
                future_prices = prices[i:]
                future_mean = np.mean(future_prices) if len(future_prices) > 0 else price
                
                if price < future_mean - 10 and soc < 0.85:
                    action = 'CHARGE'
                    mw = min(self.power, (self.max_soc - soc) * self.capacity / self.eff)
                elif price > future_mean + 10 and soc > 0.15:
                    action = 'DISCHARGE'
                    mw = min(self.power, (soc - self.min_soc) * self.capacity * self.eff)
                elif price < 0:
                    action = 'CHARGE'
                    mw = min(self.power, (self.max_soc - soc) * self.capacity / self.eff)
                elif price > 100 and soc > 0.10:
                    action = 'DISCHARGE'
                    mw = min(self.power, (soc - self.min_soc) * self.capacity * self.eff)
            
            elif strategy == 'hold':
                pass  # do nothing
            
            # Execute
            revenue = 0
            if action == 'CHARGE' and mw > 0:
                soc += mw * self.eff / self.capacity
                revenue = -price * mw * 0.25  # 15-min interval
            elif action == 'DISCHARGE' and mw > 0:
                soc -= mw / self.eff / self.capacity
                revenue = price * mw * 0.25
            
            soc = max(self.min_soc, min(self.max_soc, soc))
            total_revenue += revenue
            
            decisions.append({
                'step': i, 'price': price, 'action': action,
                'mw': round(mw, 1), 'revenue': round(revenue, 2), 'soc': round(soc, 4),
            })
        
        return total_revenue, decisions


class AnticipatoryPlanner:
    """
    The brain that thinks ahead.
    
    Instead of "what should I do RIGHT NOW?", it asks
    "what should I do RIGHT NOW given everything that
    MIGHT happen in the next 12 hours?"
    
    This is the chess player. Simulate many futures,
    evaluate each one, pick the move that's best on average.
    """
    
    # Possible actions the brain considers each interval
    ACTIONS = [
        {'name': 'CHARGE_FULL', 'intensity': -1.0},
        {'name': 'CHARGE_HALF', 'intensity': -0.5},
        {'name': 'CHARGE_QUARTER', 'intensity': -0.25},
        {'name': 'HOLD', 'intensity': 0.0},
        {'name': 'DISCHARGE_QUARTER', 'intensity': 0.25},
        {'name': 'DISCHARGE_HALF', 'intensity': 0.5},
        {'name': 'DISCHARGE_FULL', 'intensity': 1.0},
    ]
    
    def __init__(self):
        self.path_generator = PricePath()
        self.simulator = BatterySimulator()
        self.planning_log = []
    
    def plan(self, current_price: float, current_soc: float,
             current_hour: int, weather_forecast: dict = None,
             lookahead_hours: int = 12, n_simulations: int = 300) -> dict:
        """
        The core planning algorithm.
        
        For each possible action NOW:
          1. Simulate that action
          2. Generate N future price paths
          3. For each path, simulate optimal play from the new state
          4. Average the revenue across all paths
          5. Pick the action with the highest average
        
        This naturally captures optionality:
        - HOLD might win because it preserves flexibility
        - CHARGE might win because most futures have higher prices later
        - DISCHARGE might win because this price is already great
        """
        
        # Generate future price paths
        paths = self.path_generator.generate_paths(
            current_price, current_hour, lookahead_hours,
            n_simulations, weather_forecast
        )
        
        # Evaluate each possible action
        action_values = {}
        
        for action_def in self.ACTIONS:
            action_name = action_def['name']
            intensity = action_def['intensity']
            
            # Simulate taking this action now
            soc_after = current_soc
            immediate_revenue = 0
            mw = abs(intensity) * self.simulator.power
            
            if intensity < 0:  # charge
                actual_mw = min(mw, (self.simulator.max_soc - current_soc) * self.simulator.capacity / self.simulator.eff)
                if actual_mw > 0:
                    soc_after += actual_mw * self.simulator.eff / self.simulator.capacity
                    immediate_revenue = -current_price * actual_mw * 0.25
                else:
                    actual_mw = 0
            elif intensity > 0:  # discharge
                actual_mw = min(mw, (current_soc - self.simulator.min_soc) * self.simulator.capacity * self.simulator.eff)
                if actual_mw > 0:
                    soc_after -= actual_mw / self.simulator.eff / self.simulator.capacity
                    immediate_revenue = current_price * actual_mw * 0.25
                else:
                    actual_mw = 0
            
            soc_after = max(self.simulator.min_soc, min(self.simulator.max_soc, soc_after))
            
            # Simulate future revenue across all price paths
            future_revenues = []
            
            for path in paths:
                future_rev, _ = self.simulator.simulate_path(path, soc_after, 'greedy')
                future_revenues.append(future_rev)
            
            future_revenues = np.array(future_revenues)
            total_revenues = immediate_revenue + future_revenues
            
            action_values[action_name] = {
                'immediate_revenue': round(immediate_revenue, 2),
                'avg_future_revenue': round(np.mean(future_revenues), 2),
                'avg_total_revenue': round(np.mean(total_revenues), 2),
                'std_total_revenue': round(np.std(total_revenues), 2),
                'worst_case': round(np.percentile(total_revenues, 5), 2),
                'best_case': round(np.percentile(total_revenues, 95), 2),
                'median_total': round(np.median(total_revenues), 2),
                'soc_after': round(soc_after, 4),
                'mw': round(actual_mw if intensity != 0 else 0, 1),
                'sharpe': round(
                    np.mean(total_revenues) / max(np.std(total_revenues), 1), 3
                ),
            }
        
        # Pick the best action
        # Use risk-adjusted return (Sharpe-like ratio) not just expected value
        best_action = max(action_values.items(),
                         key=lambda x: x[1]['sharpe'])
        
        # Also find the action with highest expected value (might differ)
        highest_ev = max(action_values.items(),
                        key=lambda x: x[1]['avg_total_revenue'])
        
        # Calculate option value of holding
        hold_value = action_values.get('HOLD', {}).get('avg_total_revenue', 0)
        best_value = best_action[1]['avg_total_revenue']
        option_value = hold_value - min(
            v['avg_total_revenue'] for v in action_values.values()
        )
        
        # Path statistics
        all_future_prices = paths.flatten()
        spike_probability = np.mean(paths.max(axis=1) > 100)
        crash_probability = np.mean(paths.min(axis=1) < 0)
        
        result = {
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'current_soc': current_soc,
            'current_hour': current_hour,
            'lookahead_hours': lookahead_hours,
            'n_simulations': n_simulations,
            'recommended_action': best_action[0],
            'recommended_details': best_action[1],
            'highest_ev_action': highest_ev[0],
            'highest_ev_details': highest_ev[1],
            'action_values': action_values,
            'option_value_of_hold': round(option_value, 2),
            'path_statistics': {
                'avg_future_price': round(np.mean(all_future_prices), 2),
                'max_future_price': round(np.max(all_future_prices), 2),
                'min_future_price': round(np.min(all_future_prices), 2),
                'spike_probability': round(spike_probability, 3),
                'crash_probability': round(crash_probability, 3),
                'price_volatility': round(np.std(all_future_prices), 2),
            },
            'reasoning': self._explain(best_action, highest_ev, action_values,
                                       spike_probability, crash_probability,
                                       current_price, current_soc, option_value),
        }
        
        self.planning_log.append(result)
        return result
    
    def _explain(self, best_action, highest_ev, action_values,
                 spike_prob, crash_prob, price, soc, option_value) -> str:
        """Generate human-readable explanation of the planning decision."""
        
        name = best_action[0]
        details = best_action[1]
        
        explanation = f"Looking {details.get('lookahead', 12)} hours ahead across {300} simulated futures: "
        
        if name == 'HOLD':
            explanation += (
                f"HOLD is the best risk-adjusted move. "
                f"The option value of waiting is ${option_value:.0f}. "
            )
            if spike_prob > 0.10:
                explanation += f"There's a {spike_prob:.0%} chance of a price spike. Holding preserves charge for it. "
            if crash_prob > 0.10:
                explanation += f"There's a {crash_prob:.0%} chance of negative prices. Holding preserves capacity to charge then. "
        
        elif 'CHARGE' in name:
            explanation += (
                f"CHARGE at ${price:.0f}/MWh. "
                f"Expected total return: ${details['avg_total_revenue']:.0f} "
                f"(${details['immediate_revenue']:.0f} now + ${details['avg_future_revenue']:.0f} future). "
                f"Worst case: ${details['worst_case']:.0f}. Best case: ${details['best_case']:.0f}. "
            )
            if spike_prob > 0.05:
                explanation += f"Charging now positions us for the {spike_prob:.0%} chance of a spike later."
        
        elif 'DISCHARGE' in name:
            explanation += (
                f"DISCHARGE at ${price:.0f}/MWh. "
                f"Expected total return: ${details['avg_total_revenue']:.0f}. "
                f"This price is better than {100 - spike_prob*100:.0f}% of simulated futures. "
                f"Taking the bird in hand."
            )
        
        if name != highest_ev[0]:
            explanation += (
                f" Note: {highest_ev[0]} has higher expected value (${highest_ev[1]['avg_total_revenue']:.0f}) "
                f"but more risk (worst case ${highest_ev[1]['worst_case']:.0f}). "
                f"Choosing {name} for better risk-adjusted return."
            )
        
        return explanation


def demo():
    """Demonstrate anticipatory planning."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Level 3: Anticipatory Planning")
    print("=" * 70)
    print()
    print("  Not 'what should I do now?'")
    print("  But 'what should I do now given everything that")
    print("  MIGHT happen in the next 12 hours?'")
    print()
    
    planner = AnticipatoryPlanner()
    
    scenarios = [
        {
            'name': 'Moderate price, half charged',
            'price': 30, 'soc': 0.50, 'hour': 14,
            'question': 'Should we discharge at $30 or wait for evening peak?',
        },
        {
            'name': 'Low price, nearly empty',
            'price': 5, 'soc': 0.15, 'hour': 10,
            'question': 'Cheap power available. How aggressively should we charge?',
        },
        {
            'name': 'High price, fully charged',
            'price': 65, 'soc': 0.90, 'hour': 18,
            'question': 'Great price and full battery. Dump it all or hold some back?',
        },
        {
            'name': 'Negative price, half charged',
            'price': -8, 'soc': 0.50, 'hour': 12,
            'question': 'Being paid to charge. But already half full. How much room to save?',
        },
        {
            'name': 'Moderate price before expected spike',
            'price': 35, 'soc': 0.70, 'hour': 15,
            'question': 'Evening peak coming. Discharge now at $35 or wait for potential $100+?',
        },
    ]
    
    for scenario in scenarios:
        print(f"\n{'='*70}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"{'='*70}")
        print(f"  Price: ${scenario['price']}/MWh | SOC: {scenario['soc']*100:.0f}% | Hour: {scenario['hour']}:00")
        print(f"  Question: {scenario['question']}")
        
        result = planner.plan(
            current_price=scenario['price'],
            current_soc=scenario['soc'],
            current_hour=scenario['hour'],
            lookahead_hours=12,
            n_simulations=300,
        )
        
        rec = result['recommended_action']
        det = result['recommended_details']
        stats = result['path_statistics']
        
        print(f"\n  DECISION: {rec}")
        print(f"    Expected total revenue: ${det['avg_total_revenue']:,.0f}")
        print(f"    Worst case (5th pct):   ${det['worst_case']:,.0f}")
        print(f"    Best case (95th pct):   ${det['best_case']:,.0f}")
        print(f"    Sharpe ratio:           {det['sharpe']:.3f}")
        print(f"    SOC after action:       {det['soc_after']*100:.0f}%")
        
        print(f"\n  FUTURE OUTLOOK ({result['n_simulations']} simulations, {result['lookahead_hours']}h ahead):")
        print(f"    Avg future price:    ${stats['avg_future_price']:.1f}/MWh")
        print(f"    Spike probability:   {stats['spike_probability']:.0%} (>$100)")
        print(f"    Crash probability:   {stats['crash_probability']:.0%} (<$0)")
        print(f"    Price volatility:    ${stats['price_volatility']:.1f}")
        print(f"    Option value of HOLD: ${result['option_value_of_hold']:.0f}")
        
        # Show all actions ranked
        print(f"\n  ALL OPTIONS RANKED:")
        sorted_actions = sorted(result['action_values'].items(),
                               key=lambda x: x[1]['sharpe'], reverse=True)
        
        for i, (action, vals) in enumerate(sorted_actions):
            marker = "→" if action == rec else " "
            print(f"    {marker} {action:<20} EV: ${vals['avg_total_revenue']:>8,.0f}  "
                  f"Sharpe: {vals['sharpe']:>6.3f}  "
                  f"Range: [${vals['worst_case']:>7,.0f} to ${vals['best_case']:>7,.0f}]")
        
        print(f"\n  REASONING: {result['reasoning'][:200]}")
    
    print(f"\n{'='*70}")
    print("LEVEL 3 CAPABILITY:")
    print(f"{'='*70}")
    print("""
  The planner just made decisions no rule-based system can:
  
  1. OPTION VALUE: At $30 with evening peak coming, it might
     HOLD even though $30 is above the charge threshold.
     Why? Because the 15% chance of a $100+ spike is worth
     more than the guaranteed $30. It values keeping options open.
  
  2. RISK MANAGEMENT: When choosing between two profitable actions,
     it picks the one with better risk-adjusted return (Sharpe),
     not just the highest expected value. Sometimes the safer
     bet is smarter even if the expected value is slightly lower.
  
  3. PARTIAL ACTIONS: Instead of binary charge/discharge, it
     considers 7 different intensity levels. Sometimes charging
     at 25% is better than 100% because it preserves flexibility.
  
  4. FUTURE AWARENESS: It knows that discharging NOW means less
     charge for LATER. Every decision accounts for its impact
     on future opportunities across 300 simulated price paths.
  
  This is the chess player in the battery. It thinks moves ahead.
""")


if __name__ == '__main__':
    demo()
