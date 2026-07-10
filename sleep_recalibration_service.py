#!/usr/bin/env python3
"""
Sleep Recalibration Service - Mutation 5

Applies Dream Bucket feedback uniformly to grain confidences and edge weights.

When a high-confidence grain/edge leads to MTR error (inconsistency violation),
both the grain confidence and associated edge weights are penalized uniformly.

This treats procedural (edges) and declarative (grains) knowledge symmetrically:
- Grain confidence: confidence_mutable=true for observations/all edges
- Edge weights: always confidence_mutable=true
- Feedback signal: MTR error or false positive detection

Used by sleep pipeline (Stage 5) to consolidate and correct learning.

Author: Kitbash Team
Date: June 2026
Phase: Pre-Phase-5 (Mutation 5)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from datetime import datetime, timezone

from dream_bucket import log_hypothesis

# AXIOM_CONTRADICTION_THRESHOLD (SPEC_AXIOM_RECALIBRATION.md §2.2 / §4 Step 2):
# an axiom grain is only FLAGGED (never silently decremented) when the MTR error
# signal exceeds this. Set to 0.5 to REUSE MTR's existing high-error band
# (MTR_v6_1.py: error_signal > 0.5 AND returned_confidence > 0.8 is the
# "serious contradiction" marker) rather than inventing a new magic number.
# Observations decrement on any signal above the 0.3 inclusion floor, so the
# band 0.3-0.5 is where observations erode but axioms stay untouched (by design).
AXIOM_CONTRADICTION_THRESHOLD = 0.5
# Existing violation-inclusion floor (sleep_recalibration_service.py:254): a
# violation is even considered for recalibration only above this.
VIOLATION_INCLUSION_FLOOR = 0.3


class RecalibrationService:
    """
    Apply Dream Bucket feedback to grain and edge confidences uniformly.
    
    Reads violations from dream bucket, identifies affected grains/edges,
    and adjusts their confidence/weight scores based on error signals.
    """
    
    def __init__(self, dream_bucket_dir: str = 'data/subconscious/dream_bucket'):
        """
        Initialize recalibration service.
        
        Args:
            dream_bucket_dir: Path to dream bucket root directory
        """
        self.dream_bucket_dir = Path(dream_bucket_dir)
        self.live_dir = self.dream_bucket_dir / "live"
        self.indices_dir = self.dream_bucket_dir / "indices"
    
    def run_recalibration_cycle(self) -> Dict[str, Any]:
        """
        Run full recalibration cycle (Stage 5 of sleep pipeline).
        
        Reads violations from dream bucket, applies uniform penalties to
        grains and edges that were involved in errors.
        
        Returns:
            Report dict with recalibration statistics
        """
        report = {
            'stage': 'stage_5_recalibration',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'violations_processed': 0,
            'grains_updated': 0,
            'edges_updated': 0,
            'total_confidence_adjustment': 0.0,
            'edge_recalibration_status': None,
            'error': None,
        }
        
        try:
            # Load violations from dream bucket
            violations = self._read_violations()
            report['violations_processed'] = len(violations)
            
            if not violations:
                return report
            
            # Load grain and edge indices
            grains_updated, edges_updated, total_adjustment, edge_status = self._apply_feedback(violations)
            
            report['grains_updated'] = grains_updated
            report['edges_updated'] = edges_updated
            report['total_confidence_adjustment'] = total_adjustment
            report['edge_recalibration_status'] = edge_status
        
        except Exception as e:
            report['error'] = str(e)
            return report
        
        return report
    
    # ========================================================================
    # CORE RECALIBRATION LOGIC
    # ========================================================================
    
    def _apply_feedback(
        self,
        violations: List[Dict[str, Any]],
        grain_router: Any = None,
        db_writer: Any = None,
    ) -> Tuple[int, int, float, Dict[str, Any]]:
        """
        Apply feedback from violations to grains and edges.
        
        For each violation:
        1. Extract error signal (confidence_returned, mtr_error)
        2. Identify affected grains/edges (from violation context)
        3. Calculate penalty: confidence_penalty = error_signal * 0.1 (capped)
        4. Update grain confidence and edge weight uniformly
        5. Save updated indices
        
        Args:
            violations: List of violation records from dream bucket
        
        Returns:
            (grains_updated_count, edges_updated_count, total_adjustment, edge_status)
        """
        grains_updates = defaultdict(float)  # fact_id → penalty (kept for total_adjustment)
        edges_updates = defaultdict(float)   # edge_key → penalty (stopgap no-op)

        # Extract feedback signals; resolve fact_id -> (max_error_signal, penalty)
        # so a fact mapping to MULTIPLE grains (1:N) carries one consolidated signal.
        facts: Dict[int, Tuple[float, float]] = {}
        for violation in violations:
            returned_confidence = violation.get('returned_confidence', 0.0)
            error_signal = violation.get('mtr_error_signal', 0.0)
            returned_id = violation.get('returned_fact_id')
            if returned_id is None:
                continue

            # Calculate penalty (confidence mismatch) — observation decrement magnitude
            penalty = min(error_signal * 0.15, 0.1)  # Cap at 0.1 per violation

            if returned_id not in facts:
                facts[returned_id] = (error_signal, penalty)
            else:
                prev_sig, prev_pen = facts[returned_id]
                facts[returned_id] = (max(prev_sig, error_signal), max(prev_pen, penalty))
            grains_updates[returned_id] += penalty

        # Load and update grain index (1:N write-back; see _update_grain_confidences)
        grains_updated, axiom_flags = self._update_grain_confidences(facts, grain_router, db_writer)

        # Load and update edge index (stopgap: guarded no-op-and-report — see method docstring)
        edges_updated, edge_status = self._update_edge_weights(edges_updates, violations)

        total_adjustment = sum(grains_updates.values()) + sum(edges_updates.values())

        # Stash axiom-flag events for introspection/tests (does not change return shape)
        self.last_axiom_flags = axiom_flags

        return grains_updated, edges_updated, total_adjustment, edge_status

    def _update_grain_confidences(
        self,
        facts: Dict[int, Tuple[float, float]],
        grain_router: Any = None,
        db_writer: Any = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """Apply fact->grain feedback with axiom/observation asymmetry (§2.2).

        For each fact, resolves to EVERY grain it maps to via grain_router.grain_by_fact
        (now Dict[int, List[str]] — 1:N, NOT just the first). For each grain:
          - observation: decrement confidence on signal > VIOLATION_INCLUSION_FLOOR (0.3)
          - axiom: FLAG via log_hypothesis(subtype="contradiction") only when signal >
                   AXIOM_CONTRADICTION_THRESHOLD (0.5); never decrement at any lower signal.

        Args:
            facts: fact_id -> (max_error_signal, observation_penalty)
            grain_router: GrainRouter with .grain_by_fact (1:N) and .grains (id->dict).
                          If None, no mutation occurs (prior no-op preserved).
            db_writer: DreamBucketWriter passed to log_hypothesis for axiom flags.

        Returns:
            (count of grains actually updated, list of axiom-flag event dicts)
        """
        updated_count = 0
        axiom_flags: List[Dict[str, Any]] = []

        if grain_router is None:
            # No registry/router wired: record would-be updates but don't mutate
            # (matches prior guarded no-op; production wiring happens in Step 5).
            return 0, axiom_flags

        for fact_id, (error_signal, penalty) in facts.items():
            grain_ids = grain_router.grain_by_fact.get(fact_id, [])
            for gid in grain_ids:  # 1:N: apply to ALL grains this fact resolves to
                grain = grain_router.grains.get(gid)
                if grain is None:
                    continue
                gtype = grain.get('grain_type', 'observation')  # legacy grains default to observation
                conf = float(grain.get('confidence', 0.0))
                mutable = grain.get('confidence_mutable', True)

                if gtype == 'axiom':
                    if error_signal > AXIOM_CONTRADICTION_THRESHOLD:
                        # Flag, do NOT decrement. A downstream sleep stage reconciles.
                        if db_writer is not None:
                            log_hypothesis(
                                db_writer,
                                hypothesis_subtype="contradiction",
                                entities=[fact_id],
                                hypothesis_text=(
                                    f"Grain {gid} (axiom) contradicted by new evidence, "
                                    f"signal={error_signal}"
                                ),
                                confidence=error_signal,
                                evidence=[f"violation mtr_error_signal={error_signal}"],
                                generated_by="recalibration_service",
                            )
                        axiom_flags.append({"grain_id": gid, "fact_id": fact_id, "signal": error_signal})
                    # axioms below the contradiction threshold: NO change at all
                else:
                    # observation: decrement on any signal above the inclusion floor
                    if error_signal > VIOLATION_INCLUSION_FLOOR and mutable and conf > 0.0:
                        grain['confidence'] = max(0.0, conf - penalty)
                        updated_count += 1

        return updated_count, axiom_flags
    
    def _update_edge_weights(self, updates: Dict[str, float],
                             violations: List[Dict[str, Any]]) -> Tuple[int, Dict[str, Any]]:
        """
        Apply feedback to edge weights ONLY for edges a violation actually
        implicates.

        STOPGAP (SPEC_AXIOM_RECALIBRATION.md F2, Option 1): the previous
        implementation averaged the penalty across all pending violations and
        applied it to EVERY edge in procedural_edge_graph.json (gated only on
        confidence_mutable, which defaults True) — a blanket penalty unrelated
        to which edges were involved. That is a latent correctness bug.

        Real edge targeting requires a violation record to name the edge(s) or
        the fact-chain it involved. The current violation schema carries no such
        field (keys: dissonance_type, mtr_error_signal, returned_confidence,
        returned_fact_id, session_id, timestamp — none resolve to an edge key).
        Per the spec, we do NOT invent a targeting heuristic. When no violation
        can be targeted to a specific edge, we change NOTHING and report why.

        Returns:
            (updated_count, status) where status explains the outcome.
        """
        # Fields that could target a specific edge / fact-chain. None of these
        # exist in the current violation schema; if the schema later adds one
        # (see SPEC_AXIOM_RECALIBRATION.md violation-schema-gap), real targeting
        # becomes possible and this stopgap should be revisited.
        EDGE_TARGET_FIELDS = ("edge_key", "edge_keys", "edge_id", "context",
                              "recent_facts", "fact_chain", "involved_edges")

        targetable = [v for v in violations
                      if any(v.get(f) for f in EDGE_TARGET_FIELDS)]

        if not targetable:
            status = {
                'action': 'no-op',
                'reason': 'no_edge_targeting_field_in_violations',
                'missing_fields': list(EDGE_TARGET_FIELDS),
                'violations_seen': len(violations),
                'violations_targetable': 0,
                'detail': ('Violation records carry no edge or fact-chain '
                           'reference; refusing to apply an untargeted blanket '
                           'penalty. No edges changed.'),
            }
            print(f"[RecalibrationService] Edge recalibration skipped: {status['detail']} "
                  f"({len(violations)} violation(s) seen, 0 targetable)")
            return 0, status

        # Reaching here means the violation schema gained a targeting field.
        # Real per-edge targeting is out of scope for this stopgap (it needs a
        # confirmed, sound mapping from the new field to edge keys) — stop and
        # report rather than guess, exactly as the spec requires.
        status = {
            'action': 'no-op',
            'reason': 'targeting_field_present_but_mapping_unimplemented',
            'violations_seen': len(violations),
            'violations_targetable': len(targetable),
            'detail': ('Violations now carry a potential targeting field, but a '
                       'sound field->edge-key mapping is not implemented. '
                       'Revisit SPEC_AXIOM_RECALIBRATION.md Step 1 before '
                       'applying penalties. No edges changed.'),
        }
        print(f"[RecalibrationService] Edge recalibration deferred: {status['detail']} "
              f"({len(targetable)}/{len(violations)} targetable)")
        return 0, status
    
    # ========================================================================
    # DREAM BUCKET I/O
    # ========================================================================
    
    def _read_violations(self) -> List[Dict[str, Any]]:
        """
        Read consistency violations from dream bucket.
        
        Returns:
            List of violation records
        """
        violations = []
        violations_file = self.live_dir / "violations.jsonl"
        
        if not violations_file.exists():
            return violations
        
        try:
            with open(violations_file, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            violation = json.loads(line)
                            # Only process high-signal violations
                            if violation.get('mtr_error_signal', 0.0) > 0.3:
                                violations.append(violation)
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[RecalibrationService] Error reading violations: {e}")
        
        return violations
    
    # ========================================================================
    # INDEX I/O
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
            print(f"[RecalibrationService] Error loading edge graph: {e}")
            return None
    
    def _save_edge_graph(self, edges: Dict[str, Any]) -> bool:
        """
        Save procedural edge graph index.
        
        Args:
            edges: Edge graph dict
        
        Returns:
            True if successful
        """
        self.indices_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Atomic write
            temp_file = self.indices_dir / "procedural_edge_graph.tmp"
            
            with open(temp_file, 'w') as f:
                json.dump(edges, f, indent=2)
            
            temp_file.replace(self.indices_dir / "procedural_edge_graph.json")
            return True
        
        except Exception as e:
            print(f"[RecalibrationService] Error saving edge graph: {e}")
            return False


class UnifiedFeedbackRecalibrator:
    """
    Unified recalibration that treats grains and edges as symmetric.
    
    The core insight of Mutation 5:
    - Grain confidence and edge weight are learned from same signal (query execution)
    - Feedback (MTR error) should apply uniformly to both
    - Observation grains (confidence_mutable=true) and all edges update together
    
    This replaces separate recalibration loops with unified approach.
    """
    
    def __init__(self, dream_bucket_dir: str, grain_registry=None):
        """
        Initialize unified recalibrator.
        
        Args:
            dream_bucket_dir: Path to dream bucket
            grain_registry: Optional GrainRegistry for grain updates
        """
        self.dream_bucket_dir = Path(dream_bucket_dir)
        self.grain_registry = grain_registry
        self.recalibrator = RecalibrationService(dream_bucket_dir)
    
    def recalibrate_grains_and_edges(self) -> Dict[str, Any]:
        """
        Run unified recalibration (grains + edges together).
        
        Returns:
            Report with combined statistics
        """
        # Run base recalibration
        report = self.recalibrator.run_recalibration_cycle()
        
        # Add unified statistics
        report['mode'] = 'unified_grain_edge_recalibration'
        report['principle'] = 'Grains and edges updated uniformly from feedback signal'
        
        return report
