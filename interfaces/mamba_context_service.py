"""
Mamba Context Service Interface - Phase 3B

Defines abstract base class and data structures for context management.
Context services provide background/state information to enhance query routing
and inference (e.g., conversation history, user preferences, active topics).

Used by: QueryOrchestrator (fetches context before routing)
Implemented by: MockMambaService (MVP, no-op), BitMambaService (Phase 4)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime


# ============================================================================
# CONTEXT DATA STRUCTURES
# ============================================================================

@dataclass
class MambaContextRequest:
    """
    Request for context from a context service.
    
    Input to MambaContextService.get_context() method.
    """
    user_id: Optional[str] = None
    """User identifier (for user-specific context)"""
    
    session_id: Optional[str] = None
    """Session identifier (for conversation history)"""
    
    include_conversation_history: bool = False
    """Whether to include recent conversation messages"""
    
    include_user_preferences: bool = False
    """Whether to include user's known preferences"""
    
    include_active_topics: bool = False
    """Whether to include topics relevant to current conversation"""
    
    max_history_messages: int = 10
    """Maximum conversation messages to include"""
    
    context_window_tokens: int = 512
    """Available tokens for context in the query"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional parameters (hints, constraints, etc.)"""
    
    timestamp: Optional[datetime] = None
    """When the request was made"""
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        
        if self.max_history_messages < 0:
            raise ValueError("max_history_messages must be non-negative")
        
        if self.context_window_tokens < 0:
            raise ValueError("context_window_tokens must be non-negative")


@dataclass
class Message:
    """
    A single message in conversation history.
    """
    role: str
    """Who said it: 'user', 'assistant', 'system'"""
    
    content: str
    """The message text"""
    
    timestamp: Optional[datetime] = None
    """When the message was sent"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional data: token_count, language, etc."""
    
    def __post_init__(self):
        if self.role not in ("user", "assistant", "system"):
            raise ValueError(f"role must be 'user', 'assistant', or 'system', got {self.role}")
        
        if not self.content:
            raise ValueError("content must not be empty")
        
        if self.timestamp is None:
            self.timestamp = datetime.now()


@dataclass
class MambaContext:
    """
    Context information to enhance query processing.
    
    Output from MambaContextService.get_context() method.
    Includes temporal windows for Phase 3B Week 3/4.
    """
    # Temporal Context Windows (Week 3/4)
    context_1hour: Dict[str, Any] = field(default_factory=dict)
    """Most recent interactions/context"""
    
    context_1day: Dict[str, Any] = field(default_factory=dict)
    """Broader daily context"""
    
    context_72hours: Dict[str, Any] = field(default_factory=dict)
    """Medium-term context"""
    
    context_1week: Dict[str, Any] = field(default_factory=dict)
    """Longer-term consolidated context"""

    # Structured context fields
    conversation_history: List[Message] = field(default_factory=list)
    """Recent conversation messages (for coherence)"""
    
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    """User-specific preferences: language, detail_level, expertise, etc."""
    
    active_topics: List[str] = field(default_factory=list)
    """Topics active in current conversation (for relevance filtering)"""

    topic_shifts: List[str] = field(default_factory=list)
    """History of detected topic shifts"""
    
    system_info: Dict[str, Any] = field(default_factory=dict)
    """System state: time_of_day, device, locale, etc."""
    
    hidden_state: Optional[bytes] = None
    """Optional: serialized SSM hidden state for Phase 4 BitMamba integration"""

    reasoning_chain: Optional[str] = None
    """Optional: internal reasoning/thinking (for advanced models)"""
    
    confidence: float = 1.0
    """How confident is this context (0.0 = uncertain, 1.0 = certain)"""
    
    latency_ms: float = 0.0
    """How long it took to fetch context (in milliseconds)"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional data: source, version, etc."""
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0.0, 1.0], got {self.confidence}")
        
        if self.latency_ms < 0:
            raise ValueError(f"latency_ms must be non-negative, got {self.latency_ms}")
    
    def is_empty(self) -> bool:
        """Check if context has any useful information."""
        return (
            not self.conversation_history
            and not self.user_preferences
            and not self.active_topics
            and not self.system_info
            and not self.context_1hour
        )
    
    def token_estimate(self) -> int:
        """
        Rough estimate of tokens needed for this context.
        """
        tokens = 0
        for msg in self.conversation_history:
            tokens += len(msg.content.split()) * 4
        
        tokens += len(self.user_preferences) * 50
        tokens += len(self.active_topics) * 10
        tokens += 30 # Base overhead
        
        return tokens


# ============================================================================
# ABSTRACT BASE CLASS
# ============================================================================

class MambaContextService(ABC):
    """
    Abstract base class for context services.
    """
    
    service_name: str = "UNKNOWN"
    """Human-readable service name (override in subclass)"""
    
    def __init__(self):
        pass
    
    @abstractmethod
    def get_context(self, request: MambaContextRequest) -> MambaContext:
        """
        Fetch context for a query.
        """
        pass
    
    def is_available(self) -> bool:
        """Check if service is available and ready to use."""
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Return service statistics."""
        return {}
    
    def shutdown(self) -> None:
        """Clean up resources."""
        pass