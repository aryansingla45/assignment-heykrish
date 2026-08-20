"""
Five evaluations for the Natural Language query interface (Phase 7).

Includes a specific refusal test to prove the AI will decline answering 
questions about data we don't have (sales/revenue).
"""
import os
import re
import pytest

from src.chat import ask


# Skip evals if the API key isn't provided so regular test runs don't fail
pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set — skipping LLM evals"
)


class TestEvals:
    """Evaluations for the natural language chat interface."""

    def test_eval_1_biscuit_count(self):
        """
        Question: How many biscuit products are there in India?
        Requirement: Must return a specific number, and prove it ran SQL.
        """
        answer = ask("How many biscuit products are there in India?")
        
        # Must contain numbers
        numbers = re.findall(r"\b\d+\b", answer)
        assert len(numbers) > 0, "Answer must contain at least one number."
        
        # Must contain SQL query proving it hit the database
        assert "```sql" in answer.lower(), "Answer must include the SQL query used."

    def test_eval_2_top_brand(self):
        """
        Question: Which brand has the most biscuit products?
        Requirement: Must mention Britannia.
        """
        answer = ask("Which brand has the most biscuit products?")
        answer_lower = answer.lower()
        
        assert "britannia" in answer_lower, "Answer must correctly identify Britannia."

    def test_eval_3_sugar_average(self):
        """
        Question: What is the average sugar content in biscuits?
        Requirement: Must return a number, and must acknowledge the missing data coverage gap.
        """
        answer = ask("What is the average sugar content in biscuits per 100g?")
        
        numbers = re.findall(r"\d+\.?\d*", answer)
        assert len(numbers) > 0, "Answer must include the average value."
        
        # It must mention that a large percentage of data is missing (NULLs)
        coverage_terms = ["missing", "null", "lack", "without", "coverage", "not available", "don't have"]
        has_coverage_warning = any(term in answer.lower() for term in coverage_terms)
        
        assert has_coverage_warning, "Answer failed to disclose the massive missing data gap for sugars."

    def test_eval_4_cross_category_comparison(self):
        """
        Question: Compare average sugar levels in biscuits vs chocolates.
        Requirement: Must successfully join/query both categories.
        """
        answer = ask("Compare average sugar levels in biscuits vs chocolates.")
        answer_lower = answer.lower()
        
        assert "biscuit" in answer_lower, "Answer must discuss biscuits."
        assert "chocolate" in answer_lower, "Answer must discuss chocolates."

    def test_eval_5_refusal_sales_question(self):
        """
        Question: Whose biscuits sell the most in India?
        Requirement: System MUST REFUSE to answer this because we have no sales data.
        """
        answer = ask("Whose biscuits sell the most in India?")
        answer_lower = answer.lower()
        
        refusal_phrases = [
            "no sales", "don't have sales", "cannot answer", "can't answer", 
            "no data on sales", "does not include sales", "not available", 
            "no information about sales", "cannot determine", "contain sales"
        ]
        
        has_refusal = any(phrase in answer_lower for phrase in refusal_phrases)
        assert has_refusal, f"System failed to refuse the sales question. Got: {answer[:300]}"
