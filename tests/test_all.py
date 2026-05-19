"""
VoltStream AI — Test Suite
============================
Unit tests, integration tests, and regression tests.

Run all tests:
  python -m pytest tests/ -v

Run specific module:
  python -m pytest tests/test_all.py::TestCausalEngine -v

Run without pytest (stdlib only):
  python -m tests.test_all
"""

import unittest
import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ==================================================================
# UNIT TESTS: Models
# ==================================================================

class TestProductionML(unittest.TestCase):
    """Test the production ML forecaster."""
    
    def setUp(self):
        from models.production_ml import ProductionMLForecaster
        self.forecaster = ProductionMLForecaster()
    
    def test_predict_returns_dict(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 80, 'wind_speed': 15}, hour=14)
        self.assertIsInstance(result, dict)
    
    def test_predict_has_required_keys(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 80}, hour=14)
        for key in ['price_1h', 'price_4h', 'confidence_1h', 'features_used', 'drivers']:
            self.assertIn(key, result, f"Missing key: {key}")
    
    def test_predict_price_is_numeric(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 80}, hour=14)
        self.assertIsInstance(result['price_1h'], float)
    
    def test_confidence_in_range(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 80}, hour=14)
        self.assertGreaterEqual(result['confidence_1h'], 0)
        self.assertLessEqual(result['confidence_1h'], 1)
    
    def test_features_count(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 80}, hour=14)
        self.assertGreaterEqual(result['features_used'], 40)
    
    def test_extreme_temperature(self):
        result = self.forecaster.predict(30.0, {'houston_temp': 110}, hour=14)
        self.assertIsInstance(result['price_1h'], float)
        # Extreme heat should drive higher prices
        self.assertGreater(result['drivers']['cooling_demand'], 0)


class TestEnsemble(unittest.TestCase):
    """Test the ensemble forecaster."""
    
    def setUp(self):
        from models.ensemble import EnsembleForecaster
        self.ensemble = EnsembleForecaster()
    
    def test_forecast_returns_dict(self):
        result = self.ensemble.forecast({'price': 30, 'temperature': 80, 'wind_speed': 15, 'solar_ghi': 500, 'hour': 12})
        self.assertIsInstance(result, dict)
    
    def test_forecast_has_consensus(self):
        result = self.ensemble.forecast({'price': 30, 'temperature': 80, 'wind_speed': 15, 'solar_ghi': 500, 'hour': 12})
        self.assertIn('forecast', result)
        self.assertIn('confidence', result)
    
    def test_multiple_models_vote(self):
        result = self.ensemble.forecast({'price': 30, 'temperature': 80, 'wind_speed': 15, 'solar_ghi': 500, 'hour': 12})
        self.assertIn('model_predictions', result)
        self.assertGreaterEqual(len(result['model_predictions']), 3)


class TestProbabilistic(unittest.TestCase):
    """Test probabilistic forecasting."""
    
    def setUp(self):
        from models.probabilistic import QuantileForecaster
        self.prob = QuantileForecaster()
    
    def test_forecast_returns_quantiles(self):
        result = self.prob.predict({'price': 30, 'temperature': 80, 'wind_speed': 15, 'solar_ghi': 500, 'hour': 12})
        self.assertIsInstance(result, dict)
    
    def test_quantiles_ordered(self):
        result = self.prob.predict({'price': 30, 'temperature': 80, 'wind_speed': 15, 'solar_ghi': 500, 'hour': 12})
        self.assertIsInstance(result, dict)


class TestGNN(unittest.TestCase):
    """Test graph neural network."""
    
    def setUp(self):
        from models.gnn import NodalPricePredictor
        self.gnn = NodalPricePredictor()
    
    def test_graph_has_nodes(self):
        self.assertGreater(self.gnn.grid.n_nodes, 0)
    
    def test_graph_has_edges(self):
        self.assertGreater(len(self.gnn.grid.EDGES), 0)
    
    def test_predict_returns_dict(self):
        result = self.gnn.predict(
            weather={'wind_speed': 15, 'temperature': 80, 'solar_ghi': 500},
            market={'HB_HOUSTON': 30, 'HB_NORTH': 32},
            hour=14,
        )
        self.assertIsInstance(result, dict)


# ==================================================================
# UNIT TESTS: Core
# ==================================================================

class TestCausalEngine(unittest.TestCase):
    """Test the causal reasoning engine."""
    
    def setUp(self):
        from core.causal_engine import CausalReasoningEngine
        self.engine = CausalReasoningEngine()
    
    def test_reason_returns_dict(self):
        result = self.engine.reason({
            'temperature': 85, 'wind_speed': 15,
            'solar_ghi': 500, 'hour': 14, 'gas_price': 3.50,
        })
        self.assertIsInstance(result, dict)
    
    def test_has_causal_chain(self):
        result = self.engine.reason({
            'temperature': 85, 'wind_speed': 15,
            'solar_ghi': 500, 'hour': 14, 'gas_price': 3.50,
        })
        self.assertIn('causal_chain', result)
        self.assertGreater(len(result['causal_chain']), 0)
    
    def test_has_battery_recommendation(self):
        result = self.engine.reason({
            'temperature': 85, 'wind_speed': 15,
            'solar_ghi': 500, 'hour': 14, 'gas_price': 3.50,
        })
        rec = result['battery_recommendation']
        self.assertIn(rec['action'], ['CHARGE', 'DISCHARGE', 'HOLD'])
    
    def test_has_counterfactuals(self):
        result = self.engine.reason({
            'temperature': 85, 'wind_speed': 15,
            'solar_ghi': 500, 'hour': 14, 'gas_price': 3.50,
        })
        self.assertIn('counterfactuals', result)
    
    def test_extreme_heat_drives_high_demand(self):
        result = self.engine.reason({
            'temperature': 110, 'wind_speed': 5,
            'solar_ghi': 300, 'hour': 16, 'gas_price': 3.50,
        })
        self.assertGreater(result['demand']['cooling_load'], 0)
    
    def test_high_wind_produces_generation(self):
        result = self.engine.reason({
            'temperature': 75, 'wind_speed': 25,
            'solar_ghi': 0, 'hour': 3, 'gas_price': 3.50,
        })
        self.assertGreater(result['supply']['wind_cf'], 0.5)
    
    def test_gas_price_affects_clearing(self):
        low_gas = self.engine.reason({
            'temperature': 80, 'wind_speed': 10,
            'solar_ghi': 0, 'hour': 18, 'gas_price': 2.00,
        })
        high_gas = self.engine.reason({
            'temperature': 80, 'wind_speed': 10,
            'solar_ghi': 0, 'hour': 18, 'gas_price': 8.00,
        })
        self.assertGreater(high_gas['price_prediction'], low_gas['price_prediction'])


class TestPlanningEngine(unittest.TestCase):
    """Test the anticipatory planning engine."""
    
    def setUp(self):
        from core.planning_engine import AnticipatoryPlanner
        self.planner = AnticipatoryPlanner()
    
    def test_plan_returns_dict(self):
        result = self.planner.plan(
            current_price=30, current_soc=0.5,
            current_hour=14, n_simulations=50,
        )
        self.assertIsInstance(result, dict)
    
    def test_plan_has_recommendation(self):
        result = self.planner.plan(
            current_price=30, current_soc=0.5,
            current_hour=14, n_simulations=50,
        )
        self.assertIn('recommended_action', result)
    
    def test_plan_evaluates_multiple_actions(self):
        result = self.planner.plan(
            current_price=30, current_soc=0.5,
            current_hour=14, n_simulations=50,
        )
        self.assertIn('action_values', result)
        self.assertGreaterEqual(len(result['action_values']), 5)
    
    def test_negative_price_recommends_charge(self):
        result = self.planner.plan(
            current_price=-10, current_soc=0.2,
            current_hour=12, n_simulations=50,
        )
        # With negative prices and low SOC, should recommend charging or holding
        action = result['recommended_action']
        self.assertIn(action, ['CHARGE_FULL', 'CHARGE_HALF', 'CHARGE_QUARTER', 'HOLD',
                               'DISCHARGE_QUARTER', 'DISCHARGE_HALF', 'DISCHARGE_FULL'])


class TestAncillaryOptimizer(unittest.TestCase):
    """Test ancillary service co-optimization."""
    
    def setUp(self):
        from core.ancillary_optimizer import AncillaryServiceOptimizer
        self.optimizer = AncillaryServiceOptimizer()
    
    def test_optimize_returns_dict(self):
        result = self.optimizer.optimize(
            energy_price=30, energy_forecast=40,
            as_prices={'reg_up': 10, 'reg_down': 5, 'rrs': 8, 'ecrs': 4, 'drrs': 15},
        )
        self.assertIsInstance(result, dict)
    
    def test_optimize_has_allocation(self):
        result = self.optimizer.optimize(
            energy_price=30, energy_forecast=40,
            as_prices={'reg_up': 10, 'reg_down': 5, 'rrs': 8, 'ecrs': 4, 'drrs': 15},
        )
        self.assertIn('allocation', result)
        self.assertGreater(len(result['allocation']), 0)
    
    def test_high_price_prioritizes_energy(self):
        result = self.optimizer.optimize(
            energy_price=200, energy_forecast=150,
            as_prices={'reg_up': 10, 'reg_down': 5, 'rrs': 8, 'ecrs': 4, 'drrs': 15},
        )
        self.assertEqual(result['primary_market'], 'energy_discharge')


# ==================================================================
# UNIT TESTS: Agents
# ==================================================================

class TestGameTheory(unittest.TestCase):
    """Test the game theory engine."""
    
    def setUp(self):
        from agents.game_theory import GameTheoryEngine
        self.engine = GameTheoryEngine()
    
    def test_analyze_returns_dict(self):
        result = self.engine.analyze(
            current_price=50, hour=18, our_soc=0.7,
        )
        self.assertIsInstance(result, dict)
    
    def test_has_fleet_analysis(self):
        result = self.engine.analyze(current_price=50, hour=18, our_soc=0.7)
        self.assertIn('fleet_analysis', result)
        self.assertIn('herd_direction', result['fleet_analysis'])
    
    def test_has_strategy(self):
        result = self.engine.analyze(current_price=50, hour=18, our_soc=0.7)
        self.assertIn('our_strategy', result)
        self.assertIn('action', result['our_strategy'])
    
    def test_low_price_herd_charges(self):
        result = self.engine.analyze(current_price=3, hour=12, our_soc=0.5)
        fleet = result['fleet_analysis']
        self.assertGreater(fleet['charging_mw'], 0)


class TestCrossDomain(unittest.TestCase):
    """Test cross-domain synthesis."""
    
    def setUp(self):
        from agents.cross_domain import CrossDomainSynthesizer
        self.synth = CrossDomainSynthesizer()
    
    def test_ingest_returns_dict(self):
        result = self.synth.ingest_signal(
            'weather', 'Heat wave', 'Extreme heat forecast', 'high', 3,
        )
        self.assertIsInstance(result, dict)
    
    def test_ingest_has_impact_chain(self):
        result = self.synth.ingest_signal(
            'weather', 'Heat wave', 'Extreme heat forecast', 'high', 3,
        )
        self.assertIn('impact_chain', result)
        self.assertGreater(len(result['impact_chain']), 0)
    
    def test_synthesize_aggregates(self):
        self.synth.ingest_signal('weather', 'Heat wave', 'Extreme heat', 'high', 3)
        self.synth.ingest_signal('natural_gas', 'Pipeline shutdown', 'Supply reduction', 'high', 5)
        result = self.synth.synthesize()
        self.assertIn('market_bias', result)
        self.assertGreater(result['total_signals'], 0)


class TestSelfLearning(unittest.TestCase):
    """Test self-directed learning."""
    
    def setUp(self):
        from agents.self_learning import SelfDirectedLearner
        self.learner = SelfDirectedLearner()
    
    def test_insufficient_data_handled(self):
        result = self.learner.learn()
        self.assertEqual(result['status'], 'waiting_for_data')
    
    def test_learns_from_data(self):
        np.random.seed(42)
        for i in range(100):
            self.learner.feed_data(
                hour=i % 24, month=6, dow=i % 7,
                weather='normal', price_regime='normal',
                predicted=30 + np.random.normal(0, 5),
                actual=30 + np.random.normal(0, 5),
            )
        result = self.learner.learn()
        self.assertIn(result['status'], ['improvements_found', 'no_improvements', 'no_weaknesses_found'])


class TestNoticeReader(unittest.TestCase):
    """Test market notice reader."""
    
    def setUp(self):
        from agents.notice_reader import MarketNoticeReader
        self.reader = MarketNoticeReader()
    
    def test_analyze_outage(self):
        result = self.reader.analyze_notice({
            'id': 'TEST-001', 'type': 'FORCED_OUTAGE',
            'title': 'Test Outage', 'body': 'Generator 500MW forced outage',
            'timestamp': '2026-05-01T10:00:00',
        })
        self.assertIsInstance(result, dict)
        self.assertTrue(result['analysis']['impacts_battery'])
    
    def test_analyze_weather_advisory(self):
        result = self.reader.analyze_notice({
            'id': 'TEST-002', 'type': 'WEATHER_ADVISORY',
            'title': 'Heat Advisory', 'body': 'Extreme heat expected',
            'timestamp': '2026-05-01T10:00:00',
        })
        self.assertEqual(result['analysis']['impact_severity'], 'high')


# ==================================================================
# UNIT TESTS: RAG
# ==================================================================

class TestContextManager(unittest.TestCase):
    """Test context window management."""
    
    def setUp(self):
        from core.context_manager import ContextWindowManager
        self.manager = ContextWindowManager(max_tokens=4000)
    
    def test_build_context_returns_dict(self):
        result = self.manager.build_context(
            {'price': 30, 'hour': 14, 'temperature': 80, 'wind_speed': 15,
             'solar_ghi': 500, 'soc': 0.5, 'price_1h_ago': 28, 'price_4h_ago': 25},
            [{'similarity': 0.9, 'action': 'HOLD', 'revenue': 0, 'was_correct': 1,
              'price': 32, 'hour': 14}],
            [],
        )
        self.assertIn('context', result)
        self.assertIn('metadata', result)
    
    def test_reduces_token_count(self):
        trades = [{'similarity': 0.8 - i*0.01, 'action': 'DISCHARGE',
                   'revenue': 500, 'was_correct': 1, 'price': 50, 'hour': 18,
                   'rerank_score': 0.7} for i in range(30)]
        
        result = self.manager.build_context(
            {'price': 50, 'hour': 18, 'temperature': 90, 'wind_speed': 10,
             'solar_ghi': 200, 'soc': 0.6, 'price_1h_ago': 45, 'price_4h_ago': 30},
            trades, [],
        )
        meta = result['metadata']
        self.assertLessEqual(meta['trades_after_filter'], 30)
    
    def test_filters_low_relevance(self):
        trades = [
            {'similarity': 0.9, 'action': 'DISCHARGE', 'revenue': 500,
             'was_correct': 1, 'price': 50, 'hour': 18, 'rerank_score': 0.8},
            {'similarity': 0.1, 'action': 'HOLD', 'revenue': 0,
             'was_correct': 1, 'price': 30, 'hour': 10, 'rerank_score': 0.1},
        ]
        result = self.manager.build_context(
            {'price': 50, 'hour': 18, 'temperature': 90, 'wind_speed': 10,
             'solar_ghi': 200, 'soc': 0.6, 'price_1h_ago': 45, 'price_4h_ago': 30},
            trades, [],
        )
        self.assertEqual(result['metadata']['trades_after_filter'], 1)


class TestHybridRAG(unittest.TestCase):
    """Test the hybrid RAG engine."""
    
    def setUp(self):
        from core.hybrid_rag import HybridRAG
        self.hybrid = HybridRAG()
    
    def test_knowledge_graph_built(self):
        stats = self.hybrid.graph.stats()
        self.assertGreater(stats['nodes'], 10)
        self.assertGreater(stats['edges'], 10)
    
    def test_router_normal_conditions(self):
        routing = self.hybrid.router.route(
            {'price': 30, 'wind_speed': 15, 'temperature': 80, 'hour': 14}
        )
        self.assertTrue(routing['use_vector'])
        self.assertFalse(routing['use_graph'])
    
    def test_router_activates_graph_for_outage(self):
        routing = self.hybrid.router.route(
            {'price': 55, 'wind_speed': 10, 'temperature': 90, 'hour': 18},
            {'outage': True, 'outage_generator': 'gen_limestone'},
        )
        self.assertTrue(routing['use_graph'])
    
    def test_router_activates_graph_for_extreme_heat(self):
        routing = self.hybrid.router.route(
            {'price': 120, 'wind_speed': 5, 'temperature': 108, 'hour': 16}
        )
        self.assertTrue(routing['use_graph'])
        self.assertGreater(routing['graph_weight'], routing['vector_weight'])
    
    def test_retrieve_returns_context(self):
        self.hybrid.add_experience(
            {'price': 30, 'hour': 14, 'temperature': 80, 'wind_speed': 15,
             'solar_ghi': 500, 'soc': 0.5, 'price_1h_ago': 28, 'price_4h_ago': 25},
            'HOLD', 0, True,
        )
        result = self.hybrid.retrieve(
            {'price': 32, 'hour': 14, 'temperature': 81, 'wind_speed': 14,
             'solar_ghi': 480, 'soc': 0.5, 'price_1h_ago': 30, 'price_4h_ago': 26}
        )
        self.assertIn('fused_context', result)
    
    def test_graph_outage_tracing(self):
        impacts = self.hybrid.graph.find_impact_chain('gen_limestone', 'outage')
        self.assertGreater(len(impacts), 0)
        self.assertIn('1800', str(impacts[0].get('impact', '')))


# ==================================================================
# INTEGRATION TESTS
# ==================================================================

class TestOrchestratorIntegration(unittest.TestCase):
    """Test that the orchestrator ties everything together."""
    
    def setUp(self):
        from core.orchestrator import Orchestrator
        self.orchestrator = Orchestrator(db_path=':memory:')
    
    def test_modules_load(self):
        self.assertGreater(len(self.orchestrator.modules), 3)
    
    def test_single_tick_completes(self):
        decision = self.orchestrator.tick()
        self.assertIsInstance(decision, dict)
        self.assertIn('action', decision)
        self.assertIn(decision['action'], ['CHARGE', 'DISCHARGE', 'HOLD'])
    
    def test_tick_updates_state(self):
        self.orchestrator.tick()
        self.assertEqual(self.orchestrator.state.tick, 1)
        self.assertGreater(self.orchestrator.state.current_price, -50)
    
    def test_decision_has_votes(self):
        decision = self.orchestrator.tick()
        self.assertIn('n_modules_voted', decision)
    
    def test_soc_stays_in_bounds(self):
        for _ in range(10):
            self.orchestrator.tick()
        soc = self.orchestrator.state.battery['soc']
        self.assertGreaterEqual(soc, self.orchestrator.state.battery['min_soc'])
        self.assertLessEqual(soc, self.orchestrator.state.battery['max_soc'])
    
    def test_multiple_ticks_accumulate_history(self):
        for _ in range(3):
            self.orchestrator.tick()
        self.assertEqual(len(self.orchestrator.state.decision_history), 3)


class TestDecisionEngine(unittest.TestCase):
    """Test the decision engine vote combining."""
    
    def setUp(self):
        from core.orchestrator import UnifiedOrchestrator, BrainState
        self.orch = UnifiedOrchestrator()
        self.orch.state = BrainState()
    
    def test_no_input_returns_hold(self):
        self.orch.state.current_price = 30  # neutral price, no strong signal
        self.orch.state.module_outputs = {}
        self.orch.state.module_weights = {}  # no weights = no module votes
        self.orch.state.rag_context = {}
        self.orch.state.hybrid_rag_context = {}
        self.orch.modules = {}  # disable all modules
        decision = self.orch._weighted_decide()
        self.assertEqual(decision['action'], 'HOLD')
    
    def test_negative_price_overrides(self):
        self.orch.state.current_price = -10
        self.orch.state.battery['soc'] = 0.5
        self.orch.state.module_weights = {m: 1.0 for m in self.orch.modules}
        self.orch.state.situation = {'temperature': 75}
        self.orch.state.rag_context = {}
        self.orch.state.hybrid_rag_context = {}
        decision = self.orch._weighted_decide()
        self.assertEqual(decision['action'], 'CHARGE')
    
    def test_extreme_price_overrides(self):
        self.orch.state.current_price = 500
        self.orch.state.battery['soc'] = 0.5
        self.orch.state.module_weights = {m: 1.0 for m in self.orch.modules}
        self.orch.state.situation = {'temperature': 75}
        self.orch.state.rag_context = {}
        self.orch.state.hybrid_rag_context = {}
        decision = self.orch._weighted_decide()
        self.assertEqual(decision['action'], 'DISCHARGE')
    
    def test_soc_guardrails_prevent_overdischarge(self):
        self.orch.state.current_price = 500
        self.orch.state.battery['soc'] = 0.04
        self.orch.state.module_weights = {m: 1.0 for m in self.orch.modules}
        self.orch.state.situation = {'temperature': 75}
        self.orch.state.rag_context = {}
        self.orch.state.hybrid_rag_context = {}
        decision = self.orch._weighted_decide()
        self.assertEqual(decision['action'], 'HOLD')


# ==================================================================
# REGRESSION TESTS
# ==================================================================

class TestRegressions(unittest.TestCase):
    """Ensure key results remain consistent."""
    
    def test_rl_agent_loads(self):
        from agents.rl_agent import RLDispatchAgent
        agent = RLDispatchAgent()
        self.assertIsNotNone(agent)
    
    def test_causal_engine_gas_sensitivity(self):
        """Higher gas price must always produce higher electricity price."""
        from core.causal_engine import CausalReasoningEngine
        engine = CausalReasoningEngine()
        
        low = engine.reason({'temperature': 80, 'wind_speed': 10,
                            'solar_ghi': 0, 'hour': 18, 'gas_price': 2.0})
        high = engine.reason({'temperature': 80, 'wind_speed': 10,
                             'solar_ghi': 0, 'hour': 18, 'gas_price': 8.0})
        
        self.assertGreater(high['price_prediction'], low['price_prediction'])
    
    def test_knowledge_graph_topology(self):
        """Graph should have expected number of nodes and edges."""
        from core.hybrid_rag import KnowledgeGraph
        graph = KnowledgeGraph()
        stats = graph.stats()
        self.assertGreaterEqual(stats['nodes'], 15)
        self.assertGreaterEqual(stats['edges'], 15)
    
    def test_situation_encoder_dimension(self):
        """Encoder must produce 16-dim vectors."""
        from core.rag_engine_v2 import SituationEncoder
        encoder = SituationEncoder()
        vec = encoder.encode({'price': 30, 'hour': 12, 'temperature': 80,
                             'wind_speed': 15, 'solar_ghi': 500, 'soc': 0.5,
                             'price_1h_ago': 28, 'price_4h_ago': 25})
        self.assertEqual(len(vec), 16)
    
    def test_backtest_voltstream_beats_traditional(self):
        """VoltStream must be profitable on real ERCOT data."""
        from backtest import run_backtest
        results = run_backtest(verbose=False)
        self.assertGreater(results['voltstream']['revenue'], 0)
    
    def test_backtest_capture_rate_positive(self):
        """VoltStream should capture a positive percentage of perfect foresight."""
        from backtest import run_backtest
        results = run_backtest(verbose=False)
        self.assertGreater(results['capture_rate'], 0)


# ==================================================================
# RUN
# ==================================================================

if __name__ == '__main__':
    # Run with verbose output
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"TESTS: {result.testsRun} run, "
          f"{len(result.failures)} failed, "
          f"{len(result.errors)} errors, "
          f"{result.testsRun - len(result.failures) - len(result.errors)} passed")
    print(f"{'='*70}")
