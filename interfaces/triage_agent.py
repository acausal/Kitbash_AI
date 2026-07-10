"""
Triage Agent Interface - Phase 3B

Defines abstract base class and data structures for query routing and 
background maintenance decision making.

Used by: QueryOrchestrator (to decide which engines fire)
Implemented by: RuleBasedTriageAgent (MVP), BitNetTriageAgent (Phase 4)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# Default thresholds used by RuleBasedTriageAgent
DEFAULT_CONFIDENCE_THRESHOLDS = {
    "GRAIN": 0.90,
    "BITNET": 0.75,
    "CARTRIDGE": 0.70,
    "SPECIALIST": 0.65,
    "LLM": 0.0,  # Validated separately via NWP
}

# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class TriageRequest:
    """Input to the triage process."""
    user_query: str
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TriageDecision:
    """Output from the triage agent for a specific query."""
    layer_sequence: List[str]
    """Order of engines to try (e.g., ['GRAIN', 'CARTRIDGE', 'ESCALATE'])"""
    
    confidence_thresholds: Dict[str, float]
    """Per-layer thresholds required to stop the cascade"""
    
    recommended_cartridges: List[str] = field(default_factory=list)
    """Hint for CartridgeEngine to limit search to specific domains"""
    
    use_mamba_context: bool = False
    """Whether the engines should inject temporal context"""
    
    cache_result: bool = True
    """Whether this result should be recorded in ResonanceWeightService"""
    
    reasoning: str = ""
    """Diagnostic explanation for the routing decision"""


@dataclass
class BackgroundTriageRequest:
    """Input for background maintenance decisions."""
    resonance_patterns: Dict[str, Any]
    cartridge_stats: Dict[str, Any]
    current_turn: int
    system_load: float = 0.0


@dataclass
class BackgroundTriageDecision:
    """Output deciding the next maintenance priority."""
    priority: str 
    """Options: 'decay', 'analyze_split', 'routine', 'test_crystallizer'"""
    
    reasoning: str
    urgency: float = 0.0  # 0.0 to 1.0
    estimated_duration_ms: float = 0.0
    parameters: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class TriageAgent(ABC):
    """
    Abstract base class for all triage implementations.
    """
    
    @abstractmethod
    def route(self, request: TriageRequest) -> TriageDecision:
        """Decide the inference path for a query."""
        pass
    
    @abstractmethod
    def route_background(self, request: BackgroundTriageRequest) -> BackgroundTriageDecision:
        """Decide the next background maintenance task."""
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic metrics for the agent."""
        return {}