"""
TEST-factory_basic.py

Minimal test for query_orchestrator_factory.py
Tests: imports, factory initialization, basic wiring

Run from your project root:
    python TEST-factory_basic.py
"""

import sys
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

logger = logging.getLogger(__name__)


def test_imports():
    """Test that all imports work."""
    print("\n" + "="*70)
    print("TEST 1: Import Chain")
    print("="*70)
    
    try:
        print("  Importing factory...")
        from query_orchestrator_factory import create_query_orchestrator
        print("  ✓ Factory imported successfully")
        return True
    except ImportError as e:
        print(f"  ✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factory_creation(cartridges_dir="./cartridges"):
    """Test factory initialization."""
    print("\n" + "="*70)
    print("TEST 2: Factory Initialization")
    print("="*70)
    
    try:
        from query_orchestrator_factory import create_query_orchestrator
        
        print(f"  Creating orchestrator (cartridges: {cartridges_dir})...")
        orch = create_query_orchestrator(
            cartridges_dir=cartridges_dir,
            device="cpu",
            enable_grain_system=True,
            enable_bitnet=False,
            verbose=True
        )
        
        print("  ✓ Orchestrator created successfully")
        
        # Check basic attributes
        if hasattr(orch, 'engines'):
            print(f"  ✓ Engines available: {list(orch.engines.keys())}")
        
        if hasattr(orch, 'triage_agent'):
            print(f"  ✓ Triage agent: {orch.triage_agent.__class__.__name__}")
        
        return orch
        
    except FileNotFoundError as e:
        print(f"  ✗ File not found (missing Phase 3E component?): {e}")
        return None
    except Exception as e:
        print(f"  ✗ Factory creation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_basic_query(orch):
    """Test a basic query through the orchestrator."""
    print("\n" + "="*70)
    print("TEST 3: Basic Query")
    print("="*70)
    
    if not orch:
        print("  ⊗ Skipped (no orchestrator)")
        return False
    
    try:
        # Check if orchestrator has a process_query method
        if not hasattr(orch, 'process_query'):
            print("  ⚠ Orchestrator doesn't have process_query() method")
            print(f"  Available methods: {[m for m in dir(orch) if not m.startswith('_')]}")
            return False
        
        test_query = "What is ATP?"
        print(f"  Sending query: '{test_query}'")
        
        result = orch.process_query(test_query)
        
        print(f"  ✓ Query processed")
        print(f"    Answer: {result.answer[:100] if result.answer else '(empty)'}...")
        print(f"    Confidence: {result.confidence:.2f}")
        print(f"    Engine: {result.engine_name}")
        print(f"    Latency: {result.total_latency_ms:.2f}ms")
        
        return True
        
    except NotImplementedError:
        print("  ⚠ Query method not implemented yet")
        return False
    except Exception as e:
        print(f"  ✗ Query failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_engine_availability(orch):
    """Test if engines are available."""
    print("\n" + "="*70)
    print("TEST 4: Engine Availability")
    print("="*70)
    
    if not orch:
        print("  ⊗ Skipped (no orchestrator)")
        return False
    
    try:
        if not hasattr(orch, 'engines'):
            print("  ⚠ Orchestrator doesn't have engines attribute")
            return False
        
        for engine_name, engine in orch.engines.items():
            print(f"  Engine: {engine_name}")
            
            # Check if engine has is_available method
            if hasattr(engine, 'is_available'):
                available = engine.is_available()
                status = "✓" if available else "✗"
                print(f"    {status} Available: {available}")
            
            # Check if engine has stats
            if hasattr(engine, 'get_stats'):
                stats = engine.get_stats()
                print(f"    Stats: {stats}")
        
        return True
        
    except Exception as e:
        print(f"  ✗ Engine check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("KITBASH FACTORY TEST SUITE")
    print("="*70)
    
    results = {}
    
    # Test 1: Imports
    results["imports"] = test_imports()
    
    if not results["imports"]:
        print("\n✗ Import test failed - cannot continue")
        return False
    
    # Test 2: Factory creation
    orch = test_factory_creation()
    results["factory"] = orch is not None
    
    if orch:
        # Test 3: Engine availability
        results["engines"] = test_engine_availability(orch)
        
        # Test 4: Basic query (if available)
        results["query"] = test_basic_query(orch)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    for test_name, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {test_name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✓ All tests passed!")
        return True
    else:
        print("\n✗ Some tests failed")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
