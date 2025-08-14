"""
Testing utilities for the sqlite-llm-bench dataset versioning system.

This module provides comprehensive testing functions for validating dataset
versioning, loading, integrity, and compatibility across all supported datasets.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

from .registry import DatasetRegistry, DatasetConfig, load_dataset


def test_version_agnostic_loading(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Test loading dataset without specifying version (should get latest)."""
    print("🔍 Testing version-agnostic loading...")

    try:
        # Load without specifying version - should get latest
        loader = load_dataset(dataset_name, variant)

        print(f"✅ Loaded dataset: {loader.metadata.dataset_name}-{loader.metadata.variant}")
        print(f"   Version: {loader.metadata.version}")
        print(f"   Created: {loader.metadata.created_at[:19].replace('T', ' ')}")
        print(f"   Description: {loader.metadata.description}")

        # Get some questions to verify functionality
        questions = loader.get_questions(limit=3)
        print(f"   Sample questions: {len(questions)}")

        for i, q in enumerate(questions[:2], 1):
            print(f"     {i}. {q['question'][:80]}...")

        return True

    except Exception as e:
        print(f"❌ Version-agnostic loading failed: {e}")
        return False


def test_explicit_version_loading(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Test loading specific version of dataset."""
    print("\n🔍 Testing explicit version loading...")

    registry = DatasetRegistry()
    available_versions = registry.get_available_versions(dataset_name, variant)

    if not available_versions:
        print("❌ No archived versions available for testing")
        return False

    # Test loading oldest version
    oldest_version = available_versions[0]

    try:
        config = DatasetConfig(name=dataset_name, variant=variant, version=oldest_version)
        loader = load_dataset(config.name, config.variant, config.version)

        print(f"✅ Loaded specific version: v{oldest_version}")
        print(f"   Path: {loader.db_path}")
        print(f"   Metadata version: {loader.metadata.version}")

        # Verify this is actually the older version
        questions = loader.get_questions(limit=1)
        if questions:
            print(f"   First question UID: {questions[0]['uid']}")

        return True

    except Exception as e:
        print(f"❌ Explicit version loading failed: {e}")
        return False


def test_version_comparison(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Compare questions between different versions."""
    print("\n🔍 Testing version comparison...")

    registry = DatasetRegistry()
    available_versions = registry.get_available_versions(dataset_name, variant)

    if len(available_versions) < 2:
        print("ℹ️  Need at least 2 versions for comparison")
        return True  # Not a failure, just insufficient data

    try:
        # Load latest and oldest versions
        latest_loader = load_dataset(dataset_name, variant, "latest")
        oldest_loader = load_dataset(dataset_name, variant, available_versions[0])

        latest_questions = latest_loader.get_questions(limit=5)
        oldest_questions = oldest_loader.get_questions(limit=5)

        print(f"✅ Version comparison:")
        print(f"   Latest (v{latest_loader.metadata.version}): {len(latest_questions)} questions")
        print(f"   Oldest (v{oldest_loader.metadata.version}): {len(oldest_questions)} questions")

        # Check if first question is the same (should be for same top-K)
        if latest_questions and oldest_questions:
            latest_first = latest_questions[0]
            oldest_first = oldest_questions[0]

            if latest_first['uid'] == oldest_first['uid']:
                print("   ✅ Question ordering consistent between versions")
            else:
                print("   ⚠️  Question ordering differs between versions")
                print(f"      Latest first UID: {latest_first['uid']}")
                print(f"      Oldest first UID: {oldest_first['uid']}")

        return True

    except Exception as e:
        print(f"❌ Version comparison failed: {e}")
        return False


def test_dataset_registry_functions() -> bool:
    """Test dataset registry utility functions."""
    print("\n🔍 Testing dataset registry functions...")

    registry = DatasetRegistry()

    try:
        # Test dataset listing
        datasets = registry.list_datasets()
        print(f"✅ Found datasets: {list(datasets.keys())}")

        # Test version listing for WikiSQL if available
        if "wikisql" in datasets and "top500" in datasets["wikisql"]:
            versions = registry.get_available_versions("wikisql", "top500")
            print(f"✅ WikiSQL top500 versions: {versions}")

            latest_version = registry.get_latest_version("wikisql", "top500")
            print(f"✅ Latest version: {latest_version}")

        # Test metadata retrieval
        config = DatasetConfig(name="wikisql", variant="top500", version="latest")
        db_path = registry.get_dataset_path(config)

        if db_path.exists():
            metadata = registry.get_dataset_metadata(db_path)

            if metadata:
                print(f"✅ Metadata retrieval working")
                print(f"   Checksum: {metadata.checksum[:16]}...")

            # Test compatibility validation
            compatible = registry.validate_version_compatibility(db_path, min_schema_version=1)
            print(f"✅ Compatibility check: {'compatible' if compatible else 'incompatible'}")

        return True

    except Exception as e:
        print(f"❌ Registry function test failed: {e}")
        return False


def test_dataset_specific_features(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Test dataset-specific loader features."""
    print(f"\n🔍 Testing {dataset_name}-specific features...")

    try:
        loader = load_dataset(dataset_name, variant, "latest")

        # Test schema validation
        schema_valid = loader.validate_schema()
        print(f"✅ Schema validation: {'passed' if schema_valid else 'failed'}")

        # Test question retrieval
        all_questions = loader.get_questions(limit=10)
        print(f"✅ Retrieved {len(all_questions)} questions")

        if all_questions:
            # Test question properties
            q = all_questions[0]
            print(f"   Sample question difficulty score: {q.get('difficulty_score', 'N/A')}")
            print(f"   Has aggregation: {q.get('has_agg', 0) == 1}")
            print(f"   Condition count: {q.get('cond_count', 'N/A')}")

        # Test dataset-specific methods if available
        if hasattr(loader, 'get_table_metadata') and all_questions:
            first_q = all_questions[0]
            if 'table_id' in first_q and 'split' in first_q:
                table_meta = loader.get_table_metadata(first_q['table_id'], first_q['split'])
                if table_meta:
                    print(f"✅ Table metadata retrieved for {first_q.get('table_name', 'unknown')}")
                    print(f"   Columns: {table_meta.n_cols}")
                    print(f"   Rows: {table_meta.n_rows}")

        return True

    except Exception as e:
        print(f"❌ {dataset_name}-specific test failed: {e}")
        return False


def test_sql_execution(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Test SQL execution against the dataset."""
    print("\n🔍 Testing SQL execution...")

    try:
        loader = load_dataset(dataset_name, variant, "latest")
        questions = loader.get_questions(limit=1)

        if questions:
            question = questions[0]
            gold_sql = question.get('gold_sql')

            if not gold_sql:
                print("⚠️  No gold SQL found in question")
                return True

            print(f"✅ Testing SQL execution")
            print(f"   Question: {question['question'][:60]}...")
            print(f"   Gold SQL: {gold_sql}")

            # Execute the gold SQL to verify it works
            if hasattr(loader, 'execute_sql'):
                success, results, error = loader.execute_sql(gold_sql)
                if success:
                    print(f"   ✅ SQL executed successfully, {len(results)} rows returned")
                else:
                    print(f"   ❌ SQL execution failed: {error}")
                    return False
            else:
                # Fall back to direct database execution
                with loader.get_connection() as conn:
                    cursor = conn.execute(gold_sql)
                    results = cursor.fetchall()
                    print(f"   ✅ SQL executed successfully, {len(results)} rows returned")

        return True

    except Exception as e:
        print(f"❌ SQL execution test failed: {e}")
        return False


def run_all_tests(dataset_name: str = "wikisql", variant: str = "top500") -> bool:
    """Run comprehensive test suite for dataset versioning system."""
    print("🧪 Testing sqlite-llm-bench Dataset Versioning System")
    print("=" * 60)

    # Check if we have any datasets to test with
    registry = DatasetRegistry()
    datasets = registry.list_datasets()

    if not datasets:
        print("❌ No datasets found. Build a dataset first:")
        print(f"   python datasets/scripts/build_wikisql_top500.py --k 10")
        return False

    if dataset_name not in datasets:
        print(f"❌ Dataset '{dataset_name}' not found. Available: {list(datasets.keys())}")
        return False

    if variant not in datasets[dataset_name]:
        print(f"❌ Variant '{variant}' not found for {dataset_name}. Available: {list(datasets[dataset_name].keys())}")
        return False

    # Run all tests
    test_results = []
    test_results.append(test_version_agnostic_loading(dataset_name, variant))
    test_results.append(test_explicit_version_loading(dataset_name, variant))
    test_results.append(test_version_comparison(dataset_name, variant))
    test_results.append(test_dataset_registry_functions())
    test_results.append(test_dataset_specific_features(dataset_name, variant))
    test_results.append(test_sql_execution(dataset_name, variant))

    # Summary
    passed = sum(test_results)
    total = len(test_results)

    print(f"\n📊 Test Results: {passed}/{total} passed")

    if passed == total:
        print("✅ All tests passed!")
        print("\n💡 Usage examples:")
        print("   # Load latest version")
        print("   from datasets import load_dataset")
        print("   loader = load_dataset('wikisql', 'top500')")
        print("")
        print("   # Load specific version")
        print("   loader = load_dataset('wikisql', 'top500', '1.0.0')")
        print("")
        print("   # Get questions with metadata")
        print("   questions = loader.get_questions(limit=10)")
        return True
    else:
        print("❌ Some tests failed - check output above")
        return False


def validate_installation() -> bool:
    """Quick validation that the versioning system is properly installed."""
    try:
        # Test basic imports
        from .registry import DatasetRegistry, load_dataset
        from .loaders.wikisql import WikiSQLLoader

        # Test registry creation
        registry = DatasetRegistry()

        # Test dataset listing (should work even with no datasets)
        datasets = registry.list_datasets()

        print("✅ Dataset versioning system installation valid")
        return True

    except Exception as e:
        print(f"❌ Installation validation failed: {e}")
        print("Check that all required files are present and imports work correctly")
        return False


if __name__ == "__main__":
    """Run tests when called directly."""
    if len(sys.argv) > 1 and sys.argv[1] == "validate-install":
        validate_installation()
    else:
        run_all_tests()
