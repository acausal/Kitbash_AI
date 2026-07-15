#!/usr/bin/env python3
"""
Cartridge Coverage Harness v1 - E2E Operational Data Collection

Generates synthetic queries with intentional variation to:
1. Exercise the full retrieval pipeline (CartridgeLoader → MTR → GrainRouter)
2. Verify coverage of all 609 facts at least once
3. Map procedural edge topology via co-occurrence validation
4. Collect real latency and performance data for magic number calibration

Usage:
    python coverage_harness.py --cartridge-dir ./cartridges \\
        --output-dir ./coverage_logs \\
        --num-entity-queries 700 \\
        --num-template-queries 400 \\
        --seed 42

Output:
    - coverage_harness_queries.jsonl (per-query execution log)
    - coverage_harness_report.json (summary statistics)
    - coverage_harness_topology_gaps.txt (human-readable gaps)
"""

import json
import time
import random
import argparse
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict
import re

# Assume QueryOrchestrator is available in the Kitbash environment
try:
    from query_orchestrator import QueryOrchestrator, QueryContext
    from kitbash_cartridge import KitbashCartridge
    from structured_logger import get_event_logger
    ORCHESTRATOR_AVAILABLE = True
except ImportError as e:
    ORCHESTRATOR_AVAILABLE = False
    print(f"Warning: QueryOrchestrator not available. Running in mock mode. Error: {e}")

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class QueryExecution:
    """Record of a single query execution"""
    timestamp: str
    query_text: str
    fact_ids_retrieved: List[int]
    grain_ids: List[str]
    latency_ms: float
    error: Optional[str] = None
    mtr_confidence: Optional[float] = None
    cartridge_ids: List[str] = None
    
    def __post_init__(self):
        if self.cartridge_ids is None:
            self.cartridge_ids = []


@dataclass
class EdgeCoverageEntry:
    """Validation for a single procedural edge"""
    fact_a: int
    fact_b: int
    edge_type: str
    edge_strength: float
    retrieved_together_count: int = 0
    retrieved_together: bool = False
    last_joint_retrieval: Optional[str] = None


@dataclass
class CoverageReport:
    """Summary statistics from full harness run"""
    total_queries: int
    total_facts_in_cartridge: int
    facts_accessed: int
    fact_coverage_percent: float
    total_edges: int
    edges_accessible: int
    edge_coverage_percent: float
    total_grain_activations: int
    unique_grains_activated: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float
    error_count: int
    harness_duration_sec: float


# ============================================================================
# QUERY GENERATION
# ============================================================================

class QueryGenerator:
    """Generate synthetic queries with multiple strategies"""
    
    def __init__(self, cartridges: List[KitbashCartridge], seed: int = 42):
        """
        Args:
            cartridges: List of loaded KitbashCartridge objects
            seed: RNG seed for reproducibility
        """
        self.cartridges = cartridges
        self.seed = seed
        random.seed(seed)
        self.all_facts: List[Tuple[int, str]] = []  # (fact_id, content)
        self._extract_facts()
    
    def _extract_facts(self):
        """Load all facts from cartridges into a flat list"""
        for cartridge in self.cartridges:
            # Assuming cartridge has a method to list all facts
            # Adjust based on actual CartridgeLoader API
            if hasattr(cartridge, 'get_all_facts'):
                facts = cartridge.get_all_facts()
                for fact_id, fact_content in facts:
                    self.all_facts.append((fact_id, fact_content))
        
        print(f"[QueryGenerator] Loaded {len(self.all_facts)} facts from cartridges")
    
    def _extract_entities(self, text: str) -> List[str]:
        """
        Extract key entities/terms from fact text.
        Simple regex + capitalization heuristic.
        
        Returns:
            List of candidate entities
        """
        # Split on common delimiters, keep capitalized phrases
        words = text.split()
        entities = []
        
        for word in words:
            # Strip punctuation, keep if capitalized or all-caps
            clean = word.strip('.,;:!?')
            if clean and (clean[0].isupper() or clean.isupper()):
                entities.append(clean)
        
        return entities
    
    def generate_entity_queries(self, target_count: int = 700) -> List[str]:
        """
        Strategy 1: Extract entities from facts and build single-subject queries.
        
        Args:
            target_count: Approximate number of queries to generate
        
        Returns:
            List of query strings
        """
        queries = []
        entity_pool = defaultdict(int)
        
        # Extract entities from all facts
        for fact_id, content in self.all_facts:
            entities = self._extract_entities(content)
            for ent in entities:
                entity_pool[ent] += 1
        
        # Sort by frequency (rarest first to ensure coverage)
        sorted_entities = sorted(entity_pool.items(), key=lambda x: x[1])
        
        # Generate queries for each entity
        templates = [
            "What is {entity}?",
            "Tell me about {entity}.",
            "Explain {entity}.",
            "What do you know about {entity}?",
            "How does {entity} work?",
            "What is the role of {entity}?",
            "Describe {entity}.",
        ]
        
        for entity, freq in sorted_entities[:target_count]:
            template = random.choice(templates)
            query = template.format(entity=entity)
            queries.append(query)
        
        print(f"[QueryGenerator] Generated {len(queries)} entity queries")
        return queries
    
    def generate_template_queries(self, target_count: int = 400) -> List[str]:
        """
        Strategy 2: Template-based generation with multi-subject queries.
        
        Args:
            target_count: Number of queries to generate
        
        Returns:
            List of query strings
        """
        templates = [
            # Factual
            "What is {subject}?",
            "Tell me about {subject}.",
            "Explain {subject}.",
            
            # Relational (2-subject)
            "How does {subject} relate to {object}?",
            "What's the connection between {subject} and {object}?",
            "How are {subject} and {object} different?",
            "Compare {subject} and {object}.",
            "What's the relationship between {subject} and {object}?",
            
            # Procedural
            "How do I {action} with {subject}?",
            "What's the process for {subject}?",
            "How do you use {subject}?",
            
            # Temporal
            "When was {subject} created?",
            "What happened to {subject}?",
            "What's the timeline of {subject}?",
            
            # Causality
            "Why does {subject} {action}?",
            "What causes {subject}?",
            "What's the result of {subject}?",
        ]
        
        queries = []
        
        for _ in range(target_count):
            template = random.choice(templates)
            
            # Count placeholders
            placeholders = re.findall(r'\{(\w+)\}', template)
            
            if len(placeholders) == 0:
                continue
            
            # Sample facts for each placeholder
            replacements = {}
            for placeholder in placeholders:
                if placeholder == "action":
                    # Use verb-like words
                    actions = ["use", "apply", "work with", "implement", "configure"]
                    replacements[placeholder] = random.choice(actions)
                else:
                    # Use actual fact content (subject, object)
                    fact_id, content = random.choice(self.all_facts)
                    # Take first ~5 words as placeholder value
                    words = content.split()[:5]
                    replacements[placeholder] = " ".join(words)
            
            try:
                query = template.format(**replacements)
                queries.append(query)
            except KeyError:
                # Skip if placeholder wasn't filled
                continue
        
        print(f"[QueryGenerator] Generated {len(queries)} template queries")
        return queries
    
    def generate_all(self, 
                    num_entity: int = 700, 
                    num_template: int = 400) -> List[str]:
        """
        Generate queries from all strategies and deduplicate.
        
        Returns:
            Sorted list of unique query strings
        """
        all_queries = []
        all_queries.extend(self.generate_entity_queries(num_entity))
        all_queries.extend(self.generate_template_queries(num_template))
        
        # Deduplicate and sort
        unique_queries = sorted(set(all_queries))
        
        print(f"[QueryGenerator] Final query set: {len(unique_queries)} unique queries")
        return unique_queries


# ============================================================================
# EXECUTION & COVERAGE VALIDATION
# ============================================================================

class CartridgeCoverageHarness:
    """Main harness: generate queries, execute, validate coverage"""
    
    def __init__(self, cartridges: List[KitbashCartridge], 
                 output_dir: Path, 
                 seed: int = 42):
        """
        Args:
            cartridges: List of loaded cartridges
            output_dir: Directory for output files
            seed: RNG seed
        """
        self.cartridges = cartridges
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed
        
        self.query_generator = QueryGenerator(cartridges, seed)
        self.queries: List[str] = []
        self.executions: List[QueryExecution] = []
        
        # Coverage tracking
        self.facts_accessed: Set[int] = set()
        self.co_occurrences: Dict[Tuple[int, int], int] = defaultdict(int)
        self.latencies: List[float] = []
        self.errors: List[str] = []
        self.grain_activations: List[str] = []
        
        self.start_time = None
        self.end_time = None
    
    def generate_queries(self, num_entity: int = 700, num_template: int = 400):
        """Generate query stream"""
        self.queries = self.query_generator.generate_all(num_entity, num_template)
        print(f"[Harness] Query generation complete: {len(self.queries)} queries ready")
    
    def run_all(self, verbose: bool = False):
        """Execute all queries through the orchestrator"""
        if not self.queries:
            raise ValueError("No queries generated. Call generate_queries() first.")
        
        if not ORCHESTRATOR_AVAILABLE:
            print("[Harness] Orchestrator not available. Running in mock mode.")
            self._run_mock()
            return
        
        print(f"[Harness] Starting execution of {len(self.queries)} queries...")
        self.start_time = time.time()
        
        orchestrator = QueryOrchestrator()  # Assume global instance or initialize
        
        for i, query in enumerate(self.queries):
            if (i + 1) % 50 == 0:
                print(f"  Progress: {i+1}/{len(self.queries)}")
            
            try:
                query_start = time.time()
                
                # Execute query through the full pipeline
                context = QueryContext(query_text=query)
                result = orchestrator.process(context)
                
                query_elapsed = time.time() - query_start
                
                # Extract results
                fact_ids = self._extract_fact_ids(result)
                grain_ids = self._extract_grain_ids(result)
                
                execution = QueryExecution(
                    timestamp=datetime.now().isoformat(),
                    query_text=query,
                    fact_ids_retrieved=fact_ids,
                    grain_ids=grain_ids,
                    latency_ms=query_elapsed * 1000,
                    mtr_confidence=getattr(result, 'confidence', None),
                    cartridge_ids=self._extract_cartridge_ids(result),
                )
                
                self.executions.append(execution)
                self.facts_accessed.update(fact_ids)
                self.latencies.append(query_elapsed * 1000)
                self.grain_activations.extend(grain_ids)
                
                # Record co-occurrences (pairwise)
                for j in range(len(fact_ids)):
                    for k in range(j+1, len(fact_ids)):
                        pair = tuple(sorted([fact_ids[j], fact_ids[k]]))
                        self.co_occurrences[pair] += 1
                
                if verbose:
                    print(f"  [{i+1}] {query[:60]}... → {len(fact_ids)} facts, {query_elapsed*1000:.1f}ms")
            
            except Exception as e:
                error_msg = f"Query {i+1}: {str(e)}"
                self.errors.append(error_msg)
                self.executions.append(QueryExecution(
                    timestamp=datetime.now().isoformat(),
                    query_text=query,
                    fact_ids_retrieved=[],
                    grain_ids=[],
                    latency_ms=0.0,
                    error=error_msg,
                ))
                if verbose:
                    print(f"  [{i+1}] ERROR: {error_msg}")
        
        self.end_time = time.time()
        print(f"[Harness] Execution complete. Duration: {self.end_time - self.start_time:.1f}s")
    
    def _run_mock(self):
        """Mock execution for testing without full orchestrator"""
        print("[Harness] Mock mode: simulating query execution...")
        self.start_time = time.time()
        
        for i, query in enumerate(self.queries):
            # Simulate random fact retrieval
            num_facts = random.randint(1, 5)
            fact_ids = random.sample(range(1, 610), num_facts)
            
            execution = QueryExecution(
                timestamp=datetime.now().isoformat(),
                query_text=query,
                fact_ids_retrieved=fact_ids,
                grain_ids=[],
                latency_ms=random.uniform(5, 50),
            )
            
            self.executions.append(execution)
            self.facts_accessed.update(fact_ids)
            self.latencies.append(execution.latency_ms)
            
            for j in range(len(fact_ids)):
                for k in range(j+1, len(fact_ids)):
                    pair = tuple(sorted([fact_ids[j], fact_ids[k]]))
                    self.co_occurrences[pair] += 1
        
        self.end_time = time.time()
        print(f"[Harness] Mock execution complete. {len(self.executions)} queries simulated.")
    
    def _extract_fact_ids(self, result: Any) -> List[int]:
        """Extract fact IDs from orchestrator result"""
        if hasattr(result, 'fact_ids'):
            return result.fact_ids
        if hasattr(result, 'facts'):
            return [f.fact_id for f in result.facts]
        return []
    
    def _extract_grain_ids(self, result: Any) -> List[str]:
        """Extract grain IDs from orchestrator result"""
        if hasattr(result, 'grain_ids'):
            return result.grain_ids
        if hasattr(result, 'grains'):
            return [g.grain_id for g in result.grains]
        return []
    
    def _extract_cartridge_ids(self, result: Any) -> List[str]:
        """Extract cartridge IDs from orchestrator result"""
        if hasattr(result, 'cartridge_ids'):
            return result.cartridge_ids
        return []
    
    def validate_coverage(self) -> CoverageReport:
        """Analyze coverage and generate report"""
        print("[Harness] Validating coverage...")
        
        # Fact coverage
        total_facts = 609
        facts_accessed_count = len(self.facts_accessed)
        fact_coverage = (facts_accessed_count / total_facts) * 100
        
        # Edge coverage (naive: count co-occurrences that fired at all)
        edges_with_signal = len([e for e in self.co_occurrences.values() if e > 0])
        # Note: we don't have total edges without loading cartridge structure
        # Placeholder for now
        total_edges_estimate = 1000  # Placeholder
        edge_coverage = (edges_with_signal / total_edges_estimate) * 100 if total_edges_estimate > 0 else 0
        
        # Latency stats
        if self.latencies:
            sorted_latencies = sorted(self.latencies)
            p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)]
            p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
            p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)]
            p_max = max(self.latencies)
        else:
            p50 = p95 = p99 = p_max = 0.0
        
        # Grain stats
        unique_grains = len(set(self.grain_activations))
        total_grain_activations = len(self.grain_activations)
        
        report = CoverageReport(
            total_queries=len(self.executions),
            total_facts_in_cartridge=total_facts,
            facts_accessed=facts_accessed_count,
            fact_coverage_percent=fact_coverage,
            total_edges=total_edges_estimate,
            edges_accessible=edges_with_signal,
            edge_coverage_percent=edge_coverage,
            total_grain_activations=total_grain_activations,
            unique_grains_activated=unique_grains,
            latency_p50_ms=p50,
            latency_p95_ms=p95,
            latency_p99_ms=p99,
            latency_max_ms=p_max,
            error_count=len(self.errors),
            harness_duration_sec=self.end_time - self.start_time if self.end_time else 0,
        )
        
        print(f"\n[Harness] Coverage Report:")
        print(f"  Queries executed: {report.total_queries}")
        print(f"  Facts accessed: {report.facts_accessed}/{report.total_facts_in_cartridge} ({report.fact_coverage_percent:.1f}%)")
        print(f"  Co-occurrence edges with signal: {report.edges_accessible}/{report.total_edges} ({report.edge_coverage_percent:.1f}%)")
        print(f"  Grain activations: {report.total_grain_activations} total, {report.unique_grains_activated} unique")
        print(f"  Latency: p50={report.latency_p50_ms:.1f}ms, p95={report.latency_p95_ms:.1f}ms, p99={report.latency_p99_ms:.1f}ms")
        print(f"  Errors: {report.error_count}")
        print(f"  Duration: {report.harness_duration_sec:.1f}s\n")
        
        return report
    
    def write_reports(self):
        """Write output files"""
        print("[Harness] Writing reports...")
        
        # 1. JSONL log
        jsonl_path = self.output_dir / "coverage_harness_queries.jsonl"
        with open(jsonl_path, 'w') as f:
            for execution in self.executions:
                f.write(json.dumps(asdict(execution)) + '\n')
        print(f"  → {jsonl_path}")
        
        # 2. Summary report
        report = self.validate_coverage()
        report_path = self.output_dir / "coverage_harness_report.json"
        with open(report_path, 'w') as f:
            json.dump(asdict(report), f, indent=2)
        print(f"  → {report_path}")
        
        # 3. Topology gaps
        gaps_path = self.output_dir / "coverage_harness_topology_gaps.txt"
        with open(gaps_path, 'w') as f:
            all_facts = set(fid for fid, _ in self.query_generator.all_facts)
            missing_facts = sorted(all_facts - self.facts_accessed)
            
            f.write("=== CARTRIDGE COVERAGE HARNESS GAPS ===\n\n")
            f.write(f"Total facts in cartridge: {len(all_facts)}\n")
            f.write(f"Facts accessed: {len(self.facts_accessed)}\n")
            f.write(f"Facts missing: {len(missing_facts)}\n\n")
            
            if missing_facts:
                f.write("--- Missing Facts (IDs) ---\n")
                f.write(", ".join(map(str, missing_facts)) + "\n\n")
            
            f.write(f"--- Co-occurrence Edges ---\n")
            f.write(f"Total co-occurrence signals: {len(self.co_occurrences)}\n")
            f.write(f"Edges with >1 co-occurrence: {len([e for e in self.co_occurrences.values() if e > 1])}\n")
            f.write(f"Strongest edge: {max(self.co_occurrences.values()) if self.co_occurrences else 0} co-occurrences\n\n")
            
            f.write("--- Errors ---\n")
            if self.errors:
                for error in self.errors[:20]:  # First 20
                    f.write(f"  {error}\n")
                if len(self.errors) > 20:
                    f.write(f"  ... and {len(self.errors) - 20} more\n")
            else:
                f.write("  None\n")
        
        print(f"  → {gaps_path}")
        print(f"\n[Harness] All reports written to {self.output_dir}")


# ============================================================================
# CLI & MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Cartridge Coverage Harness - E2E operational data collection"
    )
    parser.add_argument("--cartridge-dir", type=Path, default=Path("./cartridges"),
                       help="Directory containing cartridge files")
    parser.add_argument("--output-dir", type=Path, default=Path("./coverage_logs"),
                       help="Output directory for logs and reports")
    parser.add_argument("--num-entity-queries", type=int, default=700,
                       help="Number of entity-based queries to generate")
    parser.add_argument("--num-template-queries", type=int, default=400,
                       help="Number of template-based queries to generate")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for reproducibility")
    parser.add_argument("--mock", action="store_true",
                       help="Run in mock mode (no orchestrator required)")
    parser.add_argument("--verbose", action="store_true",
                       help="Verbose output during execution")
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("CARTRIDGE COVERAGE HARNESS v1")
    print("=" * 70)
    
    # Load cartridges
    # TODO: Adjust based on actual cartridge loading mechanism
    cartridges = []
    print(f"[Main] Loading cartridges from {args.cartridge_dir}...")
    # If orchestrator is available, use its cartridge loading
    if ORCHESTRATOR_AVAILABLE:
        try:
            orchestrator = QueryOrchestrator()
            cartridges = orchestrator.cartridges  # Assuming this exists
        except Exception as e:
            print(f"Warning: Could not load cartridges via orchestrator: {e}")
            cartridges = []
    
    if not cartridges:
        print("No cartridges loaded. Run with --mock for simulation mode.")
        if not args.mock:
            return
    
    # Initialize harness
    harness = CartridgeCoverageHarness(cartridges, args.output_dir, seed=args.seed)
    
    # Generate and execute queries
    harness.generate_queries(
        num_entity=args.num_entity_queries,
        num_template=args.num_template_queries
    )
    
    harness.run_all(verbose=args.verbose)
    
    # Write reports
    harness.write_reports()
    
    print("=" * 70)
    print("HARNESS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
