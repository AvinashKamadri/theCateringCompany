"""
Setup test database for AI agent testing
Creates a minimal SQLite database with only the tables the AI agent touches
"""

import sqlite3
from pathlib import Path


def setup_test_database(db_path: str = "database/test_agent.db"):
    """
    Create test database with minimal schema for AI agent testing
    """
    # Create database directory if it doesn't exist
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    # Remove existing database
    if Path(db_path).exists():
        Path(db_path).unlink()
        print(f"Removed existing database: {db_path}")
    
    # Create new database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Read and execute schema
    schema_path = Path(__file__).parent / "test_schema.sql"
    with open(schema_path, 'r') as f:
        schema_sql = f.read()
    
    # Execute entire schema as one script (SQLite executescript handles multiple statements)
    try:
        cursor.executescript(schema_sql)
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error executing schema: {e}")
        conn.rollback()
        raise
    conn.close()
    
    print(f"✓ Test database created: {db_path}")
    print("\nTables created:")
    print("  1. projects")
    print("  2. threads")
    print("  3. messages")
    print("  4. contracts")
    print("  5. ai_conversation_states")
    print("\nThis database contains only the tables the AI agent touches.")
    print("Use this for testing the AI agent in isolation.")


if __name__ == "__main__":
    setup_test_database()
