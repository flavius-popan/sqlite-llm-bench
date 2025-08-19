#!/usr/bin/env python3
"""
Basic CLI setup for evaluating language models on SQL generation tasks.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main entry point for the evaluation script."""
    parser = argparse.ArgumentParser(
        description="Evaluate language models on SQL generation tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct file mode
  python eval.py --questions questions.jsonl --db mydata.db --model llama3:8b
  python eval.py --questions questions.jsonl --db databases/ --model gpt-4

  # Dataset mode
  python eval.py hello_world --model qwen/qwen3-30b-a3b-2507
  python eval.py hello_world --model openai/gpt-oss-20b
        """
    )

    parser.add_argument(
        '--questions',
        help='Path to questions.jsonl file'
    )

    parser.add_argument(
        '--db',
        help='Path to database file or directory'
    )

    parser.add_argument(
        'dataset',
        nargs='?',
        help='Dataset name (e.g., hello_world)'
    )

    parser.add_argument(
        '--model', '-m',
        required=True,
        help='Model name (e.g., qwen/qwen3-30b-a3b-2507)'
    )

    args = parser.parse_args()
    if args.questions and args.db:
        questions_file = Path(args.questions)
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        db_path = Path(args.db)
        if not db_path.exists():
            print(f"Error: Database path not found at {db_path}")
            sys.exit(1)

        print(f"Questions: {questions_file}")
        print(f"Database: {db_path}")
        print(f"Model: {args.model}")

    elif args.dataset:
        dataset_path = Path(f'datasets/{args.dataset}')
        if not dataset_path.exists():
            print(f"Error: Dataset '{args.dataset}' not found at {dataset_path}")
            sys.exit(1)

        questions_file = dataset_path / 'questions.jsonl'
        if not questions_file.exists():
            print(f"Error: Questions file not found at {questions_file}")
            sys.exit(1)

        database_file = dataset_path / 'database.db'
        if not database_file.exists():
            print(f"Error: Database file not found at {database_file}")
            sys.exit(1)

        print(f"Dataset: {args.dataset}")
        print(f"Questions: {questions_file}")
        print(f"Database: {database_file}")
        print(f"Model: {args.model}")

    else:
        print("Error: Must specify either:")
        print("  --questions <file> --db <path> --model <model>")
        print("  <dataset> --model <model>")
        sys.exit(1)

    print("\nEvaluation pipeline not yet implemented")


if __name__ == '__main__':
    main()
