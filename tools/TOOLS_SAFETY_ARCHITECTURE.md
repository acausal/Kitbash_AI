# Tools Safety & Trust Architecture

**Status:** Design document for tools/ ecosystem  
**Date:** 2026-07-14  
**Purpose:** Define trust boundaries, filesystem isolation, and safety gates for atomic tool integration into Kitbash cognitive stack

---

## Overview

The `tools/` directory implements stateless Unix-style "Lego brick" utilities that can be chained together for data transformation, pattern discovery, and external I/O. This document specifies the safety architecture that enables tools to interact with external systems (network, filesystem, models) without compromising local-first guarantees or leaking malformed data into the core cognitive stack.

**Core principle:** Trust is earned through isolation, validation, and explicit user consent.

---

## Part 1: Hardened Filesystem Architecture (The Airlock)

The workspace filesystem is partitioned by trust level. Tools operate within defined boundaries; critical paths enforce one-way validation gates.

### Directory Structure

```
workspace_root/
├── workspace/              # High-trust reasoning sandbox
│                          # Read/write by cognitive engines
│                          # Safe zone for processed, validated data
│
├── scratch/               # Ephemeral transformations
│                          # Restricted temp area for tool output staging
│                          # Cleared between sessions (optional)
│
├── outbox/                # Safe egress point
│                          # Local files waiting for broadcast/posting
│                          # Tools can write here; user controls distribution
│
├── cartridges/            # Read-only configuration & models
│                          # Frozen rulesets, embeddings, quantized models
│                          # Tools forbidden from writing here
│
└── inbox/                 # Raw input ingestion root
    ├── trusted/           # ONLY direct user-written inputs
    │                      # OR authenticated manual copies from user
    │                      # Safe to read; no auto-promotion to workspace
    │
    └── external/          # The Airlock (quarantine zone)
                           # ALL network/email/RSS tools MUST write here
                           # NO tool can read from external/ without validation
                           # ONE-WAY gate: external → workspace via validator
```

### Trust Levels (by directory)

| Directory | Read | Write | Auto-Promote | Tool Use |
|-----------|------|-------|--------------|----------|
| **workspace/** | ✅ Safe | ✅ Safe | ✅ Trusted data only | Primary reasoning layer |
| **scratch/** | ✅ OK | ✅ Temp | ❌ Never | Tool staging/debug |
| **outbox/** | ✅ OK | ✅ OK | ⚠️ User controls | Network egress (webhooks, etc.) |
| **cartridges/** | ✅ OK | ❌ FORBIDDEN | N/A | Model/config storage only |
| **inbox/trusted/** | ✅ Safe | ⚠️ User only | ⚠️ Manual only | User-provided input |
| **inbox/external/** | ❌ Forbidden | ✅ Tools only | ❌ Never | Network quarantine |

### Filesystem Access Tool (v1) — Boundary Enforcement

The `tools/filesystem_access/` tool implements these rules via path validation:

```python
ALLOWED_PATHS = {
    'workspace/': ('read', 'write'),      # High-trust
    'scratch/': ('read', 'write'),        # Ephemeral
    'inbox/trusted/': ('read',),          # Manual input only
    'inbox/external/': ('read', 'write'),  # Quarantine (special rules)
    'outbox/': ('read', 'write'),         # Egress only
    'cartridges/': ('read',),             # Read-only config
}

REJECTED_OPERATIONS = [
    'write_to_cartridges',      # Hard block on model/config modification
    'promote_external_to_workspace',  # Must go through validator
    'follow_symlinks',          # Prevent escape via symbolic links
    'recursive_unlisted_dirs',  # Enumerate before traversing
]
```

**Implementation rule:** Every filesystem operation by a tool goes through this validator. Rejected paths fail-loud with clear error message.

---

## Part 2: Consent-Gated Asset Fetching

Tools requiring heavy external assets (spaCy language models, Whisper STT weights, ONNX classifiers, quantized vision models) must not fail silently or block execution. Instead, they implement a **three-tier consent gate**.

### The Three-Tier Flow

#### **Tier 1: Check Local Cache (Cartridges)**

Tool startup checks `cartridges/` for asset:
```
cartridges/
├── models/
│   ├── spacy_en_core_web_sm.tar.gz
│   ├── whisper_base_quantized.onnx
│   └── piper_tts_en_us.model
├── asset_manifest.json    # SHA-256 hashes + source URLs
└── asset_index.json       # Which tool uses which asset
```

If asset present and hash matches manifest → **load and proceed** (fast path).

#### **Tier 2: Asset Missing → User Authorization Prompt**

If asset not found locally:

1. **Tool yields NeedsUserAuthorization signal** to orchestrator
   ```json
   {
     "signal_type": "needs_user_authorization",
     "tool": "spacy_ner_extractor",
     "asset_name": "en_core_web_sm",
     "asset_size_mb": 45,
     "source_url": "https://github.com/explosion/spacy-models/releases/download/...",
     "source_sha256": "abc123def456...",
     "cache_path": "cartridges/models/spacy_en_core_web_sm.tar.gz"
   }
   ```

2. **Orchestrator halts execution, presents user prompt:**
   ```
   Tool 'Named Entity Recognition (spaCy)' requires downloading 'en_core_web_sm' (~45 MB)
   from: https://github.com/explosion/spacy-models/releases/download/...
   
   This model will be cached in cartridges/ for offline reuse.
   
   Allow download? [Y/n/details]
   ```

3. **User decision:**
   - **Yes (Y):** Proceed to Tier 3 (secure download)
   - **No (n):** Tool fails with message "User denied asset download"
   - **Details:** Show integrity check (SHA-256), source, and previous audit trail

#### **Tier 3: Secure Download & Verification**

If user approves:

1. **Dedicated secure download utility** (single-purpose, hardened):
   ```
   tools/secure_asset_downloader/
   ├── __init__.py
   ├── core.py              # urllib.request wrapper with safety checks
   ├── integrity_checker.py # SHA-256 verification
   └── extract_cache.py     # Atomic tar extraction to cartridges/
   ```

2. **Integrity verification:**
   - Download asset + accompanying signature file
   - Verify SHA-256 hash against manifest before extraction
   - If hash mismatch → reject, alert user, DO NOT cache
   - Extract only to `cartridges/models/` (not scratch, not workspace)

3. **Update asset index:**
   ```json
   // cartridges/asset_index.json (append)
   {
     "asset": "en_core_web_sm",
     "downloaded_at": "2026-07-14T14:30:45Z",
     "hash": "abc123def456...",
     "size_bytes": 47185920,
     "source_url": "https://github.com/...",
     "user_approved": true,
     "approval_timestamp": "2026-07-14T14:25:00Z"
   }
   ```

4. **Resume tool execution** with asset now available locally

### Tools Requiring Consent-Gated Assets

**Current (v1 tools):**
- `tools/named_entity_recognition/` (spaCy en_core_web_sm)
- `tools/local_speech_to_text/` (Whisper quantized weights)
- `tools/local_text_to_speech/` (Piper TTS model)
- `tools/edge_vision_classifier/` (ONNX quantized classifier)

**Future (post-2.0):**
- Any tool using downloaded embeddings, language models, or pretrained vision weights

### Audit Trail

Every consent-gated download is logged:
```json
// inbox/external/asset_downloads.jsonl
{"timestamp": "2026-07-14T14:30:45Z", "tool": "spacy_ner", "asset": "en_core_web_sm", "size_mb": 45, "user_approved": true, "hash_verified": true, "cache_path": "cartridges/models/spacy_en_core_web_sm.tar.gz"}
{"timestamp": "2026-07-14T14:35:10Z", "tool": "whisper_stt", "asset": "whisper_base.onnx", "size_mb": 140, "user_approved": false, "reason": "user_denied"}
```

---

## Part 3: Mandatory Gateway Airlock Validation

External ingestion tools (HTTP, IMAP, RSS, Home Assistant) are forbidden from writing directly to `workspace/` or `scratch/`. All external data must pass through a validation gate.

### The One-Way Gate: external/ → workspace/

```
inbox/external/          [QUARANTINE]
    ↓ (raw, untrusted)
Structured Input Validator v1
    ↓ (validate against schema)
workspace/               [SAFE]
    ↓ (now usable by cognitive engines)
```

### Validation Rules

1. **All external ingestion tools write to `inbox/external/` only**
   ```python
   # tools/rss_feed_fetcher/
   output_path = workspace_root / "inbox" / "external" / f"feeds_{timestamp}.json"
   
   # tools/raw_http_ingester/
   output_path = workspace_root / "inbox" / "external" / f"http_response_{timestamp}.json"
   
   # tools/imap_single_message_fetcher/
   output_path = workspace_root / "inbox" / "external" / f"email_{timestamp}.json"
   ```

2. **Files in `inbox/external/` are QUARANTINED**
   - No tool reads directly from external/ without explicit schema validation
   - No orchestrator passes external/ data to cognitive engines without validation
   - Files remain in external/ until user/validator explicitly promotes them

3. **Structured Input Validator acts as exclusive gatekeeper**
   ```
   // Before tool invocation
   orchestrator.validate(
       input_file="inbox/external/feeds_2026-07-14.json",
       schema_grammar="tools/structured_validator/grammars/rss_feed.lark",
       output_path="workspace/feeds_validated.json"
   )
   
   // If validation passes → promote to workspace/
   // If validation fails → quarantine remains, error logged, user notified
   ```

4. **Schema grammars live in `cartridges/`**
   ```
   cartridges/
   └── validator_grammars/
       ├── rss_feed.lark          # RSS/Atom feed format
       ├── email_envelope.lark    # IMAP message format
       ├── http_json_response.lark # HTTP response structure
       └── home_assistant_state.lark
   ```

### Example: RSS Feed Fetcher

```
1. RSS Tool Fetches Feed
   └─ Writes to: inbox/external/feeds_2026-07-14T14_30_45.json
   └─ Format: Raw JSON array of feed entries

2. Orchestrator Invokes Validator
   └─ Schema: cartridges/validator_grammars/rss_feed.lark
   └─ Validation: Check required fields (title, link, pubDate, etc.)
   └─ On success → output to workspace/feeds_validated.json
   └─ On failure → quarantine + alert user

3. Cognitive Engine Reads from workspace/
   └─ Guaranteed valid structure
   └─ No malformed data in pipeline
```

---

## Part 4: Local Network Proxy Hardening

Tools making HTTP/HTTPS requests must not inherit ambient environment proxy settings (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`). This prevents tools from leaking data through uncontrolled proxies.

### Implementation Rule

All network tools **explicitly disable proxy lookup** unless overridden in secure registry config:

```python
# tools/raw_http_ingester/core.py
import urllib.request

# CORRECT: Explicit no-proxy handling
def fetch_url(url: str, use_proxy: bool = False) -> str:
    """
    Fetch URL strictly locally unless explicitly enabled in config.
    
    Args:
        url: Target URL
        use_proxy: If True, check cartridges/network_config.json for approved proxies
    
    Returns:
        Response body as string
    """
    if use_proxy:
        # Load approved proxy from cartridges/ only
        proxy_config = load_config("cartridges/network_config.json")
        proxy_handler = urllib.request.ProxyHandler(proxy_config)
        opener = urllib.request.build_opener(proxy_handler)
    else:
        # No proxy: direct connection only
        proxy_handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(proxy_handler)
    
    # Disable environment variable proxy lookup
    urllib.request.install_opener(opener)
    
    try:
        with opener.open(url, timeout=30) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        raise RuntimeError(f"HTTP fetch failed: {e}")
```

### Configuration

Proxy settings (if needed) live in **cartridges/** and require user approval:

```json
// cartridges/network_config.json
{
  "http_proxy": null,
  "https_proxy": null,
  "proxy_whitelist": [],
  "approved_by": "user",
  "approved_at": "2026-07-14T14:30:45Z",
  "reason": "Corporate proxy for web access"
}
```

Network tools read this config explicitly; if missing, default to no-proxy mode.

---

## Part 5: Tool Classification & Safety Checklist

All 49 tools fall into one of three categories:

### Category A: Stateless Compute (Safe)
**No filesystem access beyond scratch/, no network, no external dependencies.**

Examples:
- DateTime Utilities
- Text Search
- Math Evaluation
- Sequence Pattern Miner
- Conditional Pattern Detector

**Safety checklist:**
- ✅ Reads from stdin (JSON/text)
- ✅ Outputs to stdout (JSON)
- ✅ No filesystem I/O
- ✅ No network access
- ✅ Dependencies: stdlib only
- ✅ No user consent needed

### Category B: Controlled I/O (Gated)
**Filesystem access via validator; no network without explicit config.**

Examples:
- Filesystem Access
- Templating
- Log Parser
- Simple Version Control
- Duplicate Detection

**Safety checklist:**
- ✅ Filesystem access via Filesystem Access tool (boundary-enforced)
- ✅ Outputs to workspace/ or scratch/ only
- ✅ No unsanctioned network access
- ✅ Dependencies: stdlib + approved PyPI
- ⚠️ User awareness required (file I/O auditable)

### Category C: External Integration (Gated + Validated)
**Network access; external asset downloads; mandatory quarantine gates.**

Examples:
- RSS Feed Fetcher → writes to inbox/external/
- Raw HTTP Ingester → writes to inbox/external/
- IMAP Single-Message Fetcher → writes to inbox/external/
- Home Assistant Bridge → reads config from cartridges/
- Local STT/TTS → require consent-gated model downloads
- Local Vision Classifier → require consent-gated weights

**Safety checklist:**
- ❌ NO direct writes to workspace/ or scratch/
- ✅ Writes to inbox/external/ (quarantine)
- ✅ All external data must pass Structured Input Validator
- ✅ Network: No ambient proxy; config-driven only
- ✅ Asset downloads: Consent-gated, integrity-verified, cached in cartridges/
- ✅ Audit trail: All external ops logged (downloads, network requests, schema validations)
- 🔴 **User consent required** (network access, model downloads)

---

## Part 6: Audit Trail & Observability

All safety-critical operations are logged to `inbox/external/audit.jsonl`:

```jsonl
{"timestamp": "2026-07-14T14:30:45Z", "event": "tool_invoked", "tool": "rss_feed_fetcher", "status": "success"}
{"timestamp": "2026-07-14T14:30:50Z", "event": "file_written", "tool": "rss_feed_fetcher", "path": "inbox/external/feeds_2026-07-14.json", "size_bytes": 12345}
{"timestamp": "2026-07-14T14:31:00Z", "event": "validation_invoked", "validator": "structured_input_validator", "schema": "rss_feed.lark", "input": "inbox/external/feeds_2026-07-14.json", "status": "passed"}
{"timestamp": "2026-07-14T14:31:05Z", "event": "file_promoted", "source": "inbox/external/feeds_2026-07-14.json", "destination": "workspace/feeds_validated.json", "status": "success"}
{"timestamp": "2026-07-14T14:35:10Z", "event": "asset_download_requested", "tool": "local_speech_to_text", "asset": "whisper_base.onnx", "size_mb": 140, "status": "user_denied"}
{"timestamp": "2026-07-14T15:00:00Z", "event": "asset_download_requested", "tool": "spacy_ner", "asset": "en_core_web_sm", "size_mb": 45, "source_url": "https://github.com/...", "status": "user_approved"}
{"timestamp": "2026-07-14T15:00:30Z", "event": "asset_download_completed", "tool": "spacy_ner", "asset": "en_core_web_sm", "hash_verified": true, "cache_path": "cartridges/models/spacy_en_core_web_sm.tar.gz"}
```

**Log rotation policy:** Monthly; old logs archived (non-destructive archival principle).

---

## Part 7: Trust Model Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     TRUST BOUNDARIES                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  workspace/           [TRUSTED]  ✅ Cognitive engines read      │
│      ↑                           ✅ Validated data only          │
│      │                                                           │
│      └─── Structured Input Validator v1 [GATEKEEPER]            │
│             ↑                                                    │
│             │ (Only source of truth → workspace/)                │
│             │                                                    │
│  inbox/external/      [QUARANTINE] ❌ No direct reads            │
│      ↑                             ❌ Raw external data only      │
│      │                             ✅ All ingestion tools write  │
│      │                             ✅ Auditable, isolated        │
│      │                                                           │
│  External Networks    [UNTRUSTED]  ❌ No trust                  │
│      ├─ HTTP/HTTPS                ✅ Explicit consent gates     │
│      ├─ Email (IMAP)              ✅ Proxy-hardened            │
│      ├─ RSS Feeds                 ✅ Integrity-verified         │
│      └─ Home Assistant            ✅ Config-driven only         │
│                                                                  │
│  cartridges/          [CONFIG]    ✅ Read-only                 │
│      ├─ Models                    ✅ Consent-gated downloads    │
│      ├─ Grammars                  ✅ Validator schemas          │
│      └─ Network Config            ✅ User-approved proxies      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 8: Threat Model & Mitigations

### Threat 1: Malformed External Data Leaks Into Workspace

**Attack:** Ingestion tool fetches RSS feed with malicious JSON; writes to `workspace/` directly; downstream cognitive engine crashes.

**Mitigation:**
- ✅ Ingestion tools **forced** to write to `inbox/external/` only (Filesystem Access validator)
- ✅ One-way gate: external/ → workspace/ via Structured Input Validator
- ✅ Validator checks schema (e.g., RSS grammar); rejects on mismatch
- ✅ Malformed data stays quarantined in external/; user notified

### Threat 2: Unsanctioned Network Access / Data Exfiltration

**Attack:** Tool inherits `HTTP_PROXY` environment variable; leaks data through corporate proxy; user unaware.

**Mitigation:**
- ✅ Network tools **disable proxy lookup** by default
- ✅ Proxy config lives in `cartridges/` (user-approved, auditable)
- ✅ Each network request logged to audit trail
- ✅ No "ambient" proxy inheritance

### Threat 3: Consent-Gated Model Download is Hijacked

**Attack:** User approves Whisper model download; attacker's replica is served instead; fake weights loaded.

**Mitigation:**
- ✅ SHA-256 hash verification before extraction
- ✅ Hash comes from manifest (source of truth)
- ✅ Download rejected if hash mismatch; NOT cached
- ✅ User shown source URL + hash in approval prompt
- ✅ Audit trail logs actual hash received vs. expected

### Threat 4: Cartridges/ is Modified by Tool (Violates Immutability)

**Attack:** Tool writes forged model weights to `cartridges/models/` ; corrupts cognitive stack.

**Mitigation:**
- ✅ Filesystem Access validator **rejects all writes to cartridges/**
- ✅ Only secure_asset_downloader (single-purpose) can write to cartridges/
- ✅ secure_asset_downloader runs after user approval + hash verification
- ✅ Hardened deployment: filesystem permissions (chmod 555 on cartridges/)

### Threat 5: Symlink Escape

**Attack:** Tool creates symlink in `inbox/external/` pointing to `workspace/` ; bypasses Structured Input Validator.

**Mitigation:**
- ✅ Filesystem Access validator **rejects symlink following**
- ✅ All directory traversals **enumerate first** (no recursive listing)
- ✅ Symlinks detected and logged as security event

---

## Part 9: Implementation Checklist for Tool Developers

Every tool (especially Category B & C) must verify:

### Filesystem Safety
- [ ] Tool uses `Filesystem Access v1` for any I/O (don't call `open()` directly)
- [ ] Tool specifies allowed_paths in Filesystem Access call
- [ ] Tool never writes to `cartridges/`
- [ ] Tool writes external ingestion to `inbox/external/` only (not workspace/scratch)
- [ ] Tool handles path validation errors gracefully (fail-loud)

### Network Safety (if applicable)
- [ ] Tool disables proxy lookup by default (use urllib without proxy handler)
- [ ] If proxy needed, reads from `cartridges/network_config.json` only
- [ ] Tool logs all network requests to audit trail
- [ ] Tool implements timeout (e.g., 30 seconds)

### Asset Download Safety (if applicable)
- [ ] Tool checks `cartridges/` cache first
- [ ] If missing, tool yields `NeedsUserAuthorization` signal
- [ ] Tool uses `secure_asset_downloader` utility (don't implement own download)
- [ ] Tool verifies SHA-256 before loading asset
- [ ] Tool updates `cartridges/asset_index.json` after successful download

### Validation Safety (if applicable)
- [ ] Tool documents expected input schema (e.g., RSS grammar)
- [ ] Tool mentions Structured Input Validator in README
- [ ] Tool suggests schema grammar location (e.g., `cartridges/validator_grammars/rss_feed.lark`)

### Audit & Logging
- [ ] Tool uses `structured_logger.get_event_logger("<tool_name>")`
- [ ] Tool logs: tool_invoked, file_written, validation_passed/failed, download_approved/denied
- [ ] Tool includes metadata (file paths, sizes, hashes, user decisions)

### CLI & Error Handling
- [ ] Tool exits with code 0 (success) / 1 (ValueError) / 2 (RuntimeError)
- [ ] Tool fails-loud on safety violations (don't silently degrade)
- [ ] Tool includes clear error messages (help user understand boundary violation)

---

## Part 10: Future Evolution

### Post-1.0 Enhancements

1. **Permission Management UI** — User can review/revoke consents and asset downloads
2. **Threat Detection** — Anomaly scorer flags unusual network/filesystem patterns
3. **Tool Sandboxing** — Run Category C tools in isolated containers (low priority for v1)
4. **Signed Manifests** — Asset manifests signed by Anthropic/maintainer (future)

### Deferred to Later

- Full TLS pinning for network tools (verify server certificates)
- Encrypted cartridges/ (model weights at-rest)
- Key management for signed downloads

---

## Summary

The Kitbash tools architecture implements **trust through isolation, validation, and transparency**:

1. **Filesystem Airlock** — External data quarantined in `inbox/external/`; one-way gate to workspace/ via validator
2. **Consent-Gated Assets** — Heavy downloads require explicit user approval; integrity-verified before caching
3. **Proxy Hardening** — No ambient proxy inheritance; config-driven only
4. **Audit Trail** — All safety-critical ops logged; user can review history
5. **Fail-Loud Design** — Safety violations raise clear errors; no silent degradation

This enables Kitbash to safely integrate external data sources and models while maintaining local-first guarantees and user control.

---

**Last updated:** 2026-07-14  
**For:** tools/ ecosystem developers and orchestrator integration  
**Related:** POST_MVP_ROADMAP.md, SPEC_TOOL_REGISTRY_INFRASTRUCTURE.md
