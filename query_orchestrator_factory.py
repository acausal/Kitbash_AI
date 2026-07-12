"""
query_orchestrator_factory.py

Factory for creating a POSIX-compliant QueryOrchestrator with all dependencies
properly wired.

This module bridges the old Phase 3E implementation (which builds everything
from scratch) with the new POSIX interface layer (which accepts dependency
objects). It creates adapters and wires them together.

Usage:
    orchestrator = create_query_orchestrator(
        cartridges_dir="./cartridges",
        enable_grain_system=True,
        device="cpu"
    )
    
    result = orchestrator.process_query("What is ATP?")
"""

import logging
from typing import Optional, Dict, Any

from interfaces.triage_agent import TriageAgent
from interfaces.inference_engine import InferenceEngine
from interfaces.mamba_context_service import MambaContextService
from resonance_weights import ResonanceWeightService
from heartbeat_service import HeartbeatService

from grain_engine import GrainEngine
from cartridge_engine import CartridgeEngine
from bitnet_engine import BitNetEngine
from rule_based_triage import RuleBasedTriageAgent
from mock_mamba_service import MockMambaService
from real_mamba_service import RealMambaService

# Import existing Phase 3E components (unchanged)
try:
    from cartridge_loader import CartridgeInferenceEngine
    from grain_router import GrainRouter
    # SPEC §6: MTR import swapped to MTR_v6_1 (the repo's shipping engine).
    # Fall back to the legacy MTR_v5_5_NN name if a deployment still ships it.
    try:
        from MTR_v6_1 import KitbashMTREngine
    except ImportError:
        from MTR_v5_5_NN import KitbashMTREngine
    from grain_system import ShannonGrainOrchestrator
    from mtr_state_manager import MTRStateCheckpoint
    from mtr_grain_bridge import MTRGrainUnifiedPipeline, HatKappaMapper
    GRAIN_SYSTEM_AVAILABLE = True
except ImportError as e:
    GRAIN_SYSTEM_AVAILABLE = False
    logging.warning(f"Grain system not available: {e}")

logger = logging.getLogger(__name__)


def create_query_orchestrator(
    cartridges_dir: str = "./cartridges",
    vocab_size: int = 50257,
    d_model: int = 256,
    d_state: int = 144,
    state_dir: str = "data/state",
    grain_storage_dir: str = "./grains",
    device: str = "cpu",
    enable_grain_system: bool = True,
    dream_bucket_dir: str = "data/subconscious/dream_bucket",
    enable_bitnet: bool = False,
    bitnet_url: str = "http://127.0.0.1:8080",
    bitnet_max_tokens: int = 256,
    enable_mamba: bool = False,
    mamba_host: str = "127.0.0.1",
    mamba_port: int = 8731,
    mamba_model_path: str = "B:/ai/llm/kitbash/models/bitmamba/bitmamba_255m.bin",
    mamba_exe_path: str = "B:/ai/llm/kitbash/bitmamba.cpp/build/Release/bitmamba_server.exe",
    mamba_cwd: str = "B:/ai/llm/kitbash/bitmamba.cpp",
    mamba_max_tokens: int = 200,
    mamba_autostart: bool = True,
    verbose: bool = False,
) -> Any:
    """
    Factory function to create a fully-wired QueryOrchestrator.
    
    This creates all the POSIX interface implementations, wires them to the
    existing Phase 3E components, and returns a QueryOrchestrator ready to use.
    
    Args:
        cartridges_dir: Path to cartridge files
        vocab_size: MTR vocabulary size
        d_model: MTR embedding dimension
        d_state: MTR state space dimension
        state_dir: MTR checkpoint directory
        grain_storage_dir: Grain registry directory
        device: torch device (cpu, cuda)
        enable_grain_system: Enable grain system
        dream_bucket_dir: Dream bucket directory
        enable_bitnet: Include BitNet in engine cascade
        bitnet_url: BitNet server URL
        verbose: Enable verbose logging
        
    Returns:
        QueryOrchestrator instance (from uploaded version, with POSIX interface)
        
    Raises:
        RuntimeError: If required components cannot be initialized
    """
    
    logger.info("Creating QueryOrchestrator with POSIX interfaces...")
    
    # ========================================================================
    # STEP 1: Build Phase 3E components (unchanged logic)
    # ========================================================================
    
    logger.debug("Step 1: Initializing Phase 3E components...")
    
    # CartridgeLoader
    try:
        from cartridge_loader import CartridgeInferenceEngine
        from dream_bucket import DreamBucketWriter

        dream_bucket_writer = DreamBucketWriter(dream_bucket_dir) if dream_bucket_dir else None

        cartridge_engine_phase3e = CartridgeInferenceEngine(
            cartridges_dir,
            dream_bucket_writer=dream_bucket_writer,
        )
        logger.info(f"  ✓ CartridgeLoader: {cartridge_engine_phase3e.registry.get_stats()['total_facts']} facts"
                    + (f" (dream_bucket={dream_bucket_dir})" if dream_bucket_writer else " (dream_bucket=None)"))
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize CartridgeLoader: {e}")
        raise
    
    # MTR Engine
    try:
        mtr_engine = KitbashMTREngine(
            vocab_size=vocab_size,
            d_model=d_model,
            d_state=d_state,
        )
        mtr_engine = mtr_engine.to(device)
        logger.info(f"  ✓ MTREngine initialized")
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize MTREngine: {e}")
        raise
    
    # State Manager
    try:
        state_manager = MTRStateCheckpoint(state_dir)
        # SPEC Step 4: resume MTR state at build if a checkpoint exists.
        # Guarded: load() deserializes torch tensors, so it is a no-op until
        # torch is installed (T8) — a missing/absent checkpoint is fine.
        try:
            loaded = state_manager.load(device)
            # loaded == (mtr_state_dict, metadata) or None. Capture the state
            # so it can be seeded into the LearningObserver after construction
            # (SPEC Step 4: the counter must RESUME, not restart from 0).
            loaded_mtr_state = loaded[0] if loaded else None
            if loaded_mtr_state is not None:
                logger.info("  ✓ MTR state resumed from checkpoint")
        except Exception:
            logger.debug("  (no prior MTR checkpoint to resume)")
        logger.info(f"  ✓ StateManager initialized")
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize StateManager: {e}")
        raise
    
    # Grain System (if enabled)
    grain_router = None
    grain_orchestrator = None
    mtr_grain_pipeline = None
    
    if enable_grain_system and GRAIN_SYSTEM_AVAILABLE:
        try:
            grain_orchestrator = ShannonGrainOrchestrator(
                cartridge_id="default",
                storage_path=grain_storage_dir,
                cartridge_engine=cartridge_engine_phase3e
            )
            
            grain_router = GrainRouter(
                cartridges_dir=cartridges_dir,
                cartridge_engine=cartridge_engine_phase3e,
                dream_bucket_writer=dream_bucket_writer,
            )
            
            first_cartridge = next(
                iter(cartridge_engine_phase3e.registry.cartridges.values())
            ) if cartridge_engine_phase3e.registry.cartridges else None
            
            mtr_grain_pipeline = MTRGrainUnifiedPipeline(
                mtr_grain_orchestrator=grain_orchestrator,
                grain_router=grain_router,
                trigger_interval=51,
                cartridge=first_cartridge
            )
            
            logger.info(f"  ✓ Grain system initialized ({grain_router.total_grains} grains)")
        except Exception as e:
            logger.warning(f"  ⚠ Grain system initialization failed: {e}")
            enable_grain_system = False
    
    # ========================================================================
    # STEP 2: Create POSIX interface implementations (adapters)
    # ========================================================================
    
    logger.debug("Step 2: Creating POSIX interface implementations...")
    
    # ResonanceWeightService (Tier 5)
    try:
        resonance_service = ResonanceWeightService(
            initial_stability=3.0,
            stability_growth=2.0,
            cleanup_threshold=0.001,
            spacing_sensitive=False
        )
        logger.info(f"  ✓ ResonanceWeightService initialized")
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize ResonanceWeightService: {e}")
        raise
    
    # TriageAgent (routing)
    try:
        triage_agent = RuleBasedTriageAgent(verbose=verbose, enable_bitnet=enable_bitnet)
        logger.info(f"  ✓ RuleBasedTriageAgent initialized (bitnet_routing={enable_bitnet})")
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize TriageAgent: {e}")
        raise
    
    # InferenceEngines (adapters to Phase 3E components)
    engines: Dict[str, InferenceEngine] = {}
    
    try:
        # Grain Engine (F2: wrap the shared GrainRouter, do not rebuild it)
        grain_engine = GrainEngine(
            cartridges_dir=cartridges_dir,
            grain_router=grain_router,
        )
        engines["GRAIN"] = grain_engine
        logger.info(f"  ✓ GrainEngine created (wraps shared GrainRouter)")
    except Exception as e:
        logger.warning(f"  ⚠ Failed to create GrainEngine: {e}")
    
    try:
        # Cartridge Engine (F2: wrap the shared CartridgeInferenceEngine)
        cartridge_engine = CartridgeEngine(
            cartridges_dir=cartridges_dir,
            cartridge_engine=cartridge_engine_phase3e,
        )
        engines["CARTRIDGE"] = cartridge_engine
        logger.info(f"  ✓ CartridgeEngine created (wraps shared CartridgeInferenceEngine)")
    except Exception as e:
        logger.warning(f"  ⚠ Failed to create CartridgeEngine: {e}")
    
    try:
        # BitNet Engine (optional)
        if enable_bitnet:
            bitnet_engine = BitNetEngine(server_url=bitnet_url, max_tokens=bitnet_max_tokens)
            engines["BITNET"] = bitnet_engine
            logger.info(f"  ✓ BitNetEngine created (server: {bitnet_url}, max_tokens={bitnet_max_tokens})")
    except Exception as e:
        logger.warning(f"  ⚠ BitNet initialization skipped: {e}")
    
    if not engines:
        logger.error("No inference engines available!")
        raise RuntimeError("Failed to create any inference engines")
    
    # MambaContextService — real BitMamba2 (Option B2) when enabled, mock otherwise.
    # RealMambaService is a TCP client to bitmamba_server; it never raises to the
    # orchestrator (graceful empty-context fallback). enable_mamba defaults False
    # so existing callers are unaffected until they opt in.
    try:
        if enable_mamba:
            mamba_service = RealMambaService(
                host=mamba_host,
                port=mamba_port,
                model_path=mamba_model_path,
                exe_path=mamba_exe_path,
                cwd=mamba_cwd,
                max_tokens=mamba_max_tokens,
                enabled=True,
                autostart=mamba_autostart,
            )
            logger.info(
                f"  ✓ RealMambaService initialized (BitMamba2 @ {mamba_host}:{mamba_port}, "
                f"autostart={mamba_autostart})"
            )
        else:
            mamba_service = MockMambaService()
            logger.info(f"  ✓ MockMambaService initialized (Mamba disabled)")
    except Exception as e:
        logger.warning(f"  ⚠ RealMambaService unavailable, falling back to mock: {e}")
        mamba_service = MockMambaService()
    
    # HeartbeatService (pause/resume background work)
    try:
        heartbeat = HeartbeatService(initial_turn=0)
        logger.info(f"  ✓ HeartbeatService initialized")
    except Exception as e:
        logger.error(f"  ✗ Failed to initialize HeartbeatService: {e}")
        raise
    
    # ========================================================================
    # STEP 3: Create POSIX QueryOrchestrator with wired dependencies
    # ========================================================================
    
    logger.debug("Step 3: Creating POSIX QueryOrchestrator...")
    
    try:
        # Import the POSIX version from uploaded file
        from query_orchestrator_posix import QueryOrchestrator as POSIXQueryOrchestrator
        
        # SPEC Step 3: build the LearningObserver from the SAME shared instances
        # and inject it. The observer's learning path needs MTR (always required
        # by this factory), NOT grain — so it is built whenever mtr_engine exists,
        # independent of enable_grain_system. Guarded: a missing component must
        # NOT prevent orchestrator creation — observer stays optional.
        learning_observer = None
        if mtr_engine is not None:
            try:
                # Mutation 2 (L2WorkingTheoryService canonical wiring):
                # port the donor instantiation (attic/query_orchestrator.py:280-284)
                # so the observer receives a real, functioning instance instead of
                # None. Read-only audit service; grain_orchestrator may be None if
                # grain system disabled (service guards on None internally).
                from l2_working_theory_service import L2WorkingTheoryService
                l2_service = L2WorkingTheoryService(
                    dream_bucket_dir=dream_bucket_dir,
                    grain_orchestrator=grain_orchestrator,
                )
                logger.info("  ✓ L2WorkingTheoryService constructed (Mutation 2)")

                from learning_observer import LearningObserver
                learning_observer = LearningObserver(
                    mtr_engine=mtr_engine,
                    state_manager=state_manager,
                    cartridge_engine=cartridge_engine_phase3e,
                    grain_router=grain_router,
                    mtr_grain_pipeline=mtr_grain_pipeline,
                    l2_service=l2_service,
                    dream_bucket_writer=dream_bucket_writer,  # NEW: wire trace sink (was None → traces lost)
                )
                logger.info("  ✓ LearningObserver constructed and wired")
            except Exception as e:
                logger.warning(f"  ⚠ Could not construct LearningObserver: {e}")

        # SPEC Step 4: seed the resumed MTR state into the observer so the
        # query/time counter continues from the checkpoint instead of 0.
        if learning_observer is not None and loaded_mtr_state is not None:
            try:
                learning_observer.mtr_state = loaded_mtr_state
            except Exception as e:
                logger.warning(f"  ⚠ Could not seed observer MTR state: {e}")

        # SPEC Phase 3B.3: wire Redis-backed diagnostic feed + coupling client.
        # kitbash-redis (standalone Docker container, localhost:6379) is the
        # canonical Redis. RedisDiagnosticFeed degrades to no-op if Redis is
        # down, so the orchestrator still starts and answers (soft-fail).
        diagnostic_feed = None
        redis_client = None
        try:
            from redis_blackboard import RedisDiagnosticFeed
            diagnostic_feed = RedisDiagnosticFeed()  # pings kitbash-redis; no-op if down
            if diagnostic_feed._alive:
                import redis
                redis_client = diagnostic_feed.redis
                logger.info("  ✓ RedisDiagnosticFeed active (kitbash-redis)")
            else:
                logger.warning("  ⚠ RedisDiagnosticFeed degraded to no-op (kitbash-redis down)")
        except Exception as e:
            logger.warning(f"  ⚠ Could not build RedisDiagnosticFeed: {e} (no-op feed)")

        orchestrator = POSIXQueryOrchestrator(
            triage_agent=triage_agent,
            engines=engines,
            mamba_service=mamba_service,
            resonance=resonance_service,
            heartbeat=heartbeat,
            metabolism_scheduler=None,  # Phase3B: no background scheduler yet
            shannon=grain_orchestrator if enable_grain_system else None,
            diagnostic_feed=diagnostic_feed,  # RedisDiagnosticFeed or None -> no-op
            redis_client=redis_client,  # shared kitbash-redis client (coupling) or None
            learning_observer=learning_observer,  # SPEC Step3
        )
        
        logger.info(f"  ✓ QueryOrchestrator initialized with {len(engines)} engines")
        
    except ImportError:
        logger.warning("POSIX QueryOrchestrator not available, using Phase 3E version")
        # Fallback: return Phase 3E orchestrator (different interface)
        # This won't have full POSIX compliance but will work
        raise RuntimeError(
            "POSIX QueryOrchestrator (query_orchestrator_posix.py) not found. "
            "Please provide the POSIX version to enable interface-based architecture."
        )
    except Exception as e:
        logger.error(f"  ✗ Failed to create QueryOrchestrator: {e}")
        raise
    
    logger.info("✓ QueryOrchestrator fully initialized with POSIX interfaces")
    
    return orchestrator


def create_minimal_orchestrator(
    cartridges_dir: str = "./cartridges",
) -> Any:
    """
    Create a minimal QueryOrchestrator with just essentials.
    
    Useful for testing or MVP deployments.
    
    Args:
        cartridges_dir: Path to cartridges
        
    Returns:
        QueryOrchestrator instance
    """
    return create_query_orchestrator(
        cartridges_dir=cartridges_dir,
        device="cpu",
        enable_grain_system=False,
        enable_bitnet=False,
        verbose=False
    )


if __name__ == "__main__":
    """Test the factory."""
    import sys
    
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(levelname)s: %(message)s"
    )
    
    try:
        print("Creating QueryOrchestrator via factory...\n")
        orch = create_query_orchestrator(verbose=True)
        print("\n✓ Factory test successful!")
        print(f"Orchestrator: {orch}")
        print(f"Engines: {list(orch.engines.keys())}")
    except Exception as e:
        print(f"\n✗ Factory test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
