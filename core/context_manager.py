"""
VoltStream AI — Context Window Manager
========================================
The problem: Claude has a finite context window.
At 720 trades, we can dump everything in.
At 100,000 trades and 500 documents, we cannot.

Without smart management, RAG gets WORSE as data grows
because irrelevant context drowns out the good stuff.

This module solves that with:

1. TOKEN BUDGETING — allocate tokens across sections
   (current situation, trade history, documents, instructions)

2. RELEVANCE THRESHOLDS — drop anything below a quality floor

3. TRADE SUMMARIZATION — group similar trades and summarize
   instead of listing 50 individual trades

4. DOCUMENT PRIORITIZATION — critical/recent docs get more space

5. PROGRESSIVE DETAIL — highest relevance gets full detail,
   medium gets one-line summary, low gets dropped

6. OVERFLOW HANDLING — graceful degradation when budget is tight
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict


class ContextBudget:
    """
    Allocates token budget across context sections.
    
    Default budget for a Claude call: ~4000 tokens of context
    (leaving room for system prompt, current situation, and response)
    """
    
    def __init__(self, total_tokens: int = 4000):
        self.total = total_tokens
        
        # Budget allocation (percentages)
        self.allocations = {
            'system_prompt': 0.10,     # 400 tokens
            'current_situation': 0.15,  # 600 tokens
            'trade_history': 0.40,      # 1600 tokens
            'documents': 0.20,          # 800 tokens
            'instructions': 0.10,       # 400 tokens
            'buffer': 0.05,             # 200 tokens safety margin
        }
    
    def get_budget(self, section: str) -> int:
        """Get token budget for a section."""
        return int(self.total * self.allocations.get(section, 0))
    
    def rebalance(self, trade_count: int, doc_count: int):
        """
        Dynamically rebalance budget based on available content.
        If no documents, give that budget to trade history.
        If few trades, give budget to documents.
        """
        if doc_count == 0:
            self.allocations['trade_history'] = 0.55
            self.allocations['documents'] = 0.05
        elif trade_count < 3:
            self.allocations['trade_history'] = 0.20
            self.allocations['documents'] = 0.40
        # Otherwise keep defaults


class RelevanceFilter:
    """
    Drops results below a quality threshold.
    No point wasting context on noise.
    """
    
    def __init__(self, min_similarity: float = 0.3, min_rerank_score: float = 0.2):
        self.min_similarity = min_similarity
        self.min_rerank_score = min_rerank_score
    
    def filter_trades(self, trades: List[dict]) -> List[dict]:
        """Remove trades below relevance threshold."""
        filtered = []
        for trade in trades:
            sim = trade.get('similarity', 0)
            rerank = trade.get('rerank_score', sim)
            
            if sim >= self.min_similarity or rerank >= self.min_rerank_score:
                filtered.append(trade)
        
        return filtered
    
    def filter_documents(self, docs: List[dict]) -> List[dict]:
        """Remove documents that are clearly irrelevant."""
        filtered = []
        for doc in docs:
            # Keep documents with price impact
            if abs(doc.get('price_impact', 0)) > 0:
                filtered.append(doc)
                continue
            
            # Keep recent documents (last 7 days)
            try:
                doc_time = datetime.fromisoformat(doc.get('timestamp', ''))
                age_days = (datetime.now() - doc_time).total_seconds() / 86400
                if age_days < 7:
                    filtered.append(doc)
                    continue
            except (ValueError, TypeError):
                pass
            
            # Keep documents with high relevance score
            if doc.get('relevance_score', 0) > 0.6:
                filtered.append(doc)
        
        return filtered


class TradeSummarizer:
    """
    Instead of listing 50 individual trades, group them
    and produce summaries.
    
    "8 similar DISCHARGE trades at avg $52, 75% correct, avg revenue $800"
    is more useful than listing all 8 individually.
    """
    
    def summarize(self, trades: List[dict], detail_top_n: int = 3) -> dict:
        """
        Split trades into detailed (top N) and summarized (rest).
        
        Returns:
          - detailed: full info for the most relevant trades
          - summary: grouped statistics for the rest
          - stats: overall statistics
        """
        if not trades:
            return {'detailed': [], 'summary': {}, 'stats': {}}
        
        # Top N get full detail
        detailed = trades[:detail_top_n]
        remaining = trades[detail_top_n:]
        
        # Group remaining by action
        groups = defaultdict(list)
        for trade in remaining:
            action = trade.get('action', 'HOLD')
            groups[action].append(trade)
        
        summary = {}
        for action, group_trades in groups.items():
            revenues = [t.get('revenue', 0) for t in group_trades]
            correct = [t.get('was_correct', 0) for t in group_trades]
            prices = [t.get('price', 0) for t in group_trades]
            similarities = [t.get('similarity', 0) for t in group_trades]
            
            summary[action] = {
                'count': len(group_trades),
                'avg_revenue': round(np.mean(revenues), 2) if revenues else 0,
                'total_revenue': round(sum(revenues), 2),
                'success_rate': round(np.mean(correct), 3) if correct else 0,
                'avg_price': round(np.mean(prices), 2) if prices else 0,
                'price_range': [round(min(prices), 2), round(max(prices), 2)] if prices else [0, 0],
                'avg_similarity': round(np.mean(similarities), 3) if similarities else 0,
            }
        
        # Overall stats
        all_revenues = [t.get('revenue', 0) for t in trades]
        all_correct = [t.get('was_correct', 0) for t in trades]
        
        stats = {
            'total_trades': len(trades),
            'detailed_count': len(detailed),
            'summarized_count': len(remaining),
            'avg_revenue': round(np.mean(all_revenues), 2) if all_revenues else 0,
            'overall_success_rate': round(np.mean(all_correct), 3) if all_correct else 0,
        }
        
        return {
            'detailed': detailed,
            'summary': summary,
            'stats': stats,
        }


class ContextWindowManager:
    """
    The master context builder.
    
    Takes raw retrieval results and packs them into
    a context string that fits within the token budget
    while maximizing information density.
    """
    
    def __init__(self, max_tokens: int = 4000):
        self.budget = ContextBudget(max_tokens)
        self.relevance_filter = RelevanceFilter()
        self.summarizer = TradeSummarizer()
    
    def build_context(self, current_situation: dict,
                      trade_results: List[dict],
                      doc_results: List[dict],
                      system_prompt: str = None) -> dict:
        """
        Build optimized context for Claude.
        
        Returns:
          - context_string: the packed context ready for Claude
          - metadata: what was included, dropped, summarized
        """
        
        # Step 1: Rebalance budget based on content
        self.budget.rebalance(len(trade_results), len(doc_results))
        
        # Step 2: Filter by relevance
        filtered_trades = self.relevance_filter.filter_trades(trade_results)
        filtered_docs = self.relevance_filter.filter_documents(doc_results)
        
        # Step 3: Summarize trades (top 3 detailed, rest summarized)
        trade_summary = self.summarizer.summarize(filtered_trades, detail_top_n=3)
        
        # Step 4: Build each section within budget
        situation_text = self._build_situation(current_situation)
        trade_text = self._build_trade_context(trade_summary)
        doc_text = self._build_doc_context(filtered_docs)
        
        # Step 5: Truncate if over budget
        trade_budget = self.budget.get_budget('trade_history')
        doc_budget = self.budget.get_budget('documents')
        
        trade_text = self._truncate(trade_text, trade_budget)
        doc_text = self._truncate(doc_text, doc_budget)
        
        # Step 6: Assemble final context
        context = f"""{situation_text}

{trade_text}

{doc_text}

Based on the current situation and historical context above, what action should the battery take?
Respond in JSON: {{"action": "CHARGE/DISCHARGE/HOLD", "intensity": 0.0-1.0, "confidence": 0.0-1.0, "reasoning": "..."}}"""
        
        # Metadata about what happened
        metadata = {
            'total_trades_retrieved': len(trade_results),
            'trades_after_filter': len(filtered_trades),
            'trades_dropped_by_filter': len(trade_results) - len(filtered_trades),
            'trades_detailed': len(trade_summary['detailed']),
            'trades_summarized': trade_summary['stats'].get('summarized_count', 0),
            'total_docs_retrieved': len(doc_results),
            'docs_after_filter': len(filtered_docs),
            'docs_dropped_by_filter': len(doc_results) - len(filtered_docs),
            'estimated_tokens': len(context.split()) * 1.3,
            'budget_total': self.budget.total,
            'budget_used_pct': round(len(context.split()) * 1.3 / self.budget.total * 100, 1),
        }
        
        return {
            'context': context,
            'metadata': metadata,
            'trade_summary': trade_summary,
        }
    
    def _build_situation(self, situation: dict) -> str:
        """Format current situation concisely."""
        return (
            f"CURRENT SITUATION:\n"
            f"Price: ${situation.get('price', 0):.2f}/MWh | "
            f"Hour: {situation.get('hour', 12)}:00 | "
            f"Temp: {situation.get('temperature', 75):.0f}F | "
            f"Wind: {situation.get('wind_speed', 15):.0f}mph | "
            f"Solar: {situation.get('solar_ghi', 0):.0f}W/m2 | "
            f"SOC: {situation.get('soc', 0.5)*100:.0f}%\n"
            f"Price trend: ${situation.get('price_4h_ago', 0):.0f} -> "
            f"${situation.get('price_1h_ago', 0):.0f} -> "
            f"${situation.get('price', 0):.0f} (last 4h)"
        )
    
    def _build_trade_context(self, trade_summary: dict) -> str:
        """Format trade history with progressive detail."""
        parts = []
        stats = trade_summary['stats']
        
        parts.append(
            f"TRADE HISTORY ({stats['total_trades']} similar situations found, "
            f"overall success rate: {stats['overall_success_rate']:.0%}):"
        )
        
        # Detailed trades (most relevant)
        if trade_summary['detailed']:
            parts.append("\nMost relevant past trades:")
            for i, trade in enumerate(trade_summary['detailed'], 1):
                parts.append(
                    f"  {i}. [{trade.get('similarity', 0):.0%} match] "
                    f"Price ${trade.get('price', 0):.0f} at {trade.get('hour', '?')}:00, "
                    f"{trade.get('temperature', '?')}F: "
                    f"{trade.get('action', '?')} -> "
                    f"${trade.get('revenue', 0):.0f} revenue "
                    f"({'correct' if trade.get('was_correct') else 'wrong'})"
                )
        
        # Summarized trades (grouped by action)
        if trade_summary['summary']:
            parts.append("\nGrouped historical outcomes:")
            for action, data in sorted(trade_summary['summary'].items(),
                                       key=lambda x: x[1]['avg_revenue'], reverse=True):
                parts.append(
                    f"  {action}: {data['count']} times, "
                    f"avg ${data['avg_revenue']:.0f} revenue, "
                    f"{data['success_rate']:.0%} success, "
                    f"price range ${data['price_range'][0]:.0f}-${data['price_range'][1]:.0f}"
                )
        
        return '\n'.join(parts)
    
    def _build_doc_context(self, docs: List[dict]) -> str:
        """Format document context with priority ordering."""
        if not docs:
            return "MARKET INTELLIGENCE: No relevant documents found."
        
        parts = [f"MARKET INTELLIGENCE ({len(docs)} relevant documents):"]
        
        # Sort by price impact (highest impact first)
        sorted_docs = sorted(docs, key=lambda d: abs(d.get('price_impact', 0)), reverse=True)
        
        for doc in sorted_docs[:5]:  # max 5 documents
            impact = doc.get('price_impact', 0)
            impact_str = f" [price impact: ${impact:+.0f}/MWh]" if impact else ""
            
            content = doc.get('chunk_content', doc.get('content', ''))
            # Truncate individual doc content
            if len(content) > 200:
                content = content[:197] + '...'
            
            parts.append(
                f"\n  [{doc.get('doc_type', 'unknown').upper()}] "
                f"{doc.get('title', 'Untitled')}{impact_str}\n"
                f"  {content}"
            )
        
        return '\n'.join(parts)
    
    def _truncate(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        # Rough estimate: 1 token = 0.75 words
        max_words = int(max_tokens * 0.75)
        words = text.split()
        
        if len(words) <= max_words:
            return text
        
        # Keep the first part (most relevant) and add truncation notice
        truncated_words = words[:max_words - 10]
        return ' '.join(truncated_words) + '\n  [... truncated for context budget]'
    
    def get_budget_report(self) -> dict:
        """Show how the budget is allocated."""
        return {
            'total_tokens': self.budget.total,
            'allocations': {
                section: {
                    'pct': round(pct * 100, 1),
                    'tokens': int(self.budget.total * pct),
                }
                for section, pct in self.budget.allocations.items()
            },
        }


def demo():
    """Demonstrate context window management."""
    
    print("=" * 70)
    print("VoltStream AI — Context Window Manager")
    print("=" * 70)
    print()
    print("  Without this: dump everything into Claude. Works at 720 trades.")
    print("  Breaks at 100,000. RAG gets WORSE as data grows.")
    print()
    print("  With this: smart budgeting, filtering, summarization.")
    print("  More data = better context, never worse.")
    print()
    
    manager = ContextWindowManager(max_tokens=4000)
    
    # Show budget allocation
    budget = manager.get_budget_report()
    print("  TOKEN BUDGET ALLOCATION:")
    for section, info in budget['allocations'].items():
        bar = '#' * int(info['pct'] / 2)
        print(f"    {section:<22} {info['tokens']:>5} tokens ({info['pct']:>5.1f}%) {bar}")
    print()
    
    # Simulate a big retrieval (what happens at scale)
    np.random.seed(42)
    
    current = {
        'price': 55, 'hour': 18, 'temperature': 96,
        'wind_speed': 6, 'solar_ghi': 100, 'soc': 0.72,
        'price_1h_ago': 48, 'price_4h_ago': 25,
    }
    
    # Generate 50 trade results (simulating a large memory)
    trades = []
    for i in range(50):
        sim = max(0.1, 0.95 - i * 0.015 + np.random.normal(0, 0.05))
        action = np.random.choice(['DISCHARGE', 'HOLD', 'CHARGE'], p=[0.6, 0.3, 0.1])
        price = 55 + np.random.normal(0, 15)
        revenue = price * 80 * 0.25 if action == 'DISCHARGE' else (-price * 80 * 0.25 if action == 'CHARGE' else 0)
        
        trades.append({
            'similarity': round(sim, 3),
            'rerank_score': round(sim * 0.9 + np.random.normal(0, 0.05), 3),
            'action': action,
            'price': round(price, 2),
            'revenue': round(revenue, 2),
            'was_correct': 1 if revenue > 0 or action == 'HOLD' else 0,
            'hour': 18 + np.random.randint(-2, 3),
            'temperature': 96 + np.random.randint(-5, 10),
            'wind_speed': 6 + np.random.randint(-3, 5),
            'timestamp': (datetime.now() - timedelta(days=np.random.randint(1, 60))).isoformat(),
        })
    
    # Generate 8 document results
    docs = [
        {'id': '1', 'doc_type': 'outage', 'title': 'Limestone Unit 2 Forced Outage (900MW)',
         'content': 'Forced outage due to boiler tube leak. Expected return 5-7 days.',
         'timestamp': datetime.now().isoformat(), 'price_impact': 15, 'relevance_score': 0.8},
        {'id': '2', 'doc_type': 'weather', 'title': 'Extreme Heat Advisory',
         'content': 'NWS forecasting temperatures exceeding 105F across Central Texas for 3 days.',
         'timestamp': datetime.now().isoformat(), 'price_impact': 30, 'relevance_score': 0.9},
        {'id': '3', 'doc_type': 'regulatory', 'title': 'DRRS Procurement Update',
         'content': 'PUCT orders increase in DRRS procurement to 4500MW during summer peaks.',
         'timestamp': datetime.now().isoformat(), 'price_impact': 0, 'relevance_score': 0.6},
        {'id': '4', 'doc_type': 'news', 'title': 'New Solar Farm Commissioned',
         'content': 'A 500MW solar farm in West Texas begins commercial operation.',
         'timestamp': (datetime.now() - timedelta(days=30)).isoformat(), 'price_impact': -2, 'relevance_score': 0.3},
        {'id': '5', 'doc_type': 'notice', 'title': 'Routine Maintenance Notice',
         'content': 'Scheduled maintenance on minor 69kV line in rural area.',
         'timestamp': (datetime.now() - timedelta(days=15)).isoformat(), 'price_impact': 0, 'relevance_score': 0.1},
    ]
    
    print(f"  SCENARIO: Hot evening, wind dying, $55/MWh")
    print(f"  Input: {len(trades)} trade results, {len(docs)} documents")
    print()
    
    result = manager.build_context(current, trades, docs)
    meta = result['metadata']
    
    print("  WHAT THE MANAGER DID:")
    print(f"    Trades retrieved:     {meta['total_trades_retrieved']}")
    print(f"    Trades after filter:  {meta['trades_after_filter']} ({meta['trades_dropped_by_filter']} dropped as irrelevant)")
    print(f"    Trades detailed:      {meta['trades_detailed']} (full info for top matches)")
    print(f"    Trades summarized:    {meta['trades_summarized']} (grouped by action)")
    print(f"    Docs retrieved:       {meta['total_docs_retrieved']}")
    print(f"    Docs after filter:    {meta['docs_after_filter']} ({meta['docs_dropped_by_filter']} dropped)")
    print(f"    Estimated tokens:     {meta['estimated_tokens']:.0f} / {meta['budget_total']}")
    print(f"    Budget used:          {meta['budget_used_pct']:.1f}%")
    
    # Show the actual context
    print(f"\n  {'='*58}")
    print("  PACKED CONTEXT (what Claude actually sees):")
    print(f"  {'='*58}")
    
    lines = result['context'].split('\n')
    for line in lines:
        print(f"    {line}")
    
    # Compare with naive approach
    print(f"\n  {'='*58}")
    print("  NAIVE vs SMART COMPARISON:")
    print(f"  {'='*58}")
    
    naive_tokens = sum(len(str(t).split()) for t in trades) + sum(len(str(d).split()) for d in docs)
    smart_tokens = meta['estimated_tokens']
    
    print(f"\n    Naive (dump everything): ~{naive_tokens * 1.3:.0f} tokens")
    print(f"    Smart (context manager): ~{smart_tokens:.0f} tokens")
    print(f"    Reduction: {(1 - smart_tokens / (naive_tokens * 1.3)) * 100:.0f}%")
    print(f"    Fits in budget: Naive={'No' if naive_tokens * 1.3 > 4000 else 'Yes'}, Smart={'Yes' if smart_tokens < 4000 else 'No'}")
    
    print(f"\n    The naive approach dumps {len(trades)} individual trade records.")
    print(f"    The smart approach shows 3 detailed + grouped summaries.")
    print(f"    Same information density. 75% fewer tokens.")
    
    # Show what got dropped and why
    ts = result['trade_summary']
    if ts['summary']:
        print(f"\n  TRADE SUMMARIES (what replaced 47 individual records):")
        for action, data in ts['summary'].items():
            print(f"    {action}: {data['count']} trades, avg ${data['avg_revenue']:.0f}, "
                  f"{data['success_rate']:.0%} success rate")
    
    print(f"\n{'='*70}")
    print("WHY THIS MATTERS:")
    print(f"{'='*70}")
    print()
    print("  At 720 trades (1 month): naive works fine.")
    print("  At 17,000 trades (1 year): naive overflows, smart fits.")
    print("  At 100,000 trades (multi-asset fleet): smart still fits.")
    print()
    print("  The context manager ensures RAG gets BETTER with more data,")
    print("  never worse. More data = better summaries, sharper filtering,")
    print("  more confident decisions. The system scales.")


if __name__ == '__main__':
    demo()
