"""
RealMambaService - live BitMamba2 context service (Option B2).

Talks to bitmamba_server.exe over a local TCP socket. The server loads the
model ONCE and answers line-delimited prompts; this client sends user_query,
reads back generated text, and maps it into a MambaContext.

Mapping (Option 1, honest):
  - context_1hour  <- generated text (the only window a stateless single-shot
                      generation legitimately represents)
  - context_1day / 72hours / 1week <- LEFT EMPTY (BitMamba has no cross-query
                      memory; do NOT fabricate temporal history)
  - active_topics  <- lightweight extraction from the generated text
  - everything else <- empty / None

Contract: get_context() NEVER returns None and NEVER raises to the caller. If
the server is unreachable or the query is empty, it returns an empty-but-valid
MambaContext (matches the mock's shape) so the orchestrator degrades cleanly.

The server binary lives in the engine tree (B:\\ai\\llm\\kitbash\\bitmamba.cpp\\build),
outside this repo. Paths are config-driven, not hardcoded.
"""

import logging
import os
import re
import socket
import subprocess
from typing import List, Optional

from interfaces.mamba_context_service import (
    MambaContext,
    MambaContextRequest,
    MambaContextService,
)

logger = logging.getLogger(__name__)

_STOP = {50256, 0}
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "into", "your", "are",
    "was", "has", "have", "but", "not", "you", "our", "its", "their", "they",
    "them", "who", "what", "when", "where", "which", "will", "would", "could",
}


class RealMambaService(MambaContextService):
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8731,
        model_path: str = "",
        exe_path: str = "",
        cwd: str = "",
        max_tokens: int = 200,
        enabled: bool = True,
        autostart: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.host = host
        self.port = port
        self.model_path = model_path
        self.exe_path = exe_path
        self.cwd = cwd  # dir containing tokenizer.bin
        self.max_tokens = max_tokens
        self.enabled = enabled
        self.autostart = autostart
        self.timeout = timeout
        self.call_count: int = 0
        self.last_request: Optional[MambaContextRequest] = None
        self._proc: Optional[subprocess.Popen] = None
        self._started_here: bool = False

    # ---- public API ---------------------------------------------------------

    def get_context(self, request: MambaContextRequest) -> MambaContext:
        self.call_count += 1
        self.last_request = request

        if not self.enabled:
            return self._empty()

        prompt = (getattr(request, "user_query", None) or "").strip()
        if not prompt:
            return self._empty()

        text = self._query(prompt)
        if not text:
            return self._empty()

        return MambaContext(
            context_1hour={"generated": text, "source": "bitmamba"},
            context_1day={},
            context_72hours={},
            context_1week={},
            active_topics=self._topics(text),
            topic_shifts=[],
            hidden_state=None,
        )

    def reset(self) -> None:
        self.call_count = 0
        self.last_request = None

    def shutdown(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc = None
            self._started_here = False

    # ---- internals ----------------------------------------------------------

    def _query(self, prompt: str) -> str:
        try:
            return self._recv(prompt)
        except (ConnectionRefusedError, OSError, socket.timeout) as e:
            if self.autostart and self.exe_path and self.model_path:
                logger.warning(f"Mamba server not reachable ({e}); attempting autostart")
                if self._try_autostart():
                    try:
                        return self._recv(prompt)
                    except (ConnectionRefusedError, OSError, socket.timeout) as e2:
                        logger.warning(f"Mamba autostart failed to serve: {e2}")
            else:
                logger.warning(f"Mamba server unreachable: {e}")
            return ""

    def _recv(self, prompt: str) -> str:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as s:
            s.sendall((prompt + "\n").encode("utf-8"))
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if data.endswith(b"\n"):
                    break
        return data.decode("utf-8", errors="replace").rstrip("\n")

    def _try_autostart(self) -> bool:
        if self._started_here:
            return False
        try:
            self._proc = subprocess.Popen(
                [self.exe_path, self.model_path, str(self.port), str(self.max_tokens)],
                cwd=self.cwd or None,
            )
            self._started_here = True
        except OSError as e:
            logger.warning(f"Mamba exe launch failed: {e}")
            return False
        # Give the model a moment to load before the caller retries.
        import time
        time.sleep(8)
        return True

    @staticmethod
    def _topics(text: str, cap: int = 8) -> List[str]:
        seen = set()
        out = []
        for w in _WORD.findall(text):
            low = w.lower()
            if low in _STOPWORDS or low in seen:
                continue
            seen.add(low)
            out.append(w)
            if len(out) >= cap:
                break
        return out

    @staticmethod
    def _empty() -> MambaContext:
        return MambaContext(
            context_1hour={},
            context_1day={},
            context_72hours={},
            context_1week={},
            active_topics=[],
            topic_shifts=[],
            hidden_state=None,
        )
