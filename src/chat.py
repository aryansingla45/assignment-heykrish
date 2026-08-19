"""
Natural-language query interface for the Shelf Report.

Takes an English question, uses Gemini to generate SQL, executes it
against a read-only database connection, and returns the result.

Usage:
    python -m src.chat
"""
import os
import re
import sqlite3
import logging
from pathlib import Path

from dotenv import load_dotenv
from google import genai

from src.config import DB_PATH

load_dotenv()
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"
BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|DETACH|PRAGMA|VACUUM)\b",
    re.IGNORECASE,
)


def _get_readonly_connection(db_path: str = None) -> sqlite3.Connection:
    """Open a read-only SQLite connection. This is the database-level guardrail."""
    path = db_path or str(DB_PATH)
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def validate_sql(sql: str) -> str:
    """
    Code-level SQL guardrail — rejects any non-SELECT statement.
    """
    stripped = sql.strip().rstrip(";").strip()
    if not stripped.upper().startswith("SELECT"):
        raise ValueError(
            f"Only SELECT queries are allowed. Got: {stripped[:50]}..."
        )
    if BLOCKED_KEYWORDS.search(stripped):
        match = BLOCKED_KEYWORDS.search(stripped)
        raise ValueError(
            f"Blocked keyword detected: {match.group()}. "
            "Only read-only SELECT queries are permitted."
        )
    return stripped


def execute_query(sql: str, db_path: str = None) -> list[dict]:
    """
    Execute a validated SQL query against the read-only database.
    """
    clean_sql = validate_sql(sql)
    conn = _get_readonly_connection(db_path)
    try:
        rows = conn.execute(clean_sql).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ask(question: str, db_path: str = None, system_prompt: str = None) -> str:
    """
    Answer an English question using the database via Gemini.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Error: GEMINI_API_KEY not set. Add it to your .env file."

    if system_prompt is None:
        system_prompt = SYSTEM_PROMPT_PATH.read_text()

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=f"Question: {question}",
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
        ),
    )

    answer_text = response.text

    # Extract any SQL in the response to run it
    sql_blocks = re.findall(r"```sql\s*(.*?)\s*```", answer_text, re.DOTALL)

    results_text = ""
    for sql in sql_blocks:
        try:
            results = execute_query(sql, db_path)
            if results:
                results_text += f"\nQuery results ({len(results)} rows):\n"
                for row in results[:20]:  # Cap display at 20 rows
                    results_text += f"  {dict(row)}\n"
            else:
                results_text += "\nQuery returned no results.\n"
        except ValueError as e:
            results_text += f"\nBlocked by code guardrail: {e}\n"
        except sqlite3.Error as e:
            results_text += f"\nDatabase error: {e}\n"

    if results_text:
        return answer_text + "\n" + results_text
    
    return answer_text


def chat_loop(db_path: str = None):
    """Interactive chat loop for Priya."""
    print("=" * 60)
    print("Shelf Report — Ask me anything about the data")
    print("Type 'quit' to exit")
    print("=" * 60)

    while True:
        try:
            question = input("\nPriya> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question or question.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        print("\nThinking...\n")
        answer = ask(question, db_path)
        print(answer)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    chat_loop()
