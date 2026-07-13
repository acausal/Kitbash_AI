#!/usr/bin/env python3
"""
Procedural Edge Extractor - Sleep Stages 1.5 and 2.5

Extracts procedural edges (fact→fact and cartridge→cartridge relationships)
from query traces logged during the day.

Stage 1.5: Intra-Cartridge Edge Extraction
  - Reads traces.jsonl written by query_orchestrator
  - Builds edges from fact chains within single cartridges
  - Assigns confidence based on traversal patterns
  - Writes to procedural_edge_graph index

Stage 2.5: Cross-Cartridge Edge Extraction
  - Reads intra-cartridge edges from Stage 1.5
  - Detects fact relationships that cross cartridge boundaries
  - Builds cross-domain navigation edges
  - Updates procedural_edge_graph with linkages

Edge Structure:
  - source_fact_id / source_grain_id
  - target_fact_id / target_grain_id
  - source_cartridge / target_cartridge
  - edge_weight: float (0.0-1.0, confidence-like)
  - traversal_count: int (times followed)
  - last_traversed: str (ISO timestamp)
  - confidence_mutable: bool (can be updated by Dream Bucket)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
from datetime import datetime, timezone
import statistics

from interfaces.trace_chain import TraceChain, iter_cooccurrence_edges


class ProceduralEdgeExtractor:
    """
    Extracts and consolidates procedural edges from query traces.
    
    Designed to run as Stage 1.5 (intra-cartridge) and Stage 2.5 (cross-cartridge)
    in the sleep pipeline, with disk-driven I/O following the existing pattern.
    """
    
    def __init__(self, dream_bucket_dir: str = 'data/subconscious/dream_bucket'):
        """
        Initialize extractor.
        
        Args:
            dream_bucket_dir: Path to dream bucket root directory
        """
        self.dream_bucket_dir = Path(dream_bucket_dir)
        self.live_dir = self.dream_bucket_dir / "live"
        self.indices_dir = self.dream_bucket_dir / "indices"
        self.traces_file = self.live_dir / "traces.jsonl"
        self.edge_index_file = self.indices_dir / "procedural_edge_graph.json"
    
    # ========================================================================
    # STAGE 1.5: INTRA-CARTRIDGE EDGE EXTRACTION
    # ========================================================================
    
    def extract_intra_cartridge_edges(self) -> Dict[str, Any]:
        """
        Stage 1.5: Extract fact→fact edges within single cartridges.
        
        Reads traces.jsonl, identifies fact sequences within the same cartridge,
        builds edges with confidence metrics based on co-traversal patterns.
        
        Returns:
            Report dict with extraction statistics
        """
        report = {
            'stage': 'stage_1.5_intra_cartridge',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'traces_read': 0,
            'chains_parsed': 0,
            'chains_skipped_bad_shape': 0,
            'chains_by_type': defaultdict(int),
            'edges_created': 0,
            'edges_by_cartridge': defaultdict(int),
            'avg_edge_weight': 0.0,
            'error': None,
        }
        
        # Load or initialize edge graph
        edges = self._load_edge_graph()
        if edges is None:
            edges = {
                'metadata': {
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'stages_applied': ['1.5'],
                    'total_edges': 0,
                    'intra_cartridge_edges': 0,
                    'cross_cartridge_edges': 0,
                },
                'edges': {},  # key: "source:target", value: edge_dict
                'cartridge_index': {},  # cartridge_id -> set of facts
            }
        
        try:
            # Read traces from JSONL
            traces = self._read_traces()
            report['traces_read'] = len(traces)
            
            if not traces:
                report['edges_created'] = 0
                self._save_edge_graph(edges)
                return report
            
            # Extract intra-cartridge edges via the canonical chain contract
            # (SPEC_TRACE_CHAIN_CONTRACT): pairwise co-occurrence over set(fact_ids),
            # canonical a<b, order-independent. No consecutive-pair semantics.
            edges_created = 0
            edge_weights = []

            for trace in traces:
                raw_chain = trace.get('chain')
                if not isinstance(raw_chain, dict):
                    report['chains_skipped_bad_shape'] += 1
                    continue
                try:
                    chain = TraceChain.from_dict(raw_chain)
                except (ValueError, TypeError):
                    report['chains_skipped_bad_shape'] += 1
                    continue
                # parsed successfully: count it and its type
                report['chains_parsed'] += 1
                report['chains_by_type'][chain.chain_type] += 1
                cartridge = (trace.get('context') or {}).get('cartridge') or 'unknown'

                for src, tgt in iter_cooccurrence_edges(chain, cartridge):
                    edge_key = f"{src}->{tgt}"
                    if edge_key not in edges['edges']:
                        edges['edges'][edge_key] = {
                            'source_fact_id': src,
                            'target_fact_id': tgt,
                            'source_cartridge': cartridge,
                            'target_cartridge': cartridge,
                            'edge_type': 'intra_cartridge',
                            'edge_weight': 0.5,
                            'traversal_count': 0,
                            'confidence_mutable': True,
                            'first_traversed': datetime.now(timezone.utc).isoformat(),
                            'last_traversed': datetime.now(timezone.utc).isoformat(),
                        }
                        edges_created += 1

                    edge = edges['edges'][edge_key]
                    edge['traversal_count'] += 1
                    edge['last_traversed'] = datetime.now(timezone.utc).isoformat()
                    traversals = edge['traversal_count']
                    edge['edge_weight'] = min(0.95, 0.5 + (0.4 * (traversals / (traversals + 10))))
                    edge_weights.append(edge['edge_weight'])

                    if cartridge not in edges['cartridge_index']:
                        edges['cartridge_index'][cartridge] = set()
                    edges['cartridge_index'][cartridge].add(src)
                    edges['cartridge_index'][cartridge].add(tgt)
                    report['edges_by_cartridge'][cartridge] += 1

            # Update metadata
            edges['metadata']['intra_cartridge_edges'] = sum(
                1 for e in edges['edges'].values() if e['edge_type'] == 'intra_cartridge'
            )
            edges['metadata']['total_edges'] = len(edges['edges'])
            edges['metadata']['last_updated'] = datetime.now(timezone.utc).isoformat()
            
            if edge_weights:
                report['avg_edge_weight'] = statistics.mean(edge_weights)
            
            report['edges_created'] = edges_created
            
            # Save updated edge graph
            self._save_edge_graph(edges)
            
        except Exception as e:
            report['error'] = str(e)
            return report
        
        return report
    
    # ========================================================================
    # STAGE 2.5: CROSS-CARTRIDGE EDGE EXTRACTION
    # ========================================================================
    
    def extract_cross_cartridge_edges(self) -> Dict[str, Any]:
        """
        Stage 2.5: Extract fact relationships across cartridge boundaries.
        
        Reads intra-cartridge edges from Stage 1.5, detects cross-domain
        relationships, builds navigation edges linking cartridges.
        
        Returns:
            Report dict with extraction statistics
        """
        # REMOVED FROM SCOPE (SPEC_TRACE_CHAIN_CONTRACT): cross-query / cross-cartridge
        # edges depend on deterministic fact_ids ordering and multi-query sessions, neither
        # of which holds today. Deferred ticket: "cross-query/session edges — resume when
        # fact_ids ordering is deterministic and corpus has multi-query sessions."
        # Kept as a no-op stub so callers (run_stage_2_5) stay wired but produce nothing.
        report = {
            'stage': 'stage_2.5_cross_cartridge',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'traces_read': 0,
            'edges_created': 0,
            'edges_by_pair': defaultdict(int),
            'avg_edge_weight': 0.0,
            'error': None,
            'status': 'no-op: cross-query edges removed from scope (deferred)',
        }
        return report
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _read_traces(self) -> List[Dict[str, Any]]:
        """
        Read all traces from traces.jsonl.
        
        Returns:
            List of trace records
        """
        traces = []
        
        if not self.traces_file.exists():
            return traces
        
        try:
            with open(self.traces_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            trace = json.loads(line)
                            traces.append(trace)
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[ProceduralEdgeExtractor] Error reading traces: {e}")
        
        return traces
    
    def _load_edge_graph(self) -> Optional[Dict[str, Any]]:
        """
        Load existing procedural_edge_graph index.
        
        Returns:
            Edge graph dict or None if not found
        """
        if not self.edge_index_file.exists():
            return None
        
        try:
            with open(self.edge_index_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ProceduralEdgeExtractor] Error loading edge graph: {e}")
            return None
    
    def _save_edge_graph(self, edges: Dict[str, Any]) -> bool:
        """
        Save procedural_edge_graph index to disk.
        
        Args:
            edges: Edge graph dict
        
        Returns:
            True if successful
        """
        self.indices_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write to temp file first, then atomic rename
            temp_file = self.edge_index_file.with_suffix('.tmp')
            
            with open(temp_file, 'w') as f:
                json.dump(edges, f, indent=2)
            
            temp_file.replace(self.edge_index_file)
            return True
        
        except Exception as e:
            print(f"[ProceduralEdgeExtractor] Error saving edge graph: {e}")
            return False
