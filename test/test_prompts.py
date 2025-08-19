import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from eval import (
    create_prompt_template, create_prompt_with_question,
    get_openai_tools, create_tool_calling_prompt, create_fallback_prompt,
    supports_tool_calling, setup_evaluation, generate_response, evaluate_response
)


class TestPromptTemplate:
    """Test the generic prompt template functionality."""

    def test_create_prompt_template_structure(self):
        """Test that prompt template creates valid OpenAI format."""
        template = create_prompt_template()

        assert isinstance(template, list)
        assert len(template) == 1
        assert isinstance(template[0], dict)
        assert template[0]["role"] == "system"
        assert "content" in template[0]
        assert isinstance(template[0]["content"], str)
        assert len(template[0]["content"]) > 0

    def test_prompt_includes_tool_descriptions(self):
        """Test that prompt includes both required tools."""
        template = create_prompt_template()
        content = template[0]["content"]

        # Check for describe_database tool
        assert "describe_database" in content
        assert "table_name" in content

        # Check for execute_sql tool
        assert "execute_sql" in content
        assert "SELECT" in content

    def test_prompt_includes_sql_instructions(self):
        """Test that prompt includes SQL generation guidance."""
        template = create_prompt_template()
        content = template[0]["content"]

        assert "SQL" in content
        assert "database" in content.lower()

    def test_prompt_includes_workflow_guidance(self):
        """Test that prompt includes step-by-step workflow."""
        template = create_prompt_template()
        content = template[0]["content"]

        # Should include some workflow structure
        assert ("1." in content or "First" in content or
                "explore" in content.lower() or "schema" in content.lower())

    def test_prompt_safety_instructions(self):
        """Test that prompt includes safety and format instructions."""
        template = create_prompt_template()
        content = template[0]["content"]

        assert "timeout" in content.lower()

    def test_create_prompt_with_question_structure(self):
        """Test creating complete prompt with user question."""
        question = "How many users are in the database?"
        messages = create_prompt_with_question(question)

        assert isinstance(messages, list)
        assert len(messages) == 2

        # Check system message
        assert messages[0]["role"] == "system"
        assert "describe_database" in messages[0]["content"]

        # Check user message
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == question

    def test_prompt_with_different_questions(self):
        """Test prompt works with various question types."""
        test_questions = [
            "Show me all users",
            "What is the total amount of all orders?",
            "Which user has the most orders?",
            "List all products ordered by Alice",
            ""  # Empty question
        ]

        for question in test_questions:
            messages = create_prompt_with_question(question)
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == question

    def test_prompt_content_consistency(self):
        """Test that prompt content is consistent across calls."""
        template1 = create_prompt_template()
        template2 = create_prompt_template()

        assert template1[0]["content"] == template2[0]["content"]

        # Test with same question
        question = "Test question"
        messages1 = create_prompt_with_question(question)
        messages2 = create_prompt_with_question(question)

        assert messages1[0]["content"] == messages2[0]["content"]
        assert messages1[1]["content"] == messages2[1]["content"]

    def test_prompt_format_for_backend_compatibility(self):
        """Test that prompt format is compatible with backend systems."""
        question = "Count the total number of orders"
        messages = create_prompt_with_question(question)

        # Should be valid OpenAI chat format
        for message in messages:
            assert "role" in message
            assert message["role"] in ["system", "user", "assistant"]
            assert "content" in message
            assert isinstance(message["content"], str)

        # Should not contain any backend-specific formatting
        content = messages[0]["content"]
        assert "<|system|>" not in content  # Not Qwen format
        assert "[INST]" not in content      # Not Llama format
        assert "Human:" not in content      # Not Anthropic format

    def test_tool_descriptions_are_accurate(self):
        """Test that tool descriptions mention key functionality."""
        template = create_prompt_template()
        content = template[0]["content"]

        # describe_database should mention table_name parameter
        describe_section = content[content.find("describe_database"):content.find("execute_sql")]
        assert "table_name" in describe_section

        # execute_sql should mention SELECT and safety
        execute_section = content[content.find("execute_sql"):]
        assert "SELECT" in execute_section
        assert "timeout" in execute_section.lower()

    def test_prompt_length_reasonable(self):
        """Test that prompt is neither too short nor too long."""
        template = create_prompt_template()
        content = template[0]["content"]

        # Should be substantial but not excessive
        assert 500 < len(content) < 2000, f"Prompt length {len(content)} not in reasonable range"

        # With question should not be much longer
        question = "What is the average order amount?"
        messages = create_prompt_with_question(question)
        total_length = sum(len(msg["content"]) for msg in messages)
        assert total_length < 2500


class TestToolCalling:
    """Test the tool calling functionality."""

    def test_get_openai_tools_structure(self):
        """Test that OpenAI tools have correct structure."""
        tools = get_openai_tools()

        assert isinstance(tools, list)
        assert len(tools) == 2

        for tool in tools:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_get_openai_tools_content(self):
        """Test that tools contain expected functions."""
        tools = get_openai_tools()
        tool_names = [tool["function"]["name"] for tool in tools]

        assert "describe_database" in tool_names
        assert "execute_sql" in tool_names

        # Check describe_database tool
        describe_tool = next(t for t in tools if t["function"]["name"] == "describe_database")
        assert "table_name" in describe_tool["function"]["parameters"]["properties"]
        assert "SQLite CLI format" in describe_tool["function"]["description"]

        # Check execute_sql tool
        execute_tool = next(t for t in tools if t["function"]["name"] == "execute_sql")
        assert "query" in execute_tool["function"]["parameters"]["properties"]
        assert "query" in execute_tool["function"]["parameters"]["required"]

    def test_create_tool_calling_prompt(self):
        """Test minimal prompt for tool-calling models."""
        question = "How many users are there?"
        messages = create_tool_calling_prompt(question)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == question

        # Should be minimal and mention tools
        system_content = messages[0]["content"]
        assert len(system_content) < 1000  # Reasonable length
        assert "describe_database" in system_content
        assert "execute_sql" in system_content

    def test_create_fallback_prompt(self):
        """Test rich prompt with schema injection for non-tool models."""
        question = "Count the users"
        db_path = "datasets/hello_world/database.db"
        messages = create_fallback_prompt(question, db_path)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == question

        # Should contain schema information
        system_content = messages[0]["content"]
        assert "users" in system_content
        assert "orders" in system_content
        # Should be longer than tool prompt due to schema injection
        tool_prompt_len = len(create_tool_calling_prompt(question)[0]["content"])
        assert len(system_content) > tool_prompt_len

    def test_supports_tool_calling(self):
        """Test model capability detection."""
        # Tool-capable models
        assert supports_tool_calling("qwen/qwen3-30b-a3b-2507") == True
        assert supports_tool_calling("openai/gpt-4") == True
        assert supports_tool_calling("llama3.1:8b") == True
        assert supports_tool_calling("mistral-nemo") == True

        # Non-tool models
        assert supports_tool_calling("test/model") == False
        assert supports_tool_calling("llama2") == False
        assert supports_tool_calling("unknown-model") == False

    def test_create_prompt_with_question_tool_mode(self):
        """Test prompt creation in tool calling mode."""
        question = "Show me all users"
        model = "qwen/qwen3-30b"
        messages = create_prompt_with_question(question, model)

        # Should create tool calling prompt
        assert len(messages) == 2
        system_content = messages[0]["content"]
        # Should be a minimal tool calling prompt
        assert "describe_database" in system_content
        assert "execute_sql" in system_content

    def test_create_prompt_with_question_fallback_mode(self):
        """Test prompt creation in fallback mode."""
        question = "Show me all users"
        model = "test/model"
        db_path = "datasets/hello_world/database.db"
        messages = create_prompt_with_question(question, model, db_path)

        # Should create fallback prompt with schema
        assert len(messages) == 2
        system_content = messages[0]["content"]
        assert "users" in system_content  # Schema injected
        assert "orders" in system_content  # Schema injected


class TestEvaluationPipeline:
    """Test the evaluation pipeline functionality."""

    def test_setup_evaluation(self):
        """Test evaluation setup loads questions correctly."""
        eval_context = setup_evaluation(
            "hello_world",
            "datasets/hello_world/questions.jsonl",
            "datasets/hello_world/database.db"
        )

        assert eval_context["dataset"] == "hello_world"
        assert eval_context["total_questions"] > 0
        assert isinstance(eval_context["questions"], list)
        assert "db_path" in eval_context

        # Check question structure
        question = eval_context["questions"][0]
        assert "question" in question
        assert "sql" in question

    def test_generate_response_tool_mode(self):
        """Test response generation in tool calling mode."""
        response = generate_response(
            question="How many users?",
            model="qwen/qwen3",
            db_path="datasets/hello_world/database.db",
            use_tools=True
        )

        assert response["use_tools"] == True
        assert response["tools"] is not None
        assert len(response["tools"]) == 2
        assert response["model"] == "qwen/qwen3"

    def test_generate_response_fallback_mode(self):
        """Test response generation in fallback mode."""
        response = generate_response(
            question="How many users?",
            model="test/model",
            db_path="datasets/hello_world/database.db",
            use_tools=False
        )

        assert response["use_tools"] == False
        assert response["tools"] is None
        assert response["model"] == "test/model"

    def test_evaluate_response_success(self):
        """Test successful SQL evaluation."""
        result = evaluate_response(
            generated_sql="SELECT COUNT(*) as count FROM users",
            gold_sql="SELECT COUNT(*) as count FROM users",
            db_path="datasets/hello_world/database.db"
        )

        assert result["success"] == True
        assert result["matches"] == True
        assert result["generated_result"] == result["gold_result"]
        assert result["generated_sql"] == "SELECT COUNT(*) as count FROM users"
        assert result["gold_sql"] == "SELECT COUNT(*) as count FROM users"

    def test_evaluate_response_mismatch(self):
        """Test SQL evaluation with different results."""
        result = evaluate_response(
            generated_sql="SELECT COUNT(*) as count FROM orders",
            gold_sql="SELECT COUNT(*) as count FROM users",
            db_path="datasets/hello_world/database.db"
        )

        assert result["success"] == True
        assert result["matches"] == False
        assert result["generated_result"] != result["gold_result"]
        assert "generated_result" in result
        assert "gold_result" in result
        assert result["generated_sql"] == "SELECT COUNT(*) as count FROM orders"
        assert result["gold_sql"] == "SELECT COUNT(*) as count FROM users"

    def test_evaluate_response_error(self):
        """Test SQL evaluation with syntax error."""
        result = evaluate_response(
            generated_sql="INVALID SQL",
            gold_sql="SELECT COUNT(*) FROM users",
            db_path="datasets/hello_world/database.db"
        )

        assert result["success"] == False
        assert "error" in result
        assert result["generated_sql"] == "INVALID SQL"
        assert result["gold_sql"] == "SELECT COUNT(*) FROM users"
        assert "matches" not in result or result["matches"] == False

    def test_evaluation_consistency(self):
        """Test that evaluation uses the same execute_sql function for both queries."""
        from eval import execute_sql

        # Test that both generated and gold SQL use same execution path
        test_sql = "SELECT COUNT(*) as total FROM users"
        direct_result = execute_sql("datasets/hello_world/database.db", test_sql)

        eval_result = evaluate_response(
            generated_sql=test_sql,
            gold_sql=test_sql,
            db_path="datasets/hello_world/database.db"
        )

        assert eval_result["success"] == True
        assert eval_result["matches"] == True
        assert eval_result["generated_result"] == direct_result
        assert eval_result["gold_result"] == direct_result

    def test_mode_detection_logic(self):
        """Test that tool capability detection drives correct prompt creation."""
        question = "How many users?"
        db_path = "datasets/hello_world/database.db"

        # Tool-capable model should get tool calling prompt
        tool_messages = create_prompt_with_question(question, "qwen/qwen3", db_path)
        # Non-tool model should get fallback prompt
        fallback_messages = create_prompt_with_question(question, "test/model", db_path)

        # Both should be valid chat format
        for messages in [tool_messages, fallback_messages]:
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == question

        # Fallback should be longer due to schema injection
        tool_len = len(tool_messages[0]["content"])
        fallback_len = len(fallback_messages[0]["content"])
        assert fallback_len > tool_len

        # Fallback should contain actual schema data
        assert "users" in fallback_messages[0]["content"]
        assert "orders" in fallback_messages[0]["content"]
