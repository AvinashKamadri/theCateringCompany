"""
SQLite3 database setup and operations for Catering AI Agent

This module provides direct SQLite3 operations for testing before
integrating with Prisma ORM.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class CateringDatabase:
    """SQLite3 database manager for the Catering AI Agent"""
    
    def __init__(self, db_path: str = "database/catering.db"):
        """Initialize database connection"""
        self.db_path = db_path
        
        # Create database directory if it doesn't exist
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        self.cursor = self.conn.cursor()
        
        # Create tables
        self._create_tables()
    
    def _create_tables(self):
        """Create all required tables"""
        
        # Conversation states table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_states (
                id TEXT PRIMARY KEY,
                conversation_id TEXT UNIQUE NOT NULL,
                project_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                current_node TEXT NOT NULL,
                slots TEXT NOT NULL,
                messages TEXT NOT NULL,
                metadata TEXT,
                is_completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create indexes for conversation_states
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_thread 
            ON conversation_states(thread_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_project 
            ON conversation_states(project_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_conversation_id 
            ON conversation_states(conversation_id)
        """)
        
        # AI tags table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_tags (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                field TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                field_content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create indexes for ai_tags
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_tags_thread 
            ON ai_tags(thread_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ai_tags_message 
            ON ai_tags(message_id)
        """)
        
        # Contracts table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                client_name TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_date TEXT NOT NULL,
                service_type TEXT NOT NULL,
                guest_count INTEGER NOT NULL,
                venue TEXT NOT NULL,
                special_requests TEXT,
                pricing_data TEXT NOT NULL,
                upsells_data TEXT,
                margin_data TEXT,
                staffing_data TEXT,
                missing_info_data TEXT,
                status TEXT DEFAULT 'draft',
                pdf_url TEXT,
                signed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        # Create indexes for contracts
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contracts_project 
            ON contracts(project_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contracts_conversation 
            ON contracts(conversation_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_contracts_status 
            ON contracts(status)
        """)
        
        # Messages table
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                thread_id TEXT NOT NULL,
                conversation_id TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_type TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT NOT NULL
            )
        """)
        
        # Create indexes for messages
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_thread 
            ON messages(thread_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
            ON messages(conversation_id)
        """)
        self.cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_created 
            ON messages(created_at)
        """)
        
        self.conn.commit()
    
    def save_conversation_state(self, state: Dict[str, Any]) -> bool:
        """Save or update conversation state"""
        import uuid
        
        conversation_id = state.get("conversation_id")
        now = datetime.now().isoformat()
        
        # Check if conversation exists
        self.cursor.execute(
            "SELECT id FROM conversation_states WHERE conversation_id = ?",
            (conversation_id,)
        )
        existing = self.cursor.fetchone()
        
        if existing:
            # Update existing
            self.cursor.execute("""
                UPDATE conversation_states 
                SET current_node = ?,
                    slots = ?,
                    messages = ?,
                    metadata = ?,
                    is_completed = ?,
                    updated_at = ?
                WHERE conversation_id = ?
            """, (
                state.get("current_node"),
                json.dumps(state.get("slots", {})),
                json.dumps([msg.dict() if hasattr(msg, 'dict') else str(msg) for msg in state.get("messages", [])]),
                json.dumps(state.get("metadata", {})),
                1 if state.get("current_node") == "done" else 0,
                now,
                conversation_id
            ))
        else:
            # Insert new
            self.cursor.execute("""
                INSERT INTO conversation_states 
                (id, conversation_id, project_id, thread_id, current_node, 
                 slots, messages, metadata, is_completed, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),
                conversation_id,
                state.get("project_id"),
                state.get("thread_id"),
                state.get("current_node"),
                json.dumps(state.get("slots", {})),
                json.dumps([msg.dict() if hasattr(msg, 'dict') else str(msg) for msg in state.get("messages", [])]),
                json.dumps(state.get("metadata", {})),
                1 if state.get("current_node") == "done" else 0,
                now,
                now
            ))
        
        self.conn.commit()
        return True
    
    def load_conversation_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation state by thread ID"""
        self.cursor.execute("""
            SELECT * FROM conversation_states 
            WHERE thread_id = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        """, (thread_id,))
        
        row = self.cursor.fetchone()
        if not row:
            return None
        
        return {
            "conversation_id": row["conversation_id"],
            "project_id": row["project_id"],
            "thread_id": row["thread_id"],
            "current_node": row["current_node"],
            "slots": json.loads(row["slots"]),
            "messages": json.loads(row["messages"]),
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "next_action": None,
            "error": None
        }
    
    def save_contract(self, contract_data: Dict[str, Any]) -> str:
        """Save contract to database"""
        import uuid
        
        contract_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        slots = contract_data.get("slots", {})
        
        self.cursor.execute("""
            INSERT INTO contracts 
            (id, conversation_id, project_id, client_name, client_phone,
             event_type, event_date, service_type, guest_count, venue,
             special_requests, pricing_data, upsells_data, margin_data,
             staffing_data, missing_info_data, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            contract_id,
            slots.get("conversation_id", "unknown"),
            slots.get("project_id", "unknown"),
            slots.get("name"),
            slots.get("phone"),
            slots.get("event_type"),
            slots.get("event_date"),
            slots.get("service_type"),
            slots.get("guest_count"),
            json.dumps(slots.get("venue", {})),
            json.dumps(slots.get("special_requests", {})),
            json.dumps(contract_data.get("pricing", {})),
            json.dumps(contract_data.get("upsells", {})),
            json.dumps(contract_data.get("margin", {})),
            json.dumps(contract_data.get("staffing", {})),
            json.dumps(contract_data.get("missing_info", {})),
            "draft",
            now,
            now
        ))
        
        self.conn.commit()
        return contract_id
    
    def get_contract(self, contract_id: str) -> Optional[Dict[str, Any]]:
        """Get contract by ID"""
        self.cursor.execute("SELECT * FROM contracts WHERE id = ?", (contract_id,))
        row = self.cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "project_id": row["project_id"],
            "client_name": row["client_name"],
            "client_phone": row["client_phone"],
            "event_type": row["event_type"],
            "event_date": row["event_date"],
            "service_type": row["service_type"],
            "guest_count": row["guest_count"],
            "venue": json.loads(row["venue"]),
            "special_requests": json.loads(row["special_requests"]) if row["special_requests"] else None,
            "pricing_data": json.loads(row["pricing_data"]),
            "upsells_data": json.loads(row["upsells_data"]) if row["upsells_data"] else None,
            "margin_data": json.loads(row["margin_data"]) if row["margin_data"] else None,
            "staffing_data": json.loads(row["staffing_data"]) if row["staffing_data"] else None,
            "missing_info_data": json.loads(row["missing_info_data"]) if row["missing_info_data"] else None,
            "status": row["status"],
            "pdf_url": row["pdf_url"],
            "signed_at": row["signed_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
    
    def save_ai_tag(self, thread_id: str, message_id: str, field: str, 
                    old_value: str, new_value: str, field_content: str) -> str:
        """Save AI tag modification"""
        import uuid
        
        tag_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        self.cursor.execute("""
            INSERT INTO ai_tags 
            (id, thread_id, message_id, field, old_value, new_value, 
             field_content, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tag_id,
            thread_id,
            message_id,
            field,
            old_value,
            new_value,
            field_content,
            now,
            now
        ))
        
        self.conn.commit()
        return tag_id
    
    def save_message(self, thread_id: str, conversation_id: str, 
                    author_id: str, author_type: str, content: str,
                    metadata: Optional[Dict] = None) -> str:
        """Save message to database"""
        import uuid
        
        message_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        
        self.cursor.execute("""
            INSERT INTO messages 
            (id, thread_id, conversation_id, author_id, author_type, 
             content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            message_id,
            thread_id,
            conversation_id,
            author_id,
            author_type,
            content,
            json.dumps(metadata) if metadata else None,
            now
        ))
        
        self.conn.commit()
        return message_id
    
    def get_conversation_history(self, thread_id: str) -> list:
        """Get all messages for a thread"""
        self.cursor.execute("""
            SELECT * FROM messages 
            WHERE thread_id = ? 
            ORDER BY created_at ASC
        """, (thread_id,))
        
        rows = self.cursor.fetchall()
        return [dict(row) for row in rows]
    
    def close(self):
        """Close database connection"""
        self.conn.close()


# Convenience functions
def get_database() -> CateringDatabase:
    """Get database instance"""
    return CateringDatabase()


if __name__ == "__main__":
    # Test database setup
    print("Setting up SQLite3 database...")
    db = CateringDatabase()
    print("✓ Database created successfully!")
    print(f"  Location: {db.db_path}")
    print("\nTables created:")
    print("  - conversation_states")
    print("  - ai_tags")
    print("  - contracts")
    print("  - messages")
    db.close()
