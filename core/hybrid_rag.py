"""
VoltStream AI — Hybrid RAG Engine
===================================
Vector store finds SIMILAR situations.
Knowledge graph finds CONNECTED information.
Query router decides which one to use.
Fusion layer merges both into one context.

EXAMPLE:
  Situation: "Price spiking at $85, wind dropping in West Texas"
  
  Vector retriever: "Found 6 similar price spikes, 4 led to $150+"
  
  Graph retriever: "Wind dropping in West Texas means:
    -> Less generation at Sweetwater Wind Farm (1200MW)
    -> More load on gas plants at Odessa (800MW CCGT)
    -> Odessa connected to constrained West-Houston corridor
    -> Last 3 times this happened, HB_WEST diverged from HB_HOUSTON by $40"
  
  Router: "This needs both. Vector for price patterns, graph for grid topology."
  
  Fusion: Combines into one context. Claude sees patterns AND structure.

KNOWLEDGE GRAPH ENTITIES:
  Generators -> connected to -> Buses/Nodes
  Buses -> connected via -> Transmission Lines
  Zones -> contain -> Generators, Load
  Outages -> affect -> Generators
  Weather -> impacts -> Generators (wind/solar)
  Operators -> own -> Generators
  Market Rules -> govern -> Products (energy, AS)
"""

import numpy as np
import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Set
from collections import defaultdict


# ==================================================================
# KNOWLEDGE GRAPH
# ==================================================================

class Node:
    """A node in the knowledge graph."""
    
    def __init__(self, node_id: str, node_type: str, properties: dict = None):
        self.id = node_id
        self.type = node_type
        self.properties = properties or {}
        self.edges_out = []  # (relationship, target_node_id)
        self.edges_in = []   # (relationship, source_node_id)
    
    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'properties': self.properties,
            'n_connections': len(self.edges_out) + len(self.edges_in),
        }


class Edge:
    """A relationship between two nodes."""
    
    def __init__(self, source_id: str, relationship: str, target_id: str,
                 properties: dict = None):
        self.source = source_id
        self.relationship = relationship
        self.target = target_id
        self.properties = properties or {}


class KnowledgeGraph:
    """
    Graph database modeling the ERCOT grid and market.
    
    Nodes: generators, zones, buses, operators, market products
    Edges: connected_to, located_in, owns, supplies, affects
    
    Enables traversal queries like:
    "What generators are in Zone North that depend on gas?"
    "If this transmission line goes down, what zones are affected?"
    "Which operator owns the most capacity in West Texas?"
    """
    
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.adjacency = defaultdict(list)  # node_id -> [(relationship, target_id)]
        self.reverse_adjacency = defaultdict(list)  # target_id -> [(relationship, source_id)]
        self._build_ercot_graph()
    
    def add_node(self, node_id: str, node_type: str, properties: dict = None):
        """Add a node to the graph."""
        node = Node(node_id, node_type, properties)
        self.nodes[node_id] = node
        return node
    
    def add_edge(self, source: str, relationship: str, target: str,
                 properties: dict = None):
        """Add a directed edge between nodes."""
        edge = Edge(source, relationship, target, properties)
        self.edges.append(edge)
        self.adjacency[source].append((relationship, target))
        self.reverse_adjacency[target].append((relationship, source))
        
        if source in self.nodes:
            self.nodes[source].edges_out.append((relationship, target))
        if target in self.nodes:
            self.nodes[target].edges_in.append((relationship, source))
    
    def _build_ercot_graph(self):
        """Build the ERCOT grid knowledge graph."""
        
        # === ZONES ===
        zones = {
            'zone_houston': {'name': 'Houston', 'hub': 'HB_HOUSTON', 'peak_load_mw': 22000},
            'zone_north': {'name': 'North', 'hub': 'HB_NORTH', 'peak_load_mw': 18000},
            'zone_south': {'name': 'South', 'hub': 'HB_SOUTH', 'peak_load_mw': 8000},
            'zone_west': {'name': 'West', 'hub': 'HB_WEST', 'peak_load_mw': 5000},
            'zone_panhandle': {'name': 'Panhandle', 'hub': 'HB_PAN', 'peak_load_mw': 2000},
        }
        for zid, props in zones.items():
            self.add_node(zid, 'zone', props)
        
        # === GENERATORS ===
        generators = [
            ('gen_stp', 'STP Nuclear', 'nuclear', 2700, 'zone_south', 'nrg'),
            ('gen_comanche', 'Comanche Peak', 'nuclear', 2400, 'zone_north', 'vistra'),
            ('gen_limestone', 'Limestone', 'coal', 1800, 'zone_north', 'nrg'),
            ('gen_martin_lake', 'Martin Lake', 'coal', 2250, 'zone_north', 'vistra'),
            ('gen_cedar_bayou', 'Cedar Bayou', 'gas_ccgt', 2400, 'zone_houston', 'calpine'),
            ('gen_odessa', 'Odessa CCGT', 'gas_ccgt', 800, 'zone_west', 'independent'),
            ('gen_midland', 'Midland Peakers', 'gas_ct', 600, 'zone_west', 'independent'),
            ('gen_laredo', 'Laredo Gas', 'gas_ccgt', 500, 'zone_south', 'independent'),
            ('gen_sweetwater', 'Sweetwater Wind', 'wind', 1200, 'zone_west', 'nextera'),
            ('gen_roscoe', 'Roscoe Wind', 'wind', 782, 'zone_west', 'rwe'),
            ('gen_panhandle_wind', 'Panhandle Wind Complex', 'wind', 3000, 'zone_panhandle', 'various'),
            ('gen_coastal_wind', 'Coastal Wind', 'wind', 1500, 'zone_south', 'various'),
            ('gen_west_solar', 'West TX Solar', 'solar', 5000, 'zone_west', 'various'),
            ('gen_central_solar', 'Central TX Solar', 'solar', 3000, 'zone_north', 'various'),
            ('gen_permian_bess', 'Permian BESS', 'battery', 500, 'zone_west', 'plus_power'),
            ('gen_houston_bess', 'Houston BESS', 'battery', 300, 'zone_houston', 'various'),
        ]
        
        for gid, name, fuel, capacity, zone, operator in generators:
            self.add_node(gid, 'generator', {
                'name': name, 'fuel': fuel, 'capacity_mw': capacity, 'operator': operator,
            })
            self.add_edge(gid, 'located_in', zone)
            self.add_edge(gid, 'supplies', zone)
        
        # === TRANSMISSION ===
        transmission = [
            ('tx_west_houston', 'West-Houston 345kV', 'zone_west', 'zone_houston', 8000),
            ('tx_west_north', 'West-North 345kV', 'zone_west', 'zone_north', 5000),
            ('tx_north_houston', 'North-Houston 345kV', 'zone_north', 'zone_houston', 12000),
            ('tx_south_houston', 'South-Houston 345kV', 'zone_south', 'zone_houston', 6000),
            ('tx_pan_west', 'Panhandle-West 345kV', 'zone_panhandle', 'zone_west', 4000),
        ]
        
        for tid, name, from_z, to_z, capacity in transmission:
            self.add_node(tid, 'transmission', {
                'name': name, 'capacity_mw': capacity,
            })
            self.add_edge(from_z, 'connected_via', tid)
            self.add_edge(tid, 'connects_to', to_z)
            self.add_edge(to_z, 'connected_via', tid)
            self.add_edge(tid, 'connects_to', from_z)
        
        # === OPERATORS ===
        operators = {
            'op_vistra': {'name': 'Vistra', 'type': 'IPP', 'fleet_mw': 38000},
            'op_nrg': {'name': 'NRG Energy', 'type': 'IPP', 'fleet_mw': 23000},
            'op_calpine': {'name': 'Calpine', 'type': 'IPP', 'fleet_mw': 12000},
            'op_nextera': {'name': 'NextEra', 'type': 'renewable', 'fleet_mw': 8000},
            'op_plus_power': {'name': 'Plus Power', 'type': 'storage', 'fleet_mw': 2000},
        }
        
        for oid, props in operators.items():
            self.add_node(oid, 'operator', props)
        
        # Operator -> generator ownership
        owner_map = {
            'vistra': ['gen_comanche', 'gen_martin_lake'],
            'nrg': ['gen_stp', 'gen_limestone'],
            'calpine': ['gen_cedar_bayou'],
            'nextera': ['gen_sweetwater'],
            'plus_power': ['gen_permian_bess'],
        }
        for owner, gens in owner_map.items():
            for gen in gens:
                self.add_edge(f'op_{owner}', 'owns', gen)
        
        # === MARKET PRODUCTS ===
        products = [
            ('prod_energy', 'Energy', {'market': 'DAM/RTM', 'settlement': '15-min'}),
            ('prod_reg_up', 'Regulation Up', {'market': 'DAM', 'response': '4 seconds'}),
            ('prod_reg_down', 'Regulation Down', {'market': 'DAM', 'response': '4 seconds'}),
            ('prod_rrs', 'RRS', {'market': 'DAM', 'response': '0.5 seconds'}),
            ('prod_ecrs', 'ECRS', {'market': 'DAM', 'response': '10 minutes'}),
            ('prod_drrs', 'DRRS', {'market': 'DAM', 'response': '30 minutes', 'duration': '4 hours'}),
        ]
        
        for pid, name, props in products:
            self.add_node(pid, 'market_product', {'name': name, **props})
        
        # Batteries can participate in these products
        for bess in ['gen_permian_bess', 'gen_houston_bess']:
            for prod in ['prod_energy', 'prod_reg_up', 'prod_reg_down', 'prod_rrs', 'prod_ecrs', 'prod_drrs']:
                self.add_edge(bess, 'can_provide', prod)
    
    def get_node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)
    
    def get_neighbors(self, node_id: str, relationship: str = None) -> List[Tuple[str, str]]:
        """Get neighboring nodes, optionally filtered by relationship."""
        neighbors = self.adjacency.get(node_id, [])
        if relationship:
            neighbors = [(r, t) for r, t in neighbors if r == relationship]
        return neighbors
    
    def get_incoming(self, node_id: str, relationship: str = None) -> List[Tuple[str, str]]:
        """Get nodes that point to this node."""
        incoming = self.reverse_adjacency.get(node_id, [])
        if relationship:
            incoming = [(r, s) for r, s in incoming if r == relationship]
        return incoming
    
    def traverse(self, start_id: str, max_depth: int = 3,
                 relationship_filter: List[str] = None) -> List[dict]:
        """
        Breadth-first traversal from a starting node.
        Returns all reachable nodes within max_depth hops.
        """
        visited = set()
        queue = [(start_id, 0, [])]  # (node_id, depth, path)
        results = []
        
        while queue:
            node_id, depth, path = queue.pop(0)
            
            if node_id in visited or depth > max_depth:
                continue
            
            visited.add(node_id)
            node = self.get_node(node_id)
            
            if node and depth > 0:
                results.append({
                    'node': node.to_dict(),
                    'depth': depth,
                    'path': path,
                })
            
            for rel, target in self.adjacency.get(node_id, []):
                if relationship_filter and rel not in relationship_filter:
                    continue
                if target not in visited:
                    queue.append((target, depth + 1, path + [f"{node_id} --{rel}--> {target}"]))
        
        return results
    
    def find_impact_chain(self, event_node: str, event_type: str) -> List[dict]:
        """
        Trace the impact of an event through the grid.
        
        E.g., generator outage -> zone supply reduced -> 
        price increase -> transmission congestion
        """
        node = self.get_node(event_node)
        if not node:
            return []
        
        impacts = []
        
        if event_type == 'outage' and node.type == 'generator':
            capacity = node.properties.get('capacity_mw', 0)
            fuel = node.properties.get('fuel', 'unknown')
            
            # What zone loses supply?
            zones_affected = self.get_neighbors(event_node, 'located_in')
            for _, zone_id in zones_affected:
                zone = self.get_node(zone_id)
                if zone:
                    zone_load = zone.properties.get('peak_load_mw', 10000)
                    impact_pct = capacity / zone_load * 100
                    
                    impacts.append({
                        'step': 1,
                        'description': f"{node.properties.get('name', event_node)} ({capacity}MW {fuel}) goes offline",
                        'affected': zone.properties.get('name', zone_id),
                        'impact': f"Loses {capacity}MW ({impact_pct:.1f}% of peak load)",
                    })
                    
                    # What other generators in this zone could compensate?
                    other_gens = self.get_incoming(zone_id, 'located_in')
                    replacement = []
                    for _, gen_id in other_gens:
                        if gen_id != event_node:
                            gen = self.get_node(gen_id)
                            if gen and gen.properties.get('fuel') in ['gas_ccgt', 'gas_ct']:
                                replacement.append(gen.properties.get('name', gen_id))
                    
                    if replacement:
                        impacts.append({
                            'step': 2,
                            'description': f"Gas plants must ramp up to fill gap",
                            'affected': ', '.join(replacement[:3]),
                            'impact': f"Higher-cost generation sets the price",
                        })
                    
                    # What transmission connects this zone?
                    tx_lines = self.get_neighbors(zone_id, 'connected_via')
                    for _, tx_id in tx_lines:
                        tx = self.get_node(tx_id)
                        if tx:
                            tx_cap = tx.properties.get('capacity_mw', 0)
                            if capacity > tx_cap * 0.3:
                                impacts.append({
                                    'step': 3,
                                    'description': f"Transmission constraint risk on {tx.properties.get('name', tx_id)}",
                                    'affected': tx.properties.get('name', tx_id),
                                    'impact': f"Outage is {capacity/tx_cap*100:.0f}% of line capacity, congestion likely",
                                })
        
        elif event_type == 'transmission_constraint':
            tx = self.get_node(event_node)
            if tx:
                # What zones are connected by this line?
                connected = self.get_neighbors(event_node, 'connects_to')
                zone_names = []
                for _, z_id in connected:
                    z = self.get_node(z_id)
                    if z:
                        zone_names.append(z.properties.get('name', z_id))
                
                impacts.append({
                    'step': 1,
                    'description': f"Transmission constraint on {tx.properties.get('name', event_node)}",
                    'affected': ' and '.join(zone_names),
                    'impact': 'Price separation between zones, congestion premium',
                })
        
        return impacts
    
    def stats(self) -> dict:
        return {
            'nodes': len(self.nodes),
            'edges': len(self.edges),
            'node_types': dict(defaultdict(int, {n.type: 1 for n in self.nodes.values()})),
        }


# ==================================================================
# GRAPH RETRIEVER
# ==================================================================

class GraphRetriever:
    """
    Answers structured queries by traversing the knowledge graph.
    Finds RELATIONSHIPS, not just SIMILARITY.
    """
    
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
    
    def retrieve(self, query: dict) -> dict:
        """
        Route a structured query to the right graph traversal.
        """
        query_type = query.get('type', 'general')
        
        if query_type == 'outage_impact':
            return self._outage_impact(query)
        elif query_type == 'zone_supply':
            return self._zone_supply(query)
        elif query_type == 'transmission_risk':
            return self._transmission_risk(query)
        elif query_type == 'battery_opportunities':
            return self._battery_opportunities(query)
        elif query_type == 'operator_exposure':
            return self._operator_exposure(query)
        else:
            return self._general_traverse(query)
    
    def _outage_impact(self, query: dict) -> dict:
        """Trace impact of a generator outage through the grid."""
        gen_id = query.get('generator_id', '')
        
        impacts = self.graph.find_impact_chain(gen_id, 'outage')
        gen = self.graph.get_node(gen_id)
        
        return {
            'query_type': 'outage_impact',
            'generator': gen.to_dict() if gen else {},
            'impact_chain': impacts,
            'n_steps': len(impacts),
            'summary': self._summarize_impacts(impacts),
        }
    
    def _zone_supply(self, query: dict) -> dict:
        """What generators supply a zone?"""
        zone_id = query.get('zone_id', 'zone_houston')
        
        suppliers = self.graph.get_incoming(zone_id, 'located_in')
        gens = []
        total_mw = 0
        
        for _, gen_id in suppliers:
            gen = self.graph.get_node(gen_id)
            if gen:
                gens.append(gen.to_dict())
                total_mw += gen.properties.get('capacity_mw', 0)
        
        by_fuel = defaultdict(int)
        for g in gens:
            by_fuel[g['properties'].get('fuel', 'unknown')] += g['properties'].get('capacity_mw', 0)
        
        return {
            'query_type': 'zone_supply',
            'zone': zone_id,
            'generators': gens,
            'total_capacity_mw': total_mw,
            'by_fuel': dict(by_fuel),
        }
    
    def _transmission_risk(self, query: dict) -> dict:
        """Assess transmission constraint risk between zones."""
        from_zone = query.get('from_zone', 'zone_west')
        to_zone = query.get('to_zone', 'zone_houston')
        
        # Find transmission lines between zones
        from_tx = self.graph.get_neighbors(from_zone, 'connected_via')
        
        relevant_lines = []
        for _, tx_id in from_tx:
            tx_targets = self.graph.get_neighbors(tx_id, 'connects_to')
            for _, target in tx_targets:
                if target == to_zone:
                    tx = self.graph.get_node(tx_id)
                    if tx:
                        relevant_lines.append(tx.to_dict())
        
        total_capacity = sum(l['properties'].get('capacity_mw', 0) for l in relevant_lines)
        
        return {
            'query_type': 'transmission_risk',
            'from': from_zone,
            'to': to_zone,
            'lines': relevant_lines,
            'total_capacity_mw': total_capacity,
            'congestion_risk': 'high' if total_capacity < 6000 else 'medium' if total_capacity < 10000 else 'low',
        }
    
    def _battery_opportunities(self, query: dict) -> dict:
        """What markets can a battery participate in?"""
        battery_id = query.get('battery_id', 'gen_permian_bess')
        
        products = self.graph.get_neighbors(battery_id, 'can_provide')
        zone = self.graph.get_neighbors(battery_id, 'located_in')
        
        product_details = []
        for _, prod_id in products:
            prod = self.graph.get_node(prod_id)
            if prod:
                product_details.append(prod.to_dict())
        
        zone_detail = None
        if zone:
            z = self.graph.get_node(zone[0][1])
            if z:
                zone_detail = z.to_dict()
        
        return {
            'query_type': 'battery_opportunities',
            'battery': self.graph.get_node(battery_id).to_dict() if self.graph.get_node(battery_id) else {},
            'zone': zone_detail,
            'available_products': product_details,
            'n_products': len(product_details),
        }
    
    def _operator_exposure(self, query: dict) -> dict:
        """What does an operator own and where?"""
        operator_id = query.get('operator_id', 'op_vistra')
        
        owned = self.graph.get_neighbors(operator_id, 'owns')
        assets = []
        total_mw = 0
        zones = set()
        
        for _, gen_id in owned:
            gen = self.graph.get_node(gen_id)
            if gen:
                assets.append(gen.to_dict())
                total_mw += gen.properties.get('capacity_mw', 0)
                gen_zones = self.graph.get_neighbors(gen_id, 'located_in')
                for _, z in gen_zones:
                    zone = self.graph.get_node(z)
                    if zone:
                        zones.add(zone.properties.get('name', z))
        
        return {
            'query_type': 'operator_exposure',
            'operator': self.graph.get_node(operator_id).to_dict() if self.graph.get_node(operator_id) else {},
            'assets': assets,
            'total_mw': total_mw,
            'zones': list(zones),
        }
    
    def _general_traverse(self, query: dict) -> dict:
        """General graph traversal from any starting node."""
        start = query.get('start_node', '')
        depth = query.get('max_depth', 2)
        
        results = self.graph.traverse(start, depth)
        return {
            'query_type': 'traverse',
            'start': start,
            'depth': depth,
            'nodes_found': len(results),
            'results': results[:10],
        }
    
    def _summarize_impacts(self, impacts: List[dict]) -> str:
        """Generate a one-line summary of impact chain."""
        if not impacts:
            return "No significant grid impact detected."
        
        parts = [i['description'] for i in impacts[:3]]
        return ' -> '.join(parts)


# ==================================================================
# QUERY ROUTER
# ==================================================================

class QueryRouter:
    """
    Looks at a query and decides: vector store, knowledge graph, or both?
    
    Vector store: "what happened last time prices were this high?"
    Graph: "what generators are offline in North zone?"
    Both: "wind is dropping in West TX, what happened historically
           AND what grid infrastructure is affected?"
    """
    
    def route(self, situation: dict, context_signals: dict = None) -> dict:
        """
        Decide which retrieval strategy to use.
        
        Returns:
            {
                'use_vector': True/False,
                'use_graph': True/False,
                'vector_weight': 0.0-1.0,
                'graph_weight': 0.0-1.0,
                'graph_queries': [...],
                'reasoning': str,
            }
        """
        signals = context_signals or {}
        price = situation.get('price', 30)
        wind = situation.get('wind_speed', 15)
        temp = situation.get('temperature', 75)
        hour = situation.get('hour', 12)
        
        use_vector = True  # almost always want historical patterns
        use_graph = False
        vector_weight = 0.6
        graph_weight = 0.4
        graph_queries = []
        reasons = []
        
        # Outage signal -> definitely use graph
        if signals.get('outage'):
            use_graph = True
            graph_queries.append({
                'type': 'outage_impact',
                'generator_id': signals.get('outage_generator', ''),
            })
            vector_weight = 0.4
            graph_weight = 0.6
            reasons.append('Generator outage detected, tracing grid impact')
        
        # Extreme wind -> graph for topology awareness
        if wind < 7 or wind > 28:
            use_graph = True
            graph_queries.append({
                'type': 'zone_supply',
                'zone_id': 'zone_west',
            })
            reasons.append(f'Wind at {wind}mph, checking West TX supply stack')
        
        # High price -> graph for congestion check
        if price > 80:
            use_graph = True
            graph_queries.append({
                'type': 'transmission_risk',
                'from_zone': 'zone_west',
                'to_zone': 'zone_houston',
            })
            reasons.append(f'High price ${price}, checking transmission congestion')
        
        # Extreme heat -> graph for supply adequacy
        if temp > 100:
            use_graph = True
            graph_queries.append({
                'type': 'zone_supply',
                'zone_id': 'zone_houston',
            })
            vector_weight = 0.3
            graph_weight = 0.7
            reasons.append('Extreme heat, checking system supply adequacy')
        
        # Battery strategy -> always check opportunities
        if signals.get('check_as', False):
            use_graph = True
            graph_queries.append({
                'type': 'battery_opportunities',
                'battery_id': signals.get('battery_id', 'gen_permian_bess'),
            })
            reasons.append('Checking ancillary service opportunities')
        
        # Normal conditions -> vector only, graph adds overhead
        if not use_graph:
            vector_weight = 1.0
            graph_weight = 0.0
            reasons.append('Normal conditions, historical patterns sufficient')
        
        return {
            'use_vector': use_vector,
            'use_graph': use_graph,
            'vector_weight': vector_weight,
            'graph_weight': graph_weight,
            'graph_queries': graph_queries,
            'reasoning': ' | '.join(reasons) if reasons else 'Default routing',
        }


# ==================================================================
# FUSION LAYER
# ==================================================================

class FusionLayer:
    """
    Merges vector retrieval results and graph retrieval results
    into one coherent context for Claude.
    """
    
    def fuse(self, vector_results: List[dict], graph_results: List[dict],
             routing: dict) -> dict:
        """
        Combine vector and graph results with appropriate weighting.
        """
        v_weight = routing.get('vector_weight', 0.5)
        g_weight = routing.get('graph_weight', 0.5)
        
        # Build fused context
        sections = []
        
        # Vector section (historical patterns)
        if vector_results and v_weight > 0:
            section = self._format_vector_results(vector_results)
            sections.append({
                'source': 'historical_patterns',
                'weight': v_weight,
                'content': section,
                'n_items': len(vector_results),
            })
        
        # Graph section (structural knowledge)
        if graph_results and g_weight > 0:
            section = self._format_graph_results(graph_results)
            sections.append({
                'source': 'grid_knowledge',
                'weight': g_weight,
                'content': section,
                'n_items': len(graph_results),
            })
        
        # Build the combined context string
        context_parts = []
        
        for s in sorted(sections, key=lambda x: x['weight'], reverse=True):
            context_parts.append(f"\n[{s['source'].upper()} (weight: {s['weight']:.0%})]")
            context_parts.append(s['content'])
        
        return {
            'fused_context': '\n'.join(context_parts),
            'sections': sections,
            'vector_weight': v_weight,
            'graph_weight': g_weight,
            'total_sources': sum(s['n_items'] for s in sections),
        }
    
    def _format_vector_results(self, results: List[dict]) -> str:
        """Format vector search results for context."""
        if not results:
            return "No historical patterns found."
        
        lines = [f"Found {len(results)} similar historical situations:"]
        
        # Group by action for summary
        by_action = defaultdict(list)
        for r in results:
            by_action[r.get('action', 'HOLD')].append(r)
        
        for action, trades in sorted(by_action.items(), key=lambda x: len(x[1]), reverse=True):
            revenues = [t.get('revenue', 0) for t in trades]
            correct = sum(1 for t in trades if t.get('was_correct'))
            lines.append(
                f"  {action}: {len(trades)} times, avg revenue ${np.mean(revenues):.0f}, "
                f"{correct}/{len(trades)} correct"
            )
        
        return '\n'.join(lines)
    
    def _format_graph_results(self, results: List[dict]) -> str:
        """Format graph query results for context."""
        if not results:
            return "No structural grid information relevant."
        
        lines = ["Grid topology and structural information:"]
        
        for result in results:
            qtype = result.get('query_type', 'unknown')
            
            if qtype == 'outage_impact':
                gen = result.get('generator', {})
                lines.append(f"\n  OUTAGE: {gen.get('properties', {}).get('name', 'Unknown')} "
                           f"({gen.get('properties', {}).get('capacity_mw', 0)}MW)")
                for impact in result.get('impact_chain', []):
                    lines.append(f"    Step {impact['step']}: {impact['description']}")
                    lines.append(f"      Impact: {impact['impact']}")
            
            elif qtype == 'zone_supply':
                lines.append(f"\n  ZONE SUPPLY: {result.get('zone', 'unknown')}")
                lines.append(f"    Total capacity: {result.get('total_capacity_mw', 0):,}MW")
                for fuel, mw in result.get('by_fuel', {}).items():
                    lines.append(f"    {fuel}: {mw:,}MW")
            
            elif qtype == 'transmission_risk':
                lines.append(f"\n  TRANSMISSION: {result.get('from', '?')} to {result.get('to', '?')}")
                lines.append(f"    Capacity: {result.get('total_capacity_mw', 0):,}MW")
                lines.append(f"    Congestion risk: {result.get('congestion_risk', '?')}")
            
            elif qtype == 'battery_opportunities':
                lines.append(f"\n  BATTERY MARKETS: {result.get('n_products', 0)} products available")
                for prod in result.get('available_products', []):
                    lines.append(f"    {prod.get('properties', {}).get('name', '?')}")
        
        return '\n'.join(lines)


# ==================================================================
# HYBRID RAG ENGINE
# ==================================================================

class HybridRAG:
    """
    The complete hybrid retrieval system.
    
    Vector store + Knowledge graph + Query router + Fusion layer.
    
    Every query gets:
    1. Routed to the right retrieval strategy
    2. Vector search for historical patterns
    3. Graph traversal for structural knowledge
    4. Results fused into unified context
    """
    
    def __init__(self):
        self.graph = KnowledgeGraph()
        self.graph_retriever = GraphRetriever(self.graph)
        self.router = QueryRouter()
        self.fusion = FusionLayer()
        
        # Vector store (reuse from RAG v2)
        from core.rag_engine_v2 import PersistentVectorIndex, SituationEncoder
        self.vector_index = PersistentVectorIndex(':memory:')
        self.encoder = SituationEncoder()
    
    def add_experience(self, situation: dict, action: str, revenue: float,
                       was_correct: bool):
        """Add a trade experience to the vector store."""
        vector = self.encoder.encode(situation)
        meta = {**situation, 'action': action, 'revenue': revenue,
                'was_correct': 1 if was_correct else 0}
        self.vector_index.add(vector, meta)
    
    def retrieve(self, situation: dict, context_signals: dict = None) -> dict:
        """
        Full hybrid retrieval pipeline.
        """
        # Step 1: Route the query
        routing = self.router.route(situation, context_signals)
        
        # Step 2: Vector retrieval (if routed)
        vector_results = []
        if routing['use_vector']:
            vector = self.encoder.encode(situation)
            raw = self.vector_index.search(vector, top_k=10)
            vector_results = [{'similarity': s, **m} for s, m, t in raw]
        
        # Step 3: Graph retrieval (if routed)
        graph_results = []
        if routing['use_graph']:
            for query in routing['graph_queries']:
                result = self.graph_retriever.retrieve(query)
                graph_results.append(result)
        
        # Step 4: Fuse results
        fused = self.fusion.fuse(vector_results, graph_results, routing)
        
        return {
            'routing': routing,
            'vector_results': len(vector_results),
            'graph_results': len(graph_results),
            'fused_context': fused['fused_context'],
            'total_sources': fused['total_sources'],
            'sections': fused['sections'],
        }


def demo():
    """Demonstrate hybrid RAG."""
    
    print("=" * 70)
    print("VoltStream AI — Hybrid RAG Engine")
    print("=" * 70)
    print()
    print("  Vector store: finds SIMILAR situations")
    print("  Knowledge graph: finds CONNECTED information")
    print("  Query router: decides which to use")
    print("  Fusion layer: merges both into one context")
    print()
    
    hybrid = HybridRAG()
    
    # Show graph stats
    stats = hybrid.graph.stats()
    print(f"  Knowledge Graph: {stats['nodes']} nodes, {stats['edges']} edges")
    print(f"  Node types: generators, zones, transmission, operators, products")
    
    # Load some trade history
    np.random.seed(42)
    for _ in range(200):
        hour = np.random.randint(0, 24)
        price = 30 + np.random.normal(0, 20)
        hybrid.add_experience(
            {'price': price, 'hour': hour, 'temperature': 80, 'wind_speed': 15,
             'solar_ghi': 500 if 8 < hour < 18 else 0, 'soc': 0.5,
             'price_1h_ago': price + np.random.normal(0, 5),
             'price_4h_ago': price + np.random.normal(0, 10)},
            np.random.choice(['CHARGE', 'DISCHARGE', 'HOLD']),
            np.random.normal(500, 300),
            np.random.random() > 0.3,
        )
    
    print(f"  Vector index: {hybrid.vector_index.size} experiences\n")
    
    # Test scenarios
    scenarios = [
        {
            'name': 'Normal conditions (vector only)',
            'situation': {'price': 35, 'hour': 14, 'temperature': 82, 'wind_speed': 15, 'solar_ghi': 700, 'soc': 0.5, 'price_1h_ago': 33, 'price_4h_ago': 28},
            'signals': {},
        },
        {
            'name': 'Generator outage (graph + vector)',
            'situation': {'price': 55, 'hour': 18, 'temperature': 90, 'wind_speed': 10, 'solar_ghi': 100, 'soc': 0.7, 'price_1h_ago': 45, 'price_4h_ago': 30},
            'signals': {'outage': True, 'outage_generator': 'gen_limestone'},
        },
        {
            'name': 'Wind dying in West TX (graph + vector)',
            'situation': {'price': 75, 'hour': 17, 'temperature': 95, 'wind_speed': 5, 'solar_ghi': 300, 'soc': 0.65, 'price_1h_ago': 60, 'price_4h_ago': 25},
            'signals': {},
        },
        {
            'name': 'Extreme heat wave (graph-heavy)',
            'situation': {'price': 120, 'hour': 16, 'temperature': 108, 'wind_speed': 6, 'solar_ghi': 500, 'soc': 0.80, 'price_1h_ago': 85, 'price_4h_ago': 45},
            'signals': {},
        },
    ]
    
    for scenario in scenarios:
        result = hybrid.retrieve(scenario['situation'], scenario['signals'])
        routing = result['routing']
        
        print(f"  {'='*58}")
        print(f"  {scenario['name'].upper()}")
        print(f"  {'='*58}")
        
        s = scenario['situation']
        print(f"  Price: ${s['price']} | Hour: {s['hour']}:00 | Temp: {s['temperature']}F | Wind: {s['wind_speed']}mph")
        
        print(f"\n  ROUTING DECISION:")
        print(f"    Vector store: {'YES' if routing['use_vector'] else 'NO'} (weight: {routing['vector_weight']:.0%})")
        print(f"    Knowledge graph: {'YES' if routing['use_graph'] else 'NO'} (weight: {routing['graph_weight']:.0%})")
        print(f"    Reason: {routing['reasoning']}")
        
        if routing['graph_queries']:
            print(f"    Graph queries: {[q['type'] for q in routing['graph_queries']]}")
        
        print(f"\n  RETRIEVAL RESULTS:")
        print(f"    Vector results: {result['vector_results']}")
        print(f"    Graph results: {result['graph_results']}")
        print(f"    Total sources: {result['total_sources']}")
        
        print(f"\n  FUSED CONTEXT (what Claude sees):")
        for line in result['fused_context'].split('\n')[:15]:
            print(f"    {line}")
        if result['fused_context'].count('\n') > 15:
            print(f"    ... ({result['fused_context'].count(chr(10)) - 15} more lines)")
        print()
    
    print(f"{'='*70}")
    print("HYBRID RAG CAPABILITY:")
    print(f"{'='*70}")
    print()
    print("  Normal conditions: Router sends to vector store only.")
    print("  Fast, efficient, historical patterns are enough.")
    print()
    print("  Generator outage: Router activates BOTH retrievers.")
    print("  Vector finds similar past outages and their outcomes.")
    print("  Graph traces the outage through the physical grid:")
    print("  Limestone (1800MW) -> Zone North loses supply ->")
    print("  Gas plants ramp up -> Transmission constraint risk.")
    print()
    print("  Extreme heat: Router shifts weight to graph (70%).")
    print("  Graph checks total supply adequacy in Houston zone.")
    print("  Vector provides historical heat event outcomes.")
    print("  Claude sees BOTH physics AND patterns.")
    print()
    print("  This is true hybrid RAG. Not just one retrieval method.")
    print("  The right tool for the right question, every time.")


if __name__ == '__main__':
    demo()
