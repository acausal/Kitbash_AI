#!/usr/bin/env python3
"""
L2 Working Theory Service - Read-Only Audit Layer

Provides inspection APIs for the L2 (working theory) layer.
Exposes snapshots of:
- Locked phantoms (crystallization candidates)
- Hot procedural edges (frequently traversed relationships)
- MTR epistemic state (temporal reasoning summary)

Used by sleep pipeline (Stage 3) to understand emerging hypotheses
and by debugging/diagnostics for transparency.

Author: Kitbash Team
Date: June 2026
Phase: Pre-Phase-5 (Mutation 2)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


class L2WorkingTheoryService:
    """
    Read-only audit service for L2 (working theory) layer.
    
    Exposes snapshots of locked phantoms, hot edges, and MTR state
    without modifying any underlying data.
    """
    
    def __init__(self, dream_bucket_dir: str, grain_orchestrator=None):
        """
        Initialize L2 service.
        
        Args:
            dream_bucket_dir: Path to dream bucket (for edge graph access)
            grain_orchestrator: ShannonGrainOrchestrator instance (for phantoms)
        """
        self.dream_bucket_dir = Path(dream_bucket_dir)
        self.indices_dir = self.dream_bucket_dir / "indices"
        self.grain_orchestrator = grain_orchestrator
    
    def get_working_theory_snapshot(self, top_phantoms: int = 10, top_edges: int = 20) -> Dict[str, Any]:
        """
        Get full L2 working theory snapshot.
        
        Returns:
            Dict with:
            - locked_phantoms: Top N phantoms ready for crystallization
            - hot_edges: Top N frequently traversed procedural edges
            - timestamp: When snapshot was taken
            - metadata: Statistics about phantom/edge distribution
        
        Args:
            top_phantoms: How many locked phantoms to include
            top_edges: How many hot edges to include
        """
        snapshot = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'locked_phantoms': self._get_locked_phantoms_snapshot(top_phantoms),
            'hot_edges': self._get_hot_edges_snapshot(top_edges),
            'metadata': {
                'snapshot_type': 'L2_working_theory',
                'total_phantoms_available': 0,
                'total_edges_available': 0,
            }
        }
        
        return snapshot
    
    def _get_locked_phantoms_snapshot(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Get locked phantoms ready for crystallization (with polarity).
        
        Args:
            top_n: Number of top phantoms to return
        
        Returns:
            List of phantom snapshots, sorted by lock strength
        """
        if self.grain_orchestrator is None:
            return []
        
        try:
            locked = self.grain_orchestrator.get_locked_phantoms(top_n=top_n * 2)  # Get more, filter below
            
            # Convert to audit-safe format
            snapshots = []
            for phantom in locked:
                snapshot = {
                    'phantom_id': phantom.get('phantom_id'),
                    'lock_strength': phantom.get('lock_strength', 0.0),
                    'supporting_queries': phantom.get('supporting_queries', 0),
                    'polarity': phantom.get('polarity', 0.0) if isinstance(phantom, dict) else 0.0,
                    'expected_grain': phantom.get('expected_grain'),
                    'concepts': phantom.get('concepts', [])[:5],  # Top 5 concepts
                }
                snapshots.append(snapshot)
            
            return snapshots[:top_n]
        
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error getting locked phantoms: {e}")
            return []
    
    def _get_hot_edges_snapshot(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        Get frequently traversed procedural edges (hot edges).
        
        Args:
            top_n: Number of top edges to return
        
        Returns:
            List of edge snapshots, sorted by traversal count
        """
        try:
            edge_graph = self._load_edge_graph()
            if not edge_graph:
                return []
            
            edges = edge_graph.get('edges', {})
            
            # Rank by traversal count
            ranked = sorted(
                edges.items(),
                key=lambda x: x[1].get('traversal_count', 0),
                reverse=True
            )
            
            snapshots = []
            for edge_key, edge_data in ranked[:top_n]:
                snapshot = {
                    'edge_key': edge_key,
                    'source_fact_id': edge_data.get('source_fact_id'),
                    'target_fact_id': edge_data.get('target_fact_id'),
                    'source_cartridge': edge_data.get('source_cartridge'),
                    'target_cartridge': edge_data.get('target_cartridge'),
                    'edge_type': edge_data.get('edge_type'),
                    'edge_weight': edge_data.get('edge_weight', 0.0),
                    'traversal_count': edge_data.get('traversal_count', 0),
                    'last_traversed': edge_data.get('last_traversed'),
                }
                snapshots.append(snapshot)
            
            return snapshots
        
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error getting hot edges: {e}")
            return []
    
    def get_epistemological_state(self) -> Dict[str, Any]:
        """
        Get summary of epistemological layer state.
        
        Returns:
            Dict with:
            - layer_breakdown: Count of grains by type (axiom vs observation)
            - crystallization_stats: Recent crystallization activity
            - learning_velocity: Rate of new grain creation
        """
        state = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'layer_breakdown': {},
            'crystallization_stats': {},
            'learning_velocity': 0.0,
        }
        
        if self.grain_orchestrator is None:
            return state
        
        try:
            stats = self.grain_orchestrator.get_stats()
            grain_registry_stats = stats.get('grain_registry', {})
            
            state['layer_breakdown'] = {
                'axioms': grain_registry_stats.get('axioms', 0),
                'observations': grain_registry_stats.get('observations', 0),
                'avg_confidence_axiom': grain_registry_stats.get('avg_confidence_axiom', 0.0),
                'avg_confidence_observation': grain_registry_stats.get('avg_confidence_observation', 0.0),
            }
            
            state['crystallization_stats'] = stats.get('crystallization_stats', {})
        
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error getting epistemological state: {e}")
        
        return state
    
    def get_hot_edges_by_cartridge(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get hot edges grouped by source cartridge.
        
        Useful for understanding intra-domain learning patterns.
        
        Returns:
            Dict mapping cartridge_id → list of hot edges within that cartridge
        """
        try:
            edge_graph = self._load_edge_graph()
            if not edge_graph:
                return {}
            
            edges = edge_graph.get('edges', {})
            grouped = {}
            
            for edge_key, edge_data in edges.items():
                if edge_data.get('edge_type') != 'intra_cartridge':
                    continue
                
                cartridge = edge_data.get('source_cartridge', 'unknown')
                if cartridge not in grouped:
                    grouped[cartridge] = []
                
                grouped[cartridge].append({
                    'edge_key': edge_key,
                    'target': edge_data.get('target_fact_id'),
                    'weight': edge_data.get('edge_weight'),
                    'traversals': edge_data.get('traversal_count'),
                })
            
            # Sort each cartridge's edges by traversal count
            for cartridge in grouped:
                grouped[cartridge].sort(
                    key=lambda x: x['traversals'],
                    reverse=True
                )
            
            return grouped
        
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error getting edges by cartridge: {e}")
            return {}
    
    def audit_axiom_stability(self) -> Dict[str, Any]:
        """
        Audit axiom grains for stability (immutability validation).
        
        Returns:
            Dict with:
            - total_axioms: Count of axiom grains
            - stable_axioms: Axioms with confidence ≥ 0.98 (very stable)
            - at_risk_axioms: Axioms with confidence < 0.95 (drift risk)
            - confidence_distribution: Histogram of axiom confidence
        """
        audit = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'total_axioms': 0,
            'stable_axioms': 0,
            'at_risk_axioms': 0,
            'confidence_distribution': {},
        }
        
        if self.grain_orchestrator is None:
            return audit
        
        try:
            stats = self.grain_orchestrator.get_stats()
            audit['total_axioms'] = stats.get('grain_registry', {}).get('axioms', 0)
            
            # Note: Full grain inspection would require GrainRegistry direct access
            # For now, report summary stats only
            
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error auditing axioms: {e}")
        
        return audit
    
    # ========================================================================
    # PRIVATE HELPERS
    # ========================================================================
    
    def _load_edge_graph(self) -> Optional[Dict[str, Any]]:
        """Load procedural edge graph index."""
        edge_file = self.indices_dir / "procedural_edge_graph.json"
        
        if not edge_file.exists():
            return None
        
        try:
            with open(edge_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error loading edge graph: {e}")
            return None
    
    def _get_locked_phantoms_from_orchestrator(self, top_n: int) -> List[Dict[str, Any]]:
        """
        Get locked phantoms from grain orchestrator.
        
        This is a helper that calls the orchestrator's public API.
        """
        if self.grain_orchestrator is None:
            return []
        
        try:
            return self.grain_orchestrator.get_locked_phantoms(top_n=top_n)
        except Exception as e:
            print(f"[L2WorkingTheoryService] Error getting locked phantoms: {e}")
            return []
