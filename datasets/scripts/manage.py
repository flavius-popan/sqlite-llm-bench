#!/usr/bin/env python3
"""
Dataset Management CLI for sqlite-llm-bench.

A unified command-line interface for managing dataset versions, building datasets,
and validating integrity across all supported benchmark types.

Usage examples:
  python datasets/scripts/manage.py list
  python datasets/scripts/manage.py show wikisql top500
  python datasets/scripts/manage.py validate wikisql top500 --verify-checksum
  python datasets/scripts/manage.py build wikisql top500 --version 1.1.0 --archive-existing
  python datasets/scripts/manage.py archive wikisql top500 1.1.0
  python datasets/scripts/manage.py release wikisql top500 1.2.0 "Added 50 new high-complexity questions"
"""

import argparse
import sys
from pathlib import Path

# Add the datasets module to Python path
datasets_root = Path(__file__).parent.parent
sys.path.insert(0, str(datasets_root.parent))

from datasets._core.cli import (
    list_command,
    show_command,
    validate_command,
    build_command,
    archive_command,
    release_command
)


def main():
    """Main CLI interface for dataset management."""
    parser = argparse.ArgumentParser(
        description="Manage datasets and versions for sqlite-llm-bench",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list                                    # List all datasets and versions
  %(prog)s show wikisql top500                     # Show dataset information
  %(prog)s show wikisql top500 --version 1.0.0    # Show specific version
  %(prog)s validate wikisql top500 --verify-checksum  # Validate with checksum
  %(prog)s build wikisql top500 --version 1.1.0 --archive-existing  # Build new version
  %(prog)s archive wikisql top500 1.1.0           # Archive current version
  %(prog)s release wikisql top500 1.2.0 "Bug fixes and improvements"  # Create release

Dataset Types:
  wikisql       Single-table SQL queries with difficulty ranking
  spider1       Multi-table cross-domain queries (future)
  spider2_lite  Enterprise-scale multi-table queries (future)
  bird          Real-world database questions (future)

Version Format:
  Semantic versioning (MAJOR.MINOR.PATCH):
  - MAJOR: Breaking changes (schema, evaluation methodology)
  - MINOR: Backward-compatible additions (more questions, metadata)
  - PATCH: Bug fixes and corrections
        """
    )

    parser.add_argument("--datasets-root", default="datasets",
                       help="Root directory for datasets (default: datasets)")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # List command
    list_parser = subparsers.add_parser(
        "list",
        help="List available datasets and versions",
        description="Show all datasets, variants, and available versions"
    )

    # Show command
    show_parser = subparsers.add_parser(
        "show",
        help="Show dataset information",
        description="Display detailed information about a specific dataset version"
    )
    show_parser.add_argument("dataset", help="Dataset name (e.g., wikisql)")
    show_parser.add_argument("variant", help="Dataset variant (e.g., top500)")
    show_parser.add_argument("--version", default="latest",
                            help="Version to show (default: latest)")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate dataset integrity",
        description="Check dataset integrity, compatibility, and optional checksum verification"
    )
    validate_parser.add_argument("dataset", help="Dataset name")
    validate_parser.add_argument("variant", help="Dataset variant")
    validate_parser.add_argument("--version", default="latest",
                                 help="Version to validate (default: latest)")
    validate_parser.add_argument("--min-schema-version", type=int, default=1,
                                help="Minimum required schema version (default: 1)")
    validate_parser.add_argument("--verify-checksum", action="store_true",
                                help="Verify file checksum against stored metadata")

    # Build command
    build_parser = subparsers.add_parser(
        "build",
        help="Build a new dataset version",
        description="Build a new dataset version with optional archiving of existing version"
    )
    build_parser.add_argument("dataset", help="Dataset name")
    build_parser.add_argument("variant", help="Dataset variant")
    build_parser.add_argument("--version",
                             help="Version to build (e.g., 1.1.0). If not specified, uses script default")
    build_parser.add_argument("--k", type=int,
                             help="Number of questions to select (dataset-specific)")
    build_parser.add_argument("--archive-existing", action="store_true",
                             help="Archive existing version before building new one")
    build_parser.add_argument("--keep-source-data", action="store_true",
                             help="Keep source data after processing (default: delete to save space)")

    # Archive command
    archive_parser = subparsers.add_parser(
        "archive",
        help="Archive current version",
        description="Archive the current version before making changes"
    )
    archive_parser.add_argument("dataset", help="Dataset name")
    archive_parser.add_argument("variant", help="Dataset variant")
    archive_parser.add_argument("new_version",
                               help="Version number for upcoming changes (for reference)")
    archive_parser.add_argument("--force", action="store_true",
                               help="Archive even without metadata (not recommended)")

    # Release command
    release_parser = subparsers.add_parser(
        "release",
        help="Create a new release",
        description="Create a new release by archiving current version and updating metadata"
    )
    release_parser.add_argument("dataset", help="Dataset name")
    release_parser.add_argument("variant", help="Dataset variant")
    release_parser.add_argument("version", help="New version number (semantic versioning)")
    release_parser.add_argument("description", help="Release description for changelog")
    release_parser.add_argument("--update-changelog", action="store_true",
                               help="Automatically update CHANGELOG.md with new version")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Dispatch to appropriate command
    try:
        if args.command == "list":
            list_command(args)
        elif args.command == "show":
            show_command(args)
        elif args.command == "validate":
            validate_command(args)
        elif args.command == "build":
            build_command(args)
        elif args.command == "archive":
            archive_command(args)
        elif args.command == "release":
            release_command(args)
        else:
            parser.print_help()

    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
