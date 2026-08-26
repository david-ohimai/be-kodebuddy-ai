# cleanup_orphan_test_rows.py — run once, then delete this file
from sqlalchemy import text
from app.core.database import engine

statements = [
    "DELETE FROM content_embeddings WHERE text = 'FAQ sample question and answer'",
    "DELETE FROM escalations WHERE question = 'What is a variable?'",
    "DELETE FROM conversation_history WHERE message = 'Hi there'",
    "DELETE FROM query_logs WHERE question = 'What is a loop?'",
    "DELETE FROM courses WHERE title = 'test_agent_models_in_db course'",
    "DELETE FROM cohorts WHERE name = 'test_agent_models_in_db cohort'",
    "DELETE FROM users WHERE email = 'test_agent_models_in_db@example.com'",
]

with engine.connect() as conn:
    for stmt in statements:
        result = conn.execute(text(stmt))
        print(f"{stmt} -> {result.rowcount} row(s) deleted")
    conn.commit()

print("Done.")