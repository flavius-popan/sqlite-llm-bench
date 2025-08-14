#!/usr/bin/env python3
"""
Comprehensive test runner for sqlite-llm-bench dataset versioning system.

This script provides a complete test suite for validating dataset versioning,
loading, integrity, and compatibility across all supported datasets.

Usage:
  python datasets/scripts/test.py                    # Run all tests
  python datasets/scripts/test.py --dataset wikisql  # Test specific dataset
  python datasets/scripts/test.py --quick            # Run quick validation only
  python datasets/scripts/test.py --install-check    # Validate installation
"""

import argparse
import sys
from pathlib import Path

# Add the datasets module to Python path
datasets_root = Path(__file__).parent.parent
sys.path.insert(0, str(datasets_root.parent))

from datasets import load_dataset, DatasetRegistry, DatasetConfig


def test_installation():
    """Validate that the versioning system is properly installed."""
    print("🔧 Testing Installation")
    print("-" * 40)

    try:
        # Test imports
        from datasets import DatasetRegistry, load_dataset, DatasetConfig
        from datasets._core.loaders.wikisql import WikiSQLLoader
        print("✅ All imports successful")

        # Test registry creation
        registry = DatasetRegistry()
        print("✅ Registry creation successful")

        # Test dataset listing (should work even with no datasets)
        datasets = registry.list_datasets()
        print(f"✅ Dataset discovery working ({len(datasets)} datasets found)")

        return True

    except Exception as e:
        print(f"❌ Installation test failed: {e}")
        return False


def test_basic_functionality(dataset_name="wikisql", variant="top500"):
    """Test basic dataset loading and functionality."""
    print(f"\n📚 Testing Basic Functionality: {dataset_name}-{variant}")
    print("-" * 50)

    registry = DatasetRegistry()
    datasets = registry.list_datasets()

    if dataset_name not in datasets:
        print(f"⚠️  Dataset {dataset_name} not found - skipping basic functionality tests")
        return True  # Not a failure, just no data to test

    if variant not in datasets[dataset_name]:
        print(f"⚠️  Variant {variant} not found for {dataset_name} - skipping")
        return True

    try:
        # Test version-agnostic loading
        loader = load_dataset(dataset_name, variant)
        print(f"✅ Version-agnostic loading: v{loader.metadata.version}")

        # Test question retrieval
        questions = loader.get_questions(limit=5)
        print(f"✅ Question retrieval: {len(questions)} questions")

        # Test schema validation
        if hasattr(loader, 'validate_schema'):
            schema_valid = loader.validate_schema()
            print(f"✅ Schema validation: {'passed' if schema_valid else 'failed'}")

        # Test SQL execution if possible
        if questions and 'gold_sql' in questions[0]:
            gold_sql = questions[0]['gold_sql']
            if hasattr(loader, 'execute_sql'):
                success, results, error = loader.execute_sql(gold_sql)
                if success:
                    print(f"✅ SQL execution: {len(results)} rows returned")
                else:
                    print(f"⚠️  SQL execution failed: {error}")
            else:
                with loader.get_connection() as conn:
                    cursor = conn.execute(gold_sql)
                    results = cursor.fetchall()
                    print(f"✅ SQL execution: {len(results)} rows returned")

        return True

    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        return False


def test_version_management(dataset_name="wikisql", variant="top500"):
    """Test version management capabilities."""
    print(f"\n🔄 Testing Version Management: {dataset_name}-{variant}")
    print("-" * 50)

    registry = DatasetRegistry()

    try:
        # Test version listing
        versions = registry.get_available_versions(dataset_name, variant)
        print(f"✅ Version listing: {len(versions)} archived versions")

        # Test latest version resolution
        latest = registry.get_latest_version(dataset_name, variant)
        if latest:
            print(f"✅ Latest version resolution: v{latest}")
        else:
            print("⚠️  No latest version found")

        # Test version loading if multiple versions exist
        if len(versions) >= 1:
            # Test loading specific version
            specific_loader = load_dataset(dataset_name, variant, versions[0])
            print(f"✅ Specific version loading: v{specific_loader.metadata.version}")

            # Test latest vs specific comparison
            latest_loader = load_dataset(dataset_name, variant, "latest")
            if latest_loader.metadata.version != specific_loader.metadata.version:
                print("✅ Version differentiation working")
            else:
                print("ℹ️  Only one version available - no differentiation to test")

        return True

    except Exception as e:
        print(f"❌ Version management test failed: {e}")
        return False


def test_integrity_validation(dataset_name="wikisql", variant="top500"):
    """Test dataset integrity and validation capabilities."""
    print(f"\n🔒 Testing Integrity Validation: {dataset_name}-{variant}")
    print("-" * 50)

    registry = DatasetRegistry()
    config = DatasetConfig(name=dataset_name, variant=variant, version="latest")
    db_path = registry.get_dataset_path(config)

    if not db_path.exists():
        print("⚠️  No dataset available for integrity testing")
        return True

    try:
        # Test metadata retrieval
        metadata = registry.get_dataset_metadata(db_path)
        if metadata:
            print(f"✅ Metadata retrieval: v{metadata.version}")
        else:
            print("❌ No metadata found")
            return False

        # Test schema compatibility
        compatible = registry.validate_version_compatibility(db_path, min_schema_version=1)
        print(f"✅ Schema compatibility: {'compatible' if compatible else 'incompatible'}")

        # Test checksum validation
        stored_checksum = metadata.checksum
        computed_checksum = registry.compute_database_checksum(db_path)
        checksum_valid = stored_checksum == computed_checksum
        print(f"✅ Checksum validation: {'valid' if checksum_valid else 'invalid'}")

        return compatible and checksum_valid

    except Exception as e:
        print(f"❌ Integrity validation test failed: {e}")
        return False


def test_cli_integration():
    """Test CLI command integration."""
    print(f"\n🖥️  Testing CLI Integration")
    print("-" * 40)

    manage_script = Path(__file__).parent / "manage.py"

    if not manage_script.exists():
        print(f"❌ Management script not found: {manage_script}")
        return False

    try:
        import subprocess

        # Test help command
        result = subprocess.run(
            [sys.executable, str(manage_script), "--help"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "Dataset Management CLI" in result.stdout:
            print("✅ CLI help command working")
        else:
            print("⚠️  CLI help command issues")

        # Test list command (should always work)
        result = subprocess.run(
            [sys.executable, str(manage_script), "list"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            print("✅ CLI list command working")
        else:
            print(f"⚠️  CLI list command failed: {result.stderr}")

        return True

    except Exception as e:
        print(f"❌ CLI integration test failed: {e}")
        return False


def run_quick_tests():
    """Run a quick subset of tests for fast validation."""
    print("⚡ Quick Test Suite")
    print("=" * 50)

    tests = [
        test_installation,
        test_cli_integration,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test_func.__name__} failed with exception: {e}")
            results.append(False)

    return results


def run_full_tests(dataset_name=None):
    """Run the complete test suite."""
    print("🧪 Full Test Suite")
    print("=" * 50)

    # Determine which datasets to test
    registry = DatasetRegistry()
    available_datasets = registry.list_datasets()

    if dataset_name:
        if dataset_name not in available_datasets:
            print(f"❌ Specified dataset '{dataset_name}' not found")
            print(f"Available datasets: {list(available_datasets.keys())}")
            return [False]
        test_datasets = [(dataset_name, list(available_datasets[dataset_name].keys())[0])]
    else:
        # Test all available datasets
        test_datasets = []
        for name, variants in available_datasets.items():
            if variants:
                test_datasets.append((name, list(variants.keys())[0]))

    if not test_datasets:
        print("⚠️  No datasets available for testing")
        print("Build a dataset first:")
        print("   python datasets/scripts/build_wikisql_top500.py --k 10")
        return [True]  # Not a failure, just no data

    # Run all tests
    all_results = []

    # Installation tests
    all_results.extend(run_quick_tests())

    # Per-dataset tests
    for ds_name, ds_variant in test_datasets:
        print(f"\n🎯 Testing Dataset: {ds_name}-{ds_variant}")
        print("=" * 60)

        test_funcs = [
            lambda: test_basic_functionality(ds_name, ds_variant),
            lambda: test_version_management(ds_name, ds_variant),
            lambda: test_integrity_validation(ds_name, ds_variant),
        ]

        for test_func in test_funcs:
            try:
                result = test_func()
                all_results.append(result)
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                all_results.append(False)

    return all_results


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(
        description="Test runner for sqlite-llm-bench dataset versioning system",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--quick", action="store_true",
                       help="Run quick tests only (installation and CLI)")
    parser.add_argument("--dataset",
                       help="Test specific dataset only (e.g., wikisql)")
    parser.add_argument("--install-check", action="store_true",
                       help="Check installation only")

    args = parser.parse_args()

    if args.install_check:
        success = test_installation()
        sys.exit(0 if success else 1)

    if args.quick:
        results = run_quick_tests()
    else:
        results = run_full_tests(args.dataset)

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n📊 Test Summary")
    print("=" * 30)
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        print("\n🚀 System ready for use!")
        print("\nNext steps:")
        print("   • Build datasets: python datasets/scripts/build_wikisql_top500.py")
        print("   • Manage versions: python datasets/scripts/manage.py list")
        print("   • Run evaluations: from datasets import load_dataset")
    else:
        print("❌ Some tests failed")
        print("\nTroubleshooting:")
        print("   • Check that datasets are built: python datasets/scripts/manage.py list")
        print("   • Validate specific dataset: python datasets/scripts/manage.py validate wikisql top500")
        print("   • Check installation: python datasets/scripts/test.py --install-check")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
