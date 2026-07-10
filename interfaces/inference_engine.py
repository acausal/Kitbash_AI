"""
Inference Engine Interface - Phase 3B

Defines the abstract base class and data structures for all inference layers.
Every engine (Grain, Cartridge, BitNet, LLM) must implement this interface
to participate in the QueryOrchestrator cascade.

Used by: QueryOrchestrator
Implemented by: GrainEngine, CartridgeEngine, BitNetEngine, SpecialistEngine
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


# ============================================================================
# INFERENCE DATA STRUCTURES
# ============================================================================

@dataclass
class InferenceRequest:
    """
    Standardized request sent to an inference engine.
    """
    user_query: str
    """The natural language query to process"""
    
    context: Optional[Any] = None
    """Temporal context from MambaContextService"""
    
    cartridge_ids: Optional[List[str]] = None
    """
    Targeted cartridges for lookup. 
    Provided by TriageAgent to narrow search space (Phase 3B Week 4).
    """
    
    max_tokens: int = 100
    """Maximum response length for generative engines"""
    
    temperature: float = 0.7
    """Sampling temperature for neural engines"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Engine-specific parameters or flags"""


@dataclass
class InferenceResponse:
    """
    Standardized response returned by an inference engine.
    """
    answer: Optional[str]
    """The generated answer or retrieved fact. None if no answer found."""
    
    confidence: float
    """Confidence score (0.0 to 1.0)"""
    
    engine_name: str
    """Identifier for the engine (e.g., 'GRAIN', 'BITNET')"""
    
    sources: List[str] = field(default_factory=list)
    """IDs of facts, grains, or documents used to generate the answer"""
    
    latency_ms: float = 0.0
    """Time taken for inference in milliseconds"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Diagnostic info: token counts, model IDs, hit types, etc."""


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class InferenceEngine(ABC):
    """
    Abstract base class for all Kitbash inference implementations.
    """
    
    engine_name: str = "UNKNOWN"
    """Unique identifier for this engine type"""
    
    def __init__(self):
        """Initialize engine resources."""
        pass
    
    @abstractmethod
    def query(self, request: InferenceRequest) -> InferenceResponse:
        """
        Process an inference request.
        
        Args:
            request: InferenceRequest with query and constraints
            
        Returns:
            InferenceResponse with answer and metrics
            
        Raises:
            RuntimeError: If engine execution fails
        """
        pass
    
    def is_available(self) -> bool:
        """Check if engine is ready (e.g., model loaded, server up)."""
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Return performance metrics for this engine instance."""
        return {}
    
    def shutdown(self) -> None:
        """Release resources used by the engine."""
        pass