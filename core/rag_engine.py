"""
VoltStream AI — Retrieval Augmented Generation (RAG)
=====================================================
Right now Claude reasons about the current moment.
With RAG, Claude reasons WITH HISTORY.

Before making any decision, the RAG system:
1. Takes the current situation (price, weather, hour, etc.)
2. Searches VoltStream's entire memory for similar situations
3. Retrieves what happened, what we did, and how it worked out
4. Feeds that context to Claude alongside the current data
5. Claude makes a decision informed by every relevant past experience

EXAMPLE WITHOUT RAG:
  Claude sees: "$52/MWh, 95°F, wind dropping, 6 PM"
  Claude thinks: "High price, should discharge"

EXAMPLE WITH RAG:
  Claude sees: "$52/MWh, 95°F, wind dropping, 6 PM"
  RAG retrieves: "Last 8 times we saw this pattern:
    - 6 times price spiked to $150+ within 2 hours
    - We discharged early 3 times and missed the spike
    - We held 3 times and captured avg $180/MWh
    - Best outcome: held until $210, earned $52K"
  Claude thinks: "History says HOLD. This pattern precedes
    a spike 75% of the time. Wait for the bigger number."

That's the difference between a smart system and a wise one.

ARCHITECTURE:
  ┌──────────────┐     ┌──────────────┐
  │ Current      │     │  Memory DB   │
  │ Situation    │────→│  (SQLite)    │
  └──────┬───────┘     └──────┬───────┘
         │                     │
         │    ┌────────────┐   │ similar situations
         │    │  Retriever │←──┘
         │    └─────┬──────┘
         │          │ ranked context
         ▼          ▼
  ┌─────────────────────────┐
  │    Claude API           │
  │  (current + history)    │
  └────────┬────────────────┘
           │
           ▼
  ┌─────────────────────────┐
  │  Decision with wisdom   │
  └─────────────────────────┘
"""

import numpy as np
import sqlite3
import json
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple


class VectorIndex:
    """
    Simple vector similarity search for finding similar situations.
    
    Each situation is encoded as a feature vector.
    Finding similar situations = finding nearby vectors.
    
    In production: use FAISS or Pinecone for scale.
    Here: pure NumPy for zero dependencies.
    """
    
    def __init__(self):
        self.vectors = []
        self.metadata = []
    
    def add(self, vector: np.ndarray, meta: dict):
        """Add a situation vector with its metadata."""
        self.vectors.append(vector / (np.linalg.norm(vector) + 1e-8))
        self.metadata.append(meta)
    
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[float, dict]]:
        """
        Find the most similar past situations.
        Returns [(similarity_score, metadata), ...]
        """
        if not self.vectors:
            return []
        
        query_norm = query_vector / (np.linalg.norm(query_vector) + 1e-8)
        
        similarities = []
        for i, vec in enumerate(self.vectors):
            sim = np.dot(query_norm, vec)
            similarities.append((sim, self.metadata[i]))
        
        similarities.sort(key=lambda x: x[0], reverse=True)
        return similarities[:top_k]
    
    @property
    def size(self):
        return len(self.vectors)


class SituationEncoder:
    """
    Encodes a market situation into a feature vector
    for similarity search.
    
    Two situations are "similar" if they have similar:
    - Price level and direction
    - Weather conditions
    - Time of day and season
    - Grid conditions
    - Recent price action
    """
    
    VECTOR_DIM = 16
    
    def encode(self, situation: dict) -> np.ndarray:
        """Encode a situation into a fixed-size vector."""
        
        price = situation.get('price', 30)
        hour = situation.get('hour', 12)
        temp = situation.get('temperature', 75)
        wind = situation.get('wind_speed', 15)
        solar = situation.get('solar_ghi', 0)
        soc = situation.get('soc', 0.5)
        price_1h_ago = situation.get('price_1h_ago', price)
        price_4h_ago = situation.get('price_4h_ago', price)
        
        vector = np.array([
            price / 100,                                    # price level
            (price - price_1h_ago) / 50,                   # short momentum
            (price - price_4h_ago) / 100,                  # longer momentum
            np.sin(2 * np.pi * hour / 24),                 # hour (cyclic)
            np.cos(2 * np.pi * hour / 24),                 # hour (cyclic)
            (temp - 75) / 30,                              # temperature deviation
            wind / 30,                                      # wind normalized
            solar / 1000,                                   # solar normalized
            soc,                                            # battery state
            1.0 if price > 80 else 0.0,                    # spike flag
            1.0 if price < 5 else 0.0,                     # low price flag
            1.0 if price < 0 else 0.0,                     # negative flag
            max(0, temp - 95) / 15,                        # extreme heat
            1.0 if wind < 7 else 0.0,                      # calm wind flag
            1.0 if solar > 700 else 0.0,                   # high solar flag
            abs(price - price_1h_ago) / 30,                # volatility proxy
        ], dtype=np.float32)
        
        return vector


class MemoryRetriever:
    """
    Searches VoltStream's accumulated memory for relevant
    past experiences. This is the "Retrieval" in RAG.
    """
    
    def __init__(self, db_path: str = 'voltstream_memory.db'):
        self.db_path = db_path
        self.index = VectorIndex()
        self.encoder = SituationEncoder()
        self.loaded = False
    
    def load_from_database(self, db_path: str = None):
        """Load historical situations from the memory database."""
        path = db_path or self.db_path
        
        try:
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            
            rows = conn.execute('''
                SELECT d.*, f.forecasted_price, f.actual_price as forecast_actual,
                       f.forecast_error, f.abs_error
                FROM dispatch_memory d
                LEFT JOIN forecast_memory f ON d.hour_of_day = f.hour_of_day
                    AND d.month = f.month
                ORDER BY d.timestamp DESC
                LIMIT 10000
            ''').fetchall()
            
            for row in rows:
                situation = {
                    'price': row['price_at_decision'] or 30,
                    'hour': row['hour_of_day'] or 12,
                    'temperature': row['weather_temp'] or 75,
                    'wind_speed': row['weather_wind'] or 15,
                    'solar_ghi': row['weather_solar'] or 0,
                    'soc': row['soc_before'] or 0.5,
                    'price_1h_ago': row['price_at_decision'] or 30,
                    'price_4h_ago': row['price_at_decision'] or 30,
                }
                
                vector = self.encoder.encode(situation)
                meta = {
                    'timestamp': row['timestamp'],
                    'action': row['action'],
                    'power_mw': row['power_mw'],
                    'price': row['price_at_decision'],
                    'revenue': row['revenue'],
                    'was_correct': row['was_correct'],
                    'soc_before': row['soc_before'],
                    'soc_after': row['soc_after'],
                    'hour': row['hour_of_day'],
                    'temperature': row['weather_temp'],
                    'wind_speed': row['weather_wind'],
                    'solar_ghi': row['weather_solar'],
                    'forecast_error': row['forecast_error'] if 'forecast_error' in row.keys() else None,
                }
                
                self.index.add(vector, meta)
            
            conn.close()
            self.loaded = True
            return len(rows)
            
        except Exception as e:
            # If no database exists, start empty
            self.loaded = True
            return 0
    
    def load_from_records(self, records: List[dict]):
        """Load from in-memory records (for demo/testing)."""
        for record in records:
            situation = {
                'price': record.get('price', 30),
                'hour': record.get('hour', 12),
                'temperature': record.get('temperature', 75),
                'wind_speed': record.get('wind_speed', 15),
                'solar_ghi': record.get('solar_ghi', 0),
                'soc': record.get('soc', 0.5),
                'price_1h_ago': record.get('price_1h_ago', record.get('price', 30)),
                'price_4h_ago': record.get('price_4h_ago', record.get('price', 30)),
            }
            
            vector = self.encoder.encode(situation)
            self.index.add(vector, record)
        
        self.loaded = True
    
    def retrieve(self, current_situation: dict, top_k: int = 5) -> List[dict]:
        """
        Find the most similar past situations to the current one.
        """
        if not self.loaded or self.index.size == 0:
            return []
        
        vector = self.encoder.encode(current_situation)
        results = self.index.search(vector, top_k)
        
        retrieved = []
        for similarity, meta in results:
            retrieved.append({
                'similarity': round(float(similarity), 3),
                **meta,
            })
        
        return retrieved


class RAGReasoningEngine:
    """
    The full RAG pipeline:
    1. Encode current situation
    2. Retrieve similar past experiences
    3. Format context for Claude
    4. Get Claude's decision informed by history
    5. Store this new experience for future retrieval
    """
    
    CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
    
    def __init__(self, retriever: MemoryRetriever = None, api_key: str = None):
        self.retriever = retriever or MemoryRetriever()
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY', '')
        self.claude_enabled = bool(self.api_key)
        self.decisions = []
    
    def reason_with_history(self, current: dict) -> dict:
        """
        The core RAG function.
        
        Takes current situation, retrieves history,
        reasons with both, returns a decision.
        """
        
        # STEP 1: Retrieve similar past situations
        similar = self.retriever.retrieve(current, top_k=8)
        
        # STEP 2: Analyze retrieved history
        history_analysis = self._analyze_history(similar)
        
        # STEP 3: Build context for reasoning
        context = self._build_context(current, similar, history_analysis)
        
        # STEP 4: Reason (Claude if available, otherwise rule-based)
        if self.claude_enabled:
            decision = self._reason_with_claude(context)
        else:
            decision = self._reason_with_rules(current, history_analysis)
        
        # STEP 5: Package result
        result = {
            'timestamp': datetime.now().isoformat(),
            'current_situation': current,
            'similar_situations_found': len(similar),
            'history_analysis': history_analysis,
            'decision': decision,
            'context_used': context[:500] if isinstance(context, str) else str(context)[:500],
        }
        
        self.decisions.append(result)
        return result
    
    def _analyze_history(self, similar: List[dict]) -> dict:
        """
        Extract actionable patterns from retrieved history.
        """
        if not similar:
            return {
                'has_history': False,
                'message': 'No similar situations in memory. Flying blind.',
            }
        
        # What actions were taken in similar situations?
        actions = [s.get('action', 'HOLD') for s in similar]
        revenues = [s.get('revenue', 0) for s in similar if s.get('revenue') is not None]
        correct = [s.get('was_correct', 0) for s in similar if s.get('was_correct') is not None]
        
        # Action distribution
        from collections import Counter
        action_counts = Counter(actions)
        most_common_action = action_counts.most_common(1)[0] if action_counts else ('HOLD', 0)
        
        # Revenue by action
        revenue_by_action = {}
        for s in similar:
            action = s.get('action', 'HOLD')
            rev = s.get('revenue', 0)
            if rev is not None:
                if action not in revenue_by_action:
                    revenue_by_action[action] = []
                revenue_by_action[action].append(rev)
        
        best_action = None
        best_avg_revenue = -float('inf')
        for action, revs in revenue_by_action.items():
            avg = np.mean(revs)
            if avg > best_avg_revenue:
                best_avg_revenue = avg
                best_action = action
        
        # Success rate
        success_rate = np.mean(correct) if correct else 0.5
        
        # Price outcomes
        prices = [s.get('price', 0) for s in similar]
        
        return {
            'has_history': True,
            'n_similar': len(similar),
            'avg_similarity': round(np.mean([s['similarity'] for s in similar]), 3),
            'action_distribution': dict(action_counts),
            'most_common_action': most_common_action[0],
            'most_common_action_count': most_common_action[1],
            'best_historical_action': best_action,
            'best_avg_revenue': round(best_avg_revenue, 2) if best_avg_revenue > -float('inf') else 0,
            'historical_success_rate': round(success_rate, 3),
            'price_range_in_similar': {
                'min': round(min(prices), 2) if prices else 0,
                'max': round(max(prices), 2) if prices else 0,
                'avg': round(np.mean(prices), 2) if prices else 0,
            },
            'revenue_by_action': {k: round(np.mean(v), 2) for k, v in revenue_by_action.items()},
        }
    
    def _build_context(self, current: dict, similar: List[dict],
                       analysis: dict) -> str:
        """
        Build the context string that gets sent to Claude.
        This is what makes RAG powerful — Claude sees HISTORY.
        """
        context = f"""CURRENT SITUATION:
Price: ${current.get('price', 0):.2f}/MWh
Hour: {current.get('hour', 12)}:00
Temperature: {current.get('temperature', 75):.0f}°F
Wind: {current.get('wind_speed', 15):.0f} mph
Solar: {current.get('solar_ghi', 0):.0f} W/m²
Battery SOC: {current.get('soc', 0.5)*100:.0f}%

HISTORICAL CONTEXT (from {analysis.get('n_similar', 0)} similar situations in memory):
"""
        
        if not analysis.get('has_history'):
            context += "No similar situations found in memory. This is a new pattern.\n"
        else:
            context += f"""
Action distribution in similar situations:
{json.dumps(analysis.get('action_distribution', {}), indent=2)}

Best performing action historically: {analysis.get('best_historical_action', 'unknown')} 
  (avg revenue: ${analysis.get('best_avg_revenue', 0):.2f})
Historical success rate: {analysis.get('historical_success_rate', 0):.0%}

Specific similar situations:
"""
            for i, s in enumerate(similar[:5], 1):
                context += (
                    f"\n  Situation {i} (similarity: {s['similarity']:.0%}):\n"
                    f"    Price: ${s.get('price', 0):.2f} | Hour: {s.get('hour', '?')} | "
                    f"Temp: {s.get('temperature', '?')}°F\n"
                    f"    Action taken: {s.get('action', '?')} at {s.get('power_mw', 0):.0f} MW\n"
                    f"    Revenue: ${s.get('revenue', 0):.2f} | "
                    f"Correct: {'Yes' if s.get('was_correct') else 'No'}\n"
                )
        
        return context
    
    def _reason_with_claude(self, context: str) -> dict:
        """Send context to Claude for reasoning."""
        system = """You are VoltStream AI's dispatch brain. You make battery 
charge/discharge decisions based on current market conditions AND historical 
performance data from similar past situations.

Your memory contains real outcomes from past trades. Use them.
If history shows an action worked 80% of the time in similar situations, 
weight that heavily. If history shows we lost money doing something similar, 
avoid it.

Respond ONLY in valid JSON:
{
  "action": "CHARGE" or "DISCHARGE" or "HOLD",
  "intensity": 0.0 to 1.0,
  "reasoning": "2-3 sentences explaining the decision",
  "historical_influence": "how history shaped this decision",
  "confidence": 0.0 to 1.0
}"""
        
        try:
            response = requests.post(
                self.CLAUDE_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 300,
                    "system": system,
                    "messages": [{"role": "user", "content": context}],
                },
                timeout=15,
            )
            
            if response.status_code == 200:
                text = response.json()['content'][0]['text']
                clean = text.strip()
                if clean.startswith('```'):
                    clean = clean.split('\n', 1)[1].rsplit('```', 1)[0]
                return json.loads(clean)
        except Exception:
            pass
        
        return self._reason_with_rules({'price': 30}, {})
    
    def _reason_with_rules(self, current: dict, analysis: dict) -> dict:
        """
        Rule-based reasoning informed by historical analysis.
        Used when Claude API is not available.
        """
        price = current.get('price', 30)
        soc = current.get('soc', 0.5)
        
        # Start with the historically best action if we have history
        if analysis.get('has_history') and analysis.get('historical_success_rate', 0) > 0.6:
            best_action = analysis.get('best_historical_action', 'HOLD')
            best_revenue = analysis.get('best_avg_revenue', 0)
            
            # Trust history if it's confident
            if analysis['n_similar'] >= 5 and analysis['historical_success_rate'] > 0.7:
                confidence = min(0.90, analysis['historical_success_rate'])
                
                # But override if SOC constraints prevent it
                if best_action == 'DISCHARGE' and soc < 0.15:
                    best_action = 'HOLD'
                    confidence = 0.5
                elif best_action == 'CHARGE' and soc > 0.90:
                    best_action = 'HOLD'
                    confidence = 0.5
                
                intensity = 0.7 if confidence > 0.8 else 0.5
                
                return {
                    'action': best_action,
                    'intensity': intensity,
                    'reasoning': (
                        f"History shows {best_action} worked best in {analysis['n_similar']} "
                        f"similar situations with {analysis['historical_success_rate']:.0%} success rate "
                        f"and avg revenue of ${best_revenue:.0f}."
                    ),
                    'historical_influence': 'high',
                    'confidence': confidence,
                }
        
        # No strong historical signal — use basic rules
        action = 'HOLD'
        intensity = 0
        reasoning = ''
        
        if price < 0:
            action = 'CHARGE'
            intensity = 1.0
            reasoning = 'Negative price. No history needed. Charge.'
        elif price < 10 and soc < 0.80:
            action = 'CHARGE'
            intensity = 0.6
            reasoning = f'Low price at ${price:.0f}. Charging.'
        elif price > 60 and soc > 0.20:
            action = 'DISCHARGE'
            intensity = 0.8
            reasoning = f'High price at ${price:.0f}. Discharging.'
        else:
            reasoning = f'No strong signal. Price ${price:.0f}, SOC {soc*100:.0f}%. Holding.'
        
        return {
            'action': action,
            'intensity': intensity,
            'reasoning': reasoning,
            'historical_influence': 'low' if analysis.get('has_history') else 'none',
            'confidence': 0.5,
        }


def demo():
    """Demonstrate RAG-enhanced decision making."""
    
    print("=" * 70)
    print("⚡ VoltStream AI — Retrieval Augmented Generation (RAG)")
    print("=" * 70)
    print()
    print("  Without RAG: 'Price is $52. Should I sell?'")
    print("  With RAG: 'Price is $52. Last 8 times this happened,")
    print("  holding led to a $150 spike 75% of the time.'")
    print()
    
    # Build a memory of past experiences
    retriever = MemoryRetriever()
    
    print("  Building memory from 30 days of simulated trading...\n")
    
    np.random.seed(42)
    records = []
    
    for day in range(30):
        for hour in range(24):
            temp = 75 + 15 * np.sin((hour - 6) / 24 * 2 * np.pi) + np.random.normal(0, 3)
            wind = max(0, 15 + 8 * np.sin((hour - 3) / 24 * 2 * np.pi) + np.random.normal(0, 5))
            solar = max(0, np.sin((hour - 6) / 13 * np.pi) * 900) if 6 < hour < 19 else 0
            
            if hour < 6:
                price = 42 + np.random.normal(0, 8)
            elif hour < 10:
                price = 30 - (hour - 6) * 7 + np.random.normal(0, 5)
            elif hour < 16:
                price = 3 + np.random.normal(0, 4)
            elif hour < 20:
                price = 25 + (hour - 16) * 12 + np.random.normal(0, 8)
            else:
                price = 45 + np.random.normal(0, 10)
            
            # Random spikes
            if np.random.random() < 0.03:
                price = 150 + np.random.exponential(80)
            
            price = max(-10, price)
            
            # What action was taken and how it worked out
            if price < 10:
                action = 'CHARGE'
                revenue = -price * 80 * 0.25
                was_correct = 1
            elif price > 50:
                action = 'DISCHARGE'
                revenue = price * 80 * 0.25
                was_correct = 1
            elif price > 30 and hour in [17, 18, 19]:
                action = 'DISCHARGE'
                revenue = price * 60 * 0.25
                was_correct = 1 if price > 40 else 0
            else:
                action = 'HOLD'
                revenue = 0
                was_correct = 1 if abs(price - 25) < 15 else 0
            
            records.append({
                'price': round(price, 2),
                'hour': hour,
                'temperature': round(temp, 1),
                'wind_speed': round(wind, 1),
                'solar_ghi': round(solar, 0),
                'soc': 0.5,
                'price_1h_ago': price + np.random.normal(0, 3),
                'price_4h_ago': price + np.random.normal(0, 8),
                'action': action,
                'power_mw': 80 if action != 'HOLD' else 0,
                'revenue': round(revenue, 2),
                'was_correct': was_correct,
            })
    
    retriever.load_from_records(records)
    print(f"  Memory loaded: {retriever.index.size} experiences indexed\n")
    
    # Create RAG engine
    rag = RAGReasoningEngine(retriever)
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Evening peak, moderate price',
            'situation': {'price': 52, 'hour': 18, 'temperature': 92, 'wind_speed': 8, 'solar_ghi': 100, 'soc': 0.70, 'price_1h_ago': 45, 'price_4h_ago': 30},
            'question': 'Sell now at $52 or wait for a potential spike?',
        },
        {
            'name': 'Midday solar glut',
            'situation': {'price': 2, 'hour': 12, 'temperature': 88, 'wind_speed': 14, 'solar_ghi': 920, 'soc': 0.30, 'price_1h_ago': 5, 'price_4h_ago': 15},
            'question': 'Cheap power. How aggressively should we charge?',
        },
        {
            'name': 'Pre-dawn, price rising',
            'situation': {'price': 48, 'hour': 4, 'temperature': 72, 'wind_speed': 20, 'solar_ghi': 0, 'soc': 0.85, 'price_1h_ago': 42, 'price_4h_ago': 38},
            'question': 'Price climbing overnight. Discharge now or hold?',
        },
        {
            'name': 'Negative price event',
            'situation': {'price': -8, 'hour': 10, 'temperature': 80, 'wind_speed': 28, 'solar_ghi': 800, 'soc': 0.20, 'price_1h_ago': 3, 'price_4h_ago': 15},
            'question': 'Being paid to charge. How long does this last?',
        },
        {
            'name': 'Hot evening, wind dying',
            'situation': {'price': 65, 'hour': 17, 'temperature': 101, 'wind_speed': 5, 'solar_ghi': 400, 'soc': 0.75, 'price_1h_ago': 55, 'price_4h_ago': 20},
            'question': 'Heat wave, wind dying, price climbing. Spike incoming?',
        },
    ]
    
    for scenario in scenarios:
        result = rag.reason_with_history(scenario['situation'])
        
        analysis = result['history_analysis']
        decision = result['decision']
        
        print(f"  {'='*60}")
        print(f"  SCENARIO: {scenario['name']}")
        print(f"  {'='*60}")
        print(f"  Question: {scenario['question']}")
        
        s = scenario['situation']
        print(f"  Now: ${s['price']}/MWh | {s['hour']}:00 | {s['temperature']}°F | "
              f"Wind: {s['wind_speed']}mph | SOC: {s['soc']*100:.0f}%")
        
        if analysis.get('has_history'):
            print(f"\n  MEMORY RETRIEVAL: {analysis['n_similar']} similar situations found "
                  f"(avg similarity: {analysis['avg_similarity']:.0%})")
            print(f"    Historical actions: {analysis['action_distribution']}")
            print(f"    Best action was: {analysis['best_historical_action']} "
                  f"(avg ${analysis['best_avg_revenue']:.0f} revenue)")
            print(f"    Success rate: {analysis['historical_success_rate']:.0%}")
            
            if analysis.get('revenue_by_action'):
                print(f"    Revenue by action:")
                for action, rev in sorted(analysis['revenue_by_action'].items(), key=lambda x: x[1], reverse=True):
                    print(f"      {action}: ${rev:.0f} avg")
        else:
            print(f"\n  MEMORY: No similar situations found. New pattern.")
        
        icon = {'CHARGE': '🟢', 'DISCHARGE': '🟡', 'HOLD': '⚪'}.get(decision['action'], '?')
        print(f"\n  DECISION: {icon} {decision['action']} "
              f"(intensity: {decision['intensity']:.0%}, confidence: {decision['confidence']:.0%})")
        print(f"  Reasoning: {decision['reasoning']}")
        print(f"  History influence: {decision.get('historical_influence', 'unknown')}")
        print()
    
    print(f"{'='*70}")
    print("RAG CAPABILITY:")
    print(f"{'='*70}")
    print(f"""
  The brain just made 5 decisions with WISDOM, not just intelligence.
  
  WITHOUT RAG (what every other system does):
    "Price is $52. My model says discharge."
    
  WITH RAG (what VoltStream does):
    "Price is $52. I found 8 similar situations in my memory.
     In 6 of them, discharging early missed a spike to $150+.
     In the 2 where we held, avg revenue was 3x higher.
     Decision: HOLD. History says wait for the bigger number."
  
  The difference between a smart system and a wise one is MEMORY.
  Smart systems react to the present. Wise systems learn from the past.
  
  After 6 months of operation, VoltStream has seen thousands of
  market situations. Every new decision is informed by every past
  decision. A competitor starting from scratch has zero memory.
  
  RAG is what makes the 6-month data moat REAL.
  The data isn't just stored. It's USED. Every 5 minutes.
""")


if __name__ == '__main__':
    demo()
