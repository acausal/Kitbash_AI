"""LLaMA.cpp Engine - Phase 3B Layer (local generation LLM).

A near-twin of bitnet_engine.py, but pointed at a LOCAL generation LLM
served by llama.cpp (llama-server.exe / kobold.cpp), NOT BitNet. Implements
the same InferenceEngine interface so it drops into the QueryOrchestrator cascade
as its own engine entry (engine_name="LLM").

This is the "new InferenceEngine" half of the BitNet-retirement proposal
(docs/PROPOSAL-BITNET_ROLE_RETIREMENT_AND_LOCAL_LLM_SWAP.md, ~3.1). It is
mechanical: same HTTP-wrapper shape as BitNetEngine, different endpoint/env.

Server startup (you stand this up):
    llama-server.exe --model <your_small_model.gguf> --port 8081 -ngl 99 -c 4096

Used by: QueryOrchestrator (its own cascade slot, not BitNet's).
Wraps: llama-server HTTP /completion endpoint.
Interface: POST JSON {prompt, n_predict, temperature}.
"""
import time
import os
import logging
import requests
from typing import Optional, Dict, Any
from urllib.parse import urljoin

from interfaces.inference_engine import InferenceEngine, InferenceRequest, InferenceResponse

logger = logging.getLogger(__name__)


class LlamaCppEngine(InferenceEngine):
    """Local generation LLM via llama.cpp HTTP server.

    engine_name = "LLM"
    """

    engine_name = "LLM"

    def __init__(self, server_url: Optional[str] = None,
                 timeout_seconds: int = 120,
                 max_tokens: int = 256,
                 temperature: float = 0.7):
        """Initialize the LLM engine.

        Args:
            server_url: URL of the llama.cpp server. Defaults to the
                KITBASH_LLM_URL env var, then http://127.0.0.1:8081.
            timeout_seconds: Request timeout (local gens can be slow).
            max_tokens: Maximum tokens to generate per query.
            temperature: Sampling temperature (0.0-2.0).

        Raises:
            ValueError: If parameters invalid.
        """
        super().__init__()

        self.server_url = (server_url or os.environ.get(
            "KITBASH_LLM_URL", "http://127.0.0.1:8081"
        )).rstrip('/')
        self.completion_endpoint = urljoin(self.server_url, '/completion')
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Statistics
        self.query_count = 0
        self.successful_queries = 0
        self.failed_queries = 0
        self.total_latency_ms = 0.0
        self.total_tokens_generated = 0

        # Validation
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f"temperature must be in [0.0, 2.0], got {temperature}")
        if max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {max_tokens}")

        # Probe server reachability (warn, don't fail - server may be slow to start)
        self._verify_server()

    def _verify_server(self) -> None:
        """Verify llama.cpp server is running. Logs warning if unreachable but
        doesn't fail (server might still be booting)."""
        try:
            response = requests.head(self.server_url, timeout=5)
            logger.info(f"LLM server reachable at {self.server_url}")
        except requests.ConnectionError:
            logger.warning(
                f"LLM server not reachable at {self.server_url} - "
                f"make sure llama-server.exe is running"
            )
        except Exception as e:
            logger.warning(f"Could not verify LLM server: {e}")

    def is_available(self) -> bool:
        """Check if the llama.cpp server is reachable (quick, non-blocking)."""
        try:
            response = requests.head(self.server_url, timeout=2)
            return response.status_code < 500
        except Exception:
            return False

    def query(self, request: InferenceRequest) -> InferenceResponse:
        """Execute a generation query via the llama.cpp HTTP server.

        Args:
            request: InferenceRequest with user query + context.

        Returns:
            InferenceResponse with the LLM's answer.

        Raises:
            RuntimeError: If server unreachable or request fails.
        """
        self.query_count += 1
        start_time = time.perf_counter()

        # Build the prompt: query + Mamba context if present (the "full reasoning"
        # tier receives filtered facts + Mamba context + query, per the proposal).
        prompt = request.user_query or ""
        if request.context:
            ctx = request.context
            if isinstance(ctx, (list, tuple)):
                ctx = " ".join(str(c) for c in ctx)
            prompt = f"{ctx}\n\n{prompt}"

        try:
            payload = {
                "prompt": prompt,
                "n_predict": request.max_tokens or self.max_tokens,
                "temperature": request.temperature if request.temperature else self.temperature,
            }

            logger.debug(f"Sending query to LLM: {request.user_query[:50]}...")
            response = requests.post(
                self.completion_endpoint,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()

            data = response.json()
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.successful_queries += 1
            self.total_latency_ms += latency_ms

            # llama.cpp /completion returns {content, tokens_predicted, model, ...}
            answer = data.get('content', '').strip()
            tokens_predicted = data.get('tokens_predicted', 0)
            self.total_tokens_generated += tokens_predicted

            if not answer:
                logger.warning("LLM returned empty response")
                answer = "[LLM generated no response]"

            return InferenceResponse(
                answer=answer,
                # Confidence: LLM is the generative tier; confidence is a
                # placeholder until wired to a real signal (proposal: this is the
                # "full reasoning" layer, not a crystallized-lookup confidence).
                confidence=0.70,
                engine_name=self.engine_name,
                sources=["llm"],
                latency_ms=latency_ms,
                metadata={
                    'tokens_predicted': tokens_predicted,
                    'model': data.get('model', 'unknown'),
                    'stop_type': data.get('stop_type', 'unknown'),
                    'temperature': self.temperature,
                    'query_count': self.query_count,
                    'tokens_per_second': (
                        tokens_predicted / (latency_ms / 1000)
                        if latency_ms > 0 else 0
                    ),
                },
            )

        except requests.Timeout:
            self.failed_queries += 1
            logger.error(f"LLM request timeout after {self.timeout_seconds}s")
            raise RuntimeError(
                f"LLM server timeout (>{self.timeout_seconds}s) - "
                f"query too complex or server overloaded"
            )
        except requests.ConnectionError as e:
            self.failed_queries += 1
            logger.error(f"Could not connect to LLM server: {e}")
            raise RuntimeError(
                f"Cannot connect to LLM at {self.server_url} - "
                f"make sure llama-server.exe is running"
            )
        except requests.HTTPError as e:
            self.failed_queries += 1
            logger.error(f"LLM HTTP error: {e}")
            raise RuntimeError(f"LLM server error: {e}")
        except ValueError as e:
            self.failed_queries += 1
            logger.error(f"Could not parse LLM response: {e}")
            raise RuntimeError(f"Invalid LLM response: {e}")
        except Exception as e:
            self.failed_queries += 1
            logger.error(f"LLM query failed: {e}")
            raise RuntimeError(f"LLM query failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Return LLM engine statistics."""
        avg_latency = (
            self.total_latency_ms / self.successful_queries
            if self.successful_queries > 0 else 0.0
        )
        avg_tokens = (
            self.total_tokens_generated / self.successful_queries
            if self.successful_queries > 0 else 0.0
        )
        success_rate = (
            (self.successful_queries / self.query_count) * 100
            if self.query_count > 0 else 0.0
        )
        return {
            'query_count': self.query_count,
            'successful_queries': self.successful_queries,
            'failed_queries': self.failed_queries,
            'success_rate_percent': success_rate,
            'avg_latency_ms': avg_latency,
            'total_latency_ms': self.total_latency_ms,
            'total_tokens_generated': self.total_tokens_generated,
            'avg_tokens_per_query': avg_tokens,
            'server_url': self.server_url,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }

    def shutdown(self) -> None:
        """Clean up resources (doesn't shut down server)."""
        logger.info("LlamaCppEngine shut down (note: server process still running)")
