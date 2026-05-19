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
  python main.py ancillary      Run ancillary service co-optimization demo
  python main.py notices        Run market notice reader demo
  python main.py ml             Run production ML forecaster demo
  python main.py causal         Run causal reasoning engine demo
  python main.py planning       Run anticipatory planning demo
  python main.py gametheory     Run game theory market awareness demo
  python main.py crossdomain    Run cross-domain synthesis demo
  python main.py selflearn       Run self-directed learning demo
  python main.py strategic       Run strategic positioning demo
  python main.py context         Run context window manager demo
  python main.py orchestrate     Run the full brain (5 ticks demo)
  python main.py ragv2           Run RAG v2 demo
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
    elif command == 'ancillary':
        from core.ancillary_optimizer import demo
        demo()
    elif command == 'notices':
        from agents.notice_reader import demo
        demo()
    elif command == 'ml':
        from models.production_ml import demo
        demo()
    elif command == 'causal':
        from core.causal_engine import demo
        demo()
    elif command == 'planning':
        from core.planning_engine import demo
        demo()
    elif command == 'gametheory':
        from agents.game_theory import demo
        demo()
    elif command == 'crossdomain':
        from agents.cross_domain import demo
        demo()
    elif command == 'orchestrate':
        from core.orchestrator import demo
        demo()
    elif command == 'context':
        from core.context_manager import demo
        demo()
    elif command == 'ragv2':
        from core.rag_engine_v2 import demo
        demo()
    elif command == 'selflearn':
        from agents.self_learning import demo
        demo()
    elif command == 'strategic':
        from core.strategic_engine import demo
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
            'Agents — Notice Reader':     'agents.notice_reader',
            'Models — Ensemble':          'models.ensemble',
            'Models — Probabilistic':     'models.probabilistic',
            'Models — GNN':               'models.gnn',
            'Models — Production ML':     'models.production_ml',
            'Models — Price Forecaster':  'models.price_forecaster',
            'Core — Ancillary Optimizer': 'core.ancillary_optimizer',
            'Core — Causal Engine':       'core.causal_engine',
            'Core — Planning Engine':     'core.planning_engine',
            'Agents — Game Theory':       'agents.game_theory',
            'Agents — Cross-Domain':      'agents.cross_domain',
            'Agents — Self-Learning':     'agents.self_learning',
            'Core — Strategic Engine':    'core.strategic_engine',
            'Core — Context Manager':    'core.context_manager',
            'Core — Orchestrator':       'core.orchestrator',
            'Core — RAG Engine':         'core.rag_engine',
            'Core — RAG Engine v2':      'core.rag_engine_v2',
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
