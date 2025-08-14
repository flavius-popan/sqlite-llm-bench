#!/usr/bin/env python3
"""
Demonstration of the sqlite-llm-bench dataset versioning system.

This script showcases the key benefits of the metadata-driven versioning approach:
- Version-agnostic loading (defaults to latest)
- Explicit version pinning for reproducibility
- Automatic version discovery and validation
- Content integrity verification

Usage:
  python datasets/scripts/demo.py
"""

import sys
from pathlib import Path

# Add the datasets module to Python path
datasets_root = Path(__file__).parent.parent
sys.path.insert(0, str(datasets_root.parent))

from datasets import load_dataset, DatasetRegistry, DatasetConfig


def demo_basic_usage():
    """Demonstrate basic version-agnostic dataset loading."""
    print("🚀 Basic Usage: Load Latest Version")
    print("-" * 50)

    # This is how users will typically load datasets - simple and version-agnostic
    loader = load_dataset("wikisql", "top500")

    print(f"Dataset: {loader.metadata.dataset_name}-{loader.metadata.variant}")
    print(f"Version: {loader.metadata.version} (automatically resolved to latest)")
    print(f"Created: {loader.metadata.created_at[:19].replace('T', ' ')}")

    questions = loader.get_questions(limit=3)
    print(f"Questions loaded: {len(questions)}")
    print(f"First question: {questions[0]['question'][:80]}...")


def demo_reproducible_research():
    """Demonstrate explicit version pinning for reproducible research."""
    print("\n🔬 Reproducible Research: Pin Specific Version")
    print("-" * 50)

    # For research papers, pin exact version for reproducibility
    registry = DatasetRegistry()
    available_versions = registry.get_available_versions("wikisql", "top500")

    if available_versions:
        pinned_version = available_versions[0]  # Use oldest available

        loader = load_dataset("wikisql", "top500", version=pinned_version)

        print(f"Pinned version: {pinned_version}")
        print(f"Database path: {loader.db_path}")
        print(f"Checksum: {loader.metadata.checksum[:16]}...")
        print("✅ Results from this version will be reproducible")

        # In research, you'd log this version info
        research_metadata = {
            "dataset": "wikisql-top500",
            "version": pinned_version,
            "checksum": loader.metadata.checksum,
            "path": str(loader.db_path)
        }
        print(f"Research metadata: {research_metadata}")
    else:
        print("No archived versions available for demonstration")


def demo_version_discovery():
    """Demonstrate automatic version discovery and comparison."""
    print("\n🔍 Version Discovery: Explore Available Versions")
    print("-" * 50)

    registry = DatasetRegistry()
    datasets = registry.list_datasets()

    for dataset_name, variants in datasets.items():
        print(f"📊 {dataset_name.upper()}")

        for variant, versions in variants.items():
            print(f"  📁 {variant}")

            for version in versions:
                if version == "latest":
                    config = DatasetConfig(name=dataset_name, variant=variant)
                    db_path = registry.get_dataset_path(config)
                    metadata = registry.get_dataset_metadata(db_path)
                    if metadata:
                        print(f"    📌 latest → v{metadata.version}")
                    else:
                        print(f"    📌 latest (no metadata)")
                else:
                    print(f"    📦 v{version}")

    # Show version comparison
    if "wikisql" in datasets and len(datasets["wikisql"].get("top500", [])) > 1:
        latest_loader = load_dataset("wikisql", "top500", "latest")
        oldest_version = registry.get_available_versions("wikisql", "top500")[0]
        oldest_loader = load_dataset("wikisql", "top500", oldest_version)

        print(f"\n📈 Version Comparison:")
        print(f"  Latest v{latest_loader.metadata.version}: {latest_loader.metadata.created_at[:10]}")
        print(f"  Oldest v{oldest_loader.metadata.version}: {oldest_loader.metadata.created_at[:10]}")


def demo_integrity_validation():
    """Demonstrate dataset integrity and compatibility validation."""
    print("\n🔐 Integrity Validation: Ensure Dataset Quality")
    print("-" * 50)

    registry = DatasetRegistry()
    config = DatasetConfig(name="wikisql", variant="top500", version="latest")
    db_path = registry.get_dataset_path(config)

    if not db_path.exists():
        print("❌ No WikiSQL dataset found for validation demo")
        return

    # Metadata validation
    metadata = registry.get_dataset_metadata(db_path)
    if metadata:
        print(f"✅ Metadata present: v{metadata.version}")
    else:
        print("❌ No metadata found")
        return

    # Schema compatibility
    compatible = registry.validate_version_compatibility(db_path, min_schema_version=1)
    print(f"✅ Schema compatibility: {'compatible' if compatible else 'incompatible'}")

    # Content integrity
    stored_checksum = metadata.checksum
    computed_checksum = registry.compute_database_checksum(db_path)
    integrity_valid = stored_checksum == computed_checksum

    print(f"✅ Content integrity: {'valid' if integrity_valid else 'corrupted'}")
    if integrity_valid:
        print(f"   Checksum: {stored_checksum[:16]}...")
    else:
        print(f"   Expected: {stored_checksum[:16]}...")
        print(f"   Actual:   {computed_checksum[:16]}...")


def demo_evaluation_workflow():
    """Demonstrate typical evaluation workflow with versioning."""
    print("\n⚡ Evaluation Workflow: Real-World Usage")
    print("-" * 50)

    # Typical evaluation script pattern
    dataset_config = DatasetConfig(
        name="wikisql",
        variant="top500",
        version="latest"  # Or pin specific version for reproducibility
    )

    print(f"Configuration: {dataset_config.name}-{dataset_config.variant} v{dataset_config.version}")

    # Load with validation
    registry = DatasetRegistry()
    db_path = registry.get_dataset_path(dataset_config)

    if not db_path.exists():
        print("❌ Dataset not available for workflow demo")
        return

    if not registry.validate_version_compatibility(db_path):
        print("❌ Dataset version incompatible - evaluation would fail")
        return

    loader = load_dataset(dataset_config.name, dataset_config.variant, dataset_config.version)

    # Evaluation would log this metadata
    eval_metadata = {
        "dataset_name": loader.metadata.dataset_name,
        "dataset_variant": loader.metadata.variant,
        "dataset_version": loader.metadata.version,
        "dataset_checksum": loader.metadata.checksum,
        "dataset_created": loader.metadata.created_at,
        "questions_evaluated": len(loader.get_questions(limit=5))
    }

    print("✅ Evaluation metadata for logging:")
    for key, value in eval_metadata.items():
        print(f"   {key}: {value}")

    # This metadata would be included in evaluation JSONL output
    print("\n💾 This metadata gets logged in evaluation results for full traceability")


def main():
    """Run all demonstrations."""
    print("🎯 SQLite LLM Bench: Dataset Versioning System Demo")
    print("=" * 70)

    try:
        demo_basic_usage()
        demo_reproducible_research()
        demo_version_discovery()
        demo_integrity_validation()
        demo_evaluation_workflow()

        print("\n" + "=" * 70)
        print("✅ Versioning system successfully demonstrated!")
        print("\n📚 Key Benefits:")
        print("   • Default to latest for ease of use")
        print("   • Pin versions for reproducible research")
        print("   • Automatic integrity validation")
        print("   • Version discovery and comparison")
        print("   • Future-proof evaluation logging")

        print("\n📖 Documentation:")
        print("   VERSIONING.md - Complete versioning guide")
        print("   datasets/wikisql/CHANGELOG.md - Version history")

        print("\n🛠️  CLI Tools:")
        print("   python datasets/scripts/manage.py list")
        print("   python datasets/scripts/manage.py show wikisql top500")
        print("   python datasets/scripts/manage.py validate wikisql top500")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("Make sure to build a dataset first:")
        print("   python datasets/scripts/build_wikisql_top500.py --k 10")


if __name__ == "__main__":
    main()
