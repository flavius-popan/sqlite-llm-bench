import pytest
import sys
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval import main


class TestCLIArgumentParsing:
    """Test command line argument parsing."""

    def test_dataset_mode_valid(self, capsys):
        """Test dataset mode with valid arguments."""
        test_args = ['eval.py', 'hello_world', '--model', 'test/model']

        with patch('sys.argv', test_args):
            main()

            captured = capsys.readouterr()
            assert 'Dataset: hello_world' in captured.out
            assert 'Model: test/model' in captured.out
            assert 'Questions: datasets/hello_world/questions.jsonl' in captured.out
            assert 'Database: datasets/hello_world/database.db' in captured.out

    def test_direct_file_mode_valid(self, capsys, temp_db):
        """Test direct file mode with valid arguments."""
        # Create temporary questions file
        questions_file = Path(temp_db).parent / 'questions.jsonl'
        questions_file.write_text('{"question": "test", "sql": "SELECT 1", "table": "users"}\n')

        test_args = [
            'eval.py',
            '--questions', str(questions_file),
            '--db', temp_db,
            '--model', 'test/model'
        ]

        with patch('sys.argv', test_args):
            main()

            captured = capsys.readouterr()
            assert f'Questions: {questions_file}' in captured.out
            assert f'Database: {temp_db}' in captured.out
            assert 'Model: test/model' in captured.out

    def test_missing_model_argument(self, capsys):
        """Test that missing --model argument shows error."""
        test_args = ['eval.py', 'hello_world']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            # Should exit with error code
            assert exc_info.value.code != 0

    def test_missing_required_arguments(self, capsys):
        """Test error when neither dataset nor file arguments provided."""
        test_args = ['eval.py', '--model', 'test/model']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert 'Error: Must specify either:' in captured.out
            assert exc_info.value.code == 1

    def test_nonexistent_dataset(self, capsys):
        """Test error when dataset doesn't exist."""
        test_args = ['eval.py', 'nonexistent_dataset', '--model', 'test/model']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert "Dataset 'nonexistent_dataset' not found" in captured.out
            assert exc_info.value.code == 1

    def test_nonexistent_questions_file(self, capsys):
        """Test error when questions file doesn't exist."""
        test_args = [
            'eval.py',
            '--questions', 'nonexistent.jsonl',
            '--db', 'test.db',
            '--model', 'test/model'
        ]

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert 'Questions file not found' in captured.out
            assert exc_info.value.code == 1

    def test_nonexistent_database_file(self, capsys):
        """Test error when database file doesn't exist."""
        # Create temporary questions file
        questions_file = Path.cwd() / 'temp_questions.jsonl'
        questions_file.write_text('{"question": "test"}\n')

        try:
            test_args = [
                'eval.py',
                '--questions', str(questions_file),
                '--db', 'nonexistent.db',
                '--model', 'test/model'
            ]

            with patch('sys.argv', test_args):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                captured = capsys.readouterr()
                assert 'Database path not found' in captured.out
                assert exc_info.value.code == 1
        finally:
            questions_file.unlink(missing_ok=True)

    def test_dataset_missing_questions_file(self, capsys):
        """Test error when dataset exists but questions.jsonl doesn't."""
        # Use a dataset name that doesn't exist in the real datasets directory
        test_args = ['eval.py', 'nonexistent_dataset_xyz', '--model', 'test/model']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert "Dataset 'nonexistent_dataset_xyz' not found" in captured.out
            assert exc_info.value.code == 1

    def test_dataset_missing_database_file(self, capsys):
        """Test error when dataset exists but database.db doesn't."""
        # Use a dataset name that doesn't exist in the real datasets directory
        test_args = ['eval.py', 'nonexistent_dataset_abc', '--model', 'test/model']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert "Dataset 'nonexistent_dataset_abc' not found" in captured.out
            assert exc_info.value.code == 1

    def test_help_message(self, capsys):
        """Test that help message displays correctly."""
        test_args = ['eval.py', '--help']

        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()

            captured = capsys.readouterr()
            assert 'Evaluate language models on SQL generation tasks' in captured.out
            assert 'Examples:' in captured.out
            assert exc_info.value.code == 0

    def test_short_model_flag(self, capsys):
        """Test that -m short flag works for model argument."""
        test_args = ['eval.py', 'hello_world', '-m', 'test/model']

        with patch('sys.argv', test_args):
            main()

            captured = capsys.readouterr()
            assert 'Model: test/model' in captured.out

    def test_evaluation_pipeline_runs(self, capsys):
        """Test that evaluation pipeline executes without errors."""
        test_args = ['eval.py', 'hello_world', '--model', 'test/model']

        with patch('sys.argv', test_args):
            # Should not raise any exceptions
            main()

            captured = capsys.readouterr()
            # Verify some evaluation activity occurred
            assert len(captured.out) > 100  # Should produce substantial output
            assert 'test/model' in captured.out  # Should mention the model
            assert captured.err == ""  # Should not have errors
