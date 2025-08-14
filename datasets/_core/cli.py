"""
CLI commands for dataset management in sqlite-llm-bench.

This module provides command implementations for the dataset management CLI,
including listing, validation, building, and version management operations.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .registry import DatasetRegistry, DatasetConfig


def list_command(args):
    """List all available datasets and versions."""
    registry = DatasetRegistry(Path(args.datasets_root))
    datasets = registry.list_datasets()

    if not datasets:
        print("No datasets found.")
        return

    print("📊 Available Datasets")
    print("=" * 60)

    for dataset_name, variants in datasets.items():
        print(f"\n🗂️  {dataset_name.upper()}")

        for variant, versions in variants.items():
            print(f"   📁 {variant}")

            if not versions:
                print("      (no versions)")
                continue

            for version in sorted(versions, reverse=True):
                if version == "latest":
                    # Get actual version of latest
                    config = DatasetConfig(name=dataset_name, variant=variant, version="latest")
                    db_path = registry.get_dataset_path(config)
                    metadata = registry.get_dataset_metadata(db_path)
                    if metadata:
                        print(f"      📌 latest → v{metadata.version}")
                    else:
                        print(f"      📌 latest (no metadata)")
                else:
                    print(f"      📦 v{version}")

    print(f"\nUse 'python datasets/scripts/manage.py show <dataset> <variant>' for details")


def show_command(args):
    """Show detailed information for a specific dataset."""
    registry = DatasetRegistry(Path(args.datasets_root))
    config = DatasetConfig(name=args.dataset, variant=args.variant, version=args.version)
    db_path = registry.get_dataset_path(config)

    if not db_path.exists():
        print(f"❌ Dataset not found: {db_path}")
        available = registry.list_datasets()
        if args.dataset in available:
            print(f"Available variants for {args.dataset}: {list(available[args.dataset].keys())}")
        return

    metadata = registry.get_dataset_metadata(db_path)

    print(f"📋 Dataset Information")
    print("=" * 60)
    print(f"Path: {db_path}")

    if metadata:
        print(f"Name: {metadata.dataset_name}")
        print(f"Variant: {metadata.variant}")
        print(f"Version: {metadata.version}")
        print(f"Created: {metadata.created_at[:19].replace('T', ' ')}")
        print(f"Schema: v{metadata.schema_version}")
        print(f"Description: {metadata.description}")
        if metadata.parent_version:
            print(f"Parent: v{metadata.parent_version}")
        if metadata.breaking_changes:
            print("⚠️  Contains breaking changes")
    else:
        print("⚠️  No metadata found (legacy database)")

    # Show database statistics
    print(f"\n📈 Database Statistics")
    print("-" * 30)

    try:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            # File size
            size_mb = db_path.stat().st_size / (1024 * 1024)
            print(f"File size: {size_mb:.1f} MB")

            # Table counts
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            print(f"Tables: {len(tables)}")

            # Question count if available
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM questions")
                question_count = cursor.fetchone()[0]
                print(f"Questions: {question_count}")
            except sqlite3.OperationalError:
                pass

            # WikiSQL table count if available
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM wikisql_tables")
                table_count = cursor.fetchone()[0]
                print(f"WikiSQL Tables: {table_count}")
            except sqlite3.OperationalError:
                pass

    except Exception as e:
        print(f"Could not read database statistics: {e}")


def validate_command(args):
    """Validate dataset integrity and compatibility."""
    registry = DatasetRegistry(Path(args.datasets_root))
    config = DatasetConfig(name=args.dataset, variant=args.variant, version=args.version)
    db_path = registry.get_dataset_path(config)

    if not db_path.exists():
        print(f"❌ Dataset not found: {db_path}")
        return

    print(f"🔍 Validating {args.dataset}-{args.variant} v{args.version}")
    print("-" * 50)

    # Check metadata
    metadata = registry.get_dataset_metadata(db_path)
    if metadata:
        print(f"✅ Metadata found: v{metadata.version}")
    else:
        print("❌ No metadata found")
        return

    # Schema compatibility
    compatible = registry.validate_version_compatibility(db_path, args.min_schema_version)
    if compatible:
        print(f"✅ Schema compatible (v{metadata.schema_version} >= {args.min_schema_version})")
    else:
        print(f"❌ Schema incompatible (v{metadata.schema_version} < {args.min_schema_version})")

    # Checksum validation
    if args.verify_checksum:
        print("🔐 Verifying checksum...")
        current_checksum = registry.compute_database_checksum(db_path)
        if current_checksum == metadata.checksum:
            print("✅ Checksum valid")
        else:
            print("❌ Checksum mismatch - file may be corrupted")
            print(f"Expected: {metadata.checksum[:16]}...")
            print(f"Actual:   {current_checksum[:16]}...")

    # Database structure validation
    try:
        import sqlite3
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            required_tables = ["questions", "wikisql_tables", "dataset_metadata"]
            missing_tables = [t for t in required_tables if t not in tables]

            if missing_tables:
                print(f"❌ Missing required tables: {missing_tables}")
            else:
                print("✅ Required tables present")

    except Exception as e:
        print(f"❌ Database validation failed: {e}")


def build_command(args):
    """Build a new dataset version."""
    if args.dataset == "wikisql":
        script_path = Path(__file__).parent.parent / "scripts" / "build_wikisql_top500.py"
    else:
        print(f"❌ Build command not yet implemented for dataset: {args.dataset}")
        return

    if not script_path.exists():
        print(f"❌ Build script not found: {script_path}")
        return

    # Build command arguments
    cmd = [sys.executable, str(script_path)]

    if args.version:
        cmd.extend(["--version", args.version])
    if args.k:
        cmd.extend(["--k", str(args.k)])
    if args.archive_existing:
        cmd.append("--archive-existing")
    if args.keep_source_data:
        cmd.append("--keep-source-data")

    print(f"🔨 Building {args.dataset}-{args.variant}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)

    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ Build completed successfully")

        # Show the new version info
        print(f"\n📋 New Version Created")
        registry = DatasetRegistry(Path(args.datasets_root))
        config = DatasetConfig(name=args.dataset, variant=args.variant, version="latest")
        db_path = registry.get_dataset_path(config)
        metadata = registry.get_dataset_metadata(db_path)
        if metadata:
            print(f"Version: {metadata.version}")
            print(f"Path: {db_path}")

    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed with exit code {e.returncode}")
        sys.exit(1)


def archive_command(args):
    """Archive current version before making changes."""
    registry = DatasetRegistry(Path(args.datasets_root))
    config = DatasetConfig(name=args.dataset, variant=args.variant, version="latest")
    current_path = registry.get_dataset_path(config)

    if not current_path.exists():
        print(f"❌ Current version not found: {current_path}")
        return

    metadata = registry.get_dataset_metadata(current_path)
    if not metadata:
        print(f"⚠️  Cannot archive: no metadata found in {current_path}")
        print("Use --force to archive anyway (not recommended)")
        if not args.force:
            return

        # Create minimal metadata for legacy database
        from .registry import DatasetVersion
        metadata = DatasetVersion(
            dataset_name=args.dataset,
            variant=args.variant,
            version="1.0.0",  # Default for legacy
            created_at=datetime.now().isoformat(),
            schema_version=1,
            description="Legacy version (auto-archived)",
            checksum=registry.compute_database_checksum(current_path)
        )

    try:
        archive_path = registry.create_version_archive(current_path, args.new_version)
        print(f"✅ Archived v{metadata.version} to {archive_path}")
    except Exception as e:
        print(f"❌ Archive failed: {e}")


def release_command(args):
    """Create a new release by archiving current and updating metadata."""
    registry = DatasetRegistry(Path(args.datasets_root))

    # First archive current version
    print(f"📦 Creating release v{args.version}")

    config = DatasetConfig(name=args.dataset, variant=args.variant)
    current_path = registry.get_dataset_path(config)

    if not current_path.exists():
        print(f"❌ Current database not found: {current_path}")
        return

    # Get current metadata to determine if this is a breaking change
    current_metadata = registry.get_dataset_metadata(current_path)
    parent_version = current_metadata.version if current_metadata else None

    # Determine if breaking change based on version number
    breaking_changes = False
    if parent_version:
        parent_major = int(parent_version.split('.')[0])
        new_major = int(args.version.split('.')[0])
        breaking_changes = new_major > parent_major

    # Archive current version
    if current_metadata:
        archive_path = registry.create_version_archive(current_path, args.version)
        print(f"✅ Archived v{parent_version} to {archive_path}")

    # Update metadata in current database
    checksum = registry.compute_database_checksum(current_path)
    from .registry import DatasetVersion
    new_metadata = DatasetVersion(
        dataset_name=args.dataset,
        variant=args.variant,
        version=args.version,
        created_at=datetime.now().isoformat(),
        schema_version=1,
        description=args.description,
        checksum=checksum,
        parent_version=parent_version,
        breaking_changes=breaking_changes
    )

    registry.register_dataset(current_path, new_metadata)

    print(f"✅ Created release v{args.version}")
    if breaking_changes:
        print("⚠️  This is a MAJOR version (breaking changes)")

    # Update changelog if it exists
    changelog_path = current_path.parent / "CHANGELOG.md"
    if changelog_path.exists() and args.update_changelog:
        update_changelog(changelog_path, args.version, args.description, breaking_changes)
        print(f"✅ Updated {changelog_path}")


def update_changelog(changelog_path: Path, version: str, description: str, breaking_changes: bool):
    """Update CHANGELOG.md with new version entry."""
    content = changelog_path.read_text()

    # Find the [Unreleased] section
    unreleased_marker = "## [Unreleased]"
    if unreleased_marker not in content:
        return

    # Create new version entry
    date_str = datetime.now().strftime("%Y-%m-%d")
    change_type = "### Changed" if breaking_changes else "### Added"
    new_entry = f"""## [{version}] - {date_str}

{change_type}
- {description}

"""

    # Insert after [Unreleased] section
    updated_content = content.replace(
        unreleased_marker + "\n\n",
        unreleased_marker + "\n\n" + new_entry
    )

    changelog_path.write_text(updated_content)
