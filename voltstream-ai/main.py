#!/usr/bin/env python3
"""
VoltStream AI — Autonomous Battery Dispatch for ERCOT
======================================================

Usage:
  python main.py demo           Run 24h multi-agent demo
  python main.py live           Run live service (real ERCOT data)
  python main.py train          Train the RL dispatch agent
  python main.py weather        Pull and analyze ERCOT weather
  python main.py gnn            Run nodal price analysis
  python main.py ensemble       Run ensemble forecast demo
  python main.py probabilistic  Run probabilistic forecast demo
  python main.py memory         Run persistent memory demo
  python main.py status         Check all modules
"""

import sys
import os

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1].lower()

    if command == 'demo':
        from agents.multi_agent import demo
        demo()
    elif command == 'live':
        from core.cloud_service import VoltStreamService
        service = VoltStreamService()
        service.run_simple()
    elif command == 'train':
        from agents.rl_agent import ERCOTEnvironment, RLDispatchAgent
        env = ERCOTEnvironment()
        agent = RLDispatchAgent(state_size=8, n_actions=11, hidden_size=64, learning_rate=0.0005)
        agent.train(env, n_episodes=200, max_steps_per_episode=720)
        agent.evaluate(env, n_hours=720)
        agent.save('models/rl_dispatch_model.json')
    elif command == 'weather':
        from data.multi_weather import demo
        demo()
    elif command == 'gnn':
        from models.gnn import demo
        demo()
    elif command == 'ensemble':
        from models.ensemble import demo
        demo()
    elif command == 'probabilistic':
        from models.probabilistic import demo
        demo()
    elif command == 'memory':
        from agents.memory import demo
        demo()
    elif command == 'status':
        print("⚡ VoltStream AI — System Status")
        print("=" * 50)
        modules = {
            'Core — Hybrid Engine':       'core.hybrid_engine',
            'Core — Cloud Service':       'core.cloud_service',
            'Core — Optimizer':           'core.optimizer',
            'Agents — Multi-Agent':       'agents.multi_agent',
            'Agents — RL Agent':          'agents.rl_agent',
            'Agents — Memory':            'agents.memory',
            'Models — Ensemble':          'models.ensemble',
            'Models — Probabilistic':     'models.probabilistic',
            'Models — GNN':               'models.gnn',
            'Models — Price Forecaster':  'models.price_forecaster',
            'Data — Weather Engine':      'data.weather_engine',
            'Data — Multi-Weather':       'data.multi_weather',
            'Data — ERCOT Generator':     'data.ercot_generator',
        }
        for name, module in modules.items():
            try:
                __import__(module)
                print(f"  ✓ {name}")
            except Exception as e:
                print(f"  ✗ {name} — {e}")

        if os.path.exists('models/rl_dispatch_model.json'):
            print(f"\n  RL Model: trained ✓")
        else:
            print(f"\n  RL Model: not trained (run: python main.py train)")

        if os.environ.get('ANTHROPIC_API_KEY'):
            print(f"  Claude API: configured ✓")
        else:
            print(f"  Claude API: not set (set ANTHROPIC_API_KEY for reasoning layer)")
        print()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)

if __name__ == '__main__':
    main()
