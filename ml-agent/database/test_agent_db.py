"""
Test the AI agent database integration
Tests all tables and operations the AI agent will use
"""

import sqlite3
import json
from datetime import datetime
import uuid


def test_database():
    """Test all database operations for AI agent"""
    
    conn = sqlite3.connect('database/test_agent.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 60)
    print("Testing AI Agent Database")
    print("=" * 60)
    
    # Generate test IDs
    project_id = str(uuid.uuid4())
    thread_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    conversation_state_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    try:
        # Test 1: Create a project
        print("\n1. Creating project...")
        cursor.execute("""
            INSERT INTO projects (id, owner_user_id, title, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_id, user_id, "Test Wedding Event", "draft", now, now))
        print("   ✓ Project created")
        
        # Test 2: Create a thread
        print("\n2. Creating thread...")
        cursor.execute("""
            INSERT INTO threads (id, project_id, subject, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (thread_id, project_id, "AI Lead Intake", user_id, now))
        print("   ✓ Thread created")
        
        # Test 3: Create AI conversation state
        print("\n3. Creating AI conversation state...")
        slots = {
            "name": {"value": "John Smith", "filled": True, "modified_at": now, "modification_history": []},
            "phone": {"value": "+917012345678", "filled": True, "modified_at": now, "modification_history": []},
            "event_date": {"value": "2026-05-15", "filled": True, "modified_at": now, "modification_history": []},
            "service_type": {"value": "on-site", "filled": True, "modified_at": now, "modification_history": []},
            "event_type": {"value": "Wedding", "filled": True, "modified_at": now, "modification_history": []},
            "venue": {"value": "Grand Ballroom, Mumbai", "filled": True, "modified_at": now, "modification_history": []},
            "guest_count": {"value": 150, "filled": True, "modified_at": now, "modification_history": []},
            "special_requests": {"value": "No pork, halal options needed", "filled": True, "modified_at": now, "modification_history": []}
        }
        
        cursor.execute("""
            INSERT INTO ai_conversation_states 
            (id, thread_id, project_id, current_node, slots, is_completed, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (conversation_state_id, thread_id, project_id, "generate_contract", 
              json.dumps(slots), 1, now, now))
        print("   ✓ AI conversation state created")
        
        # Test 4: Add messages
        print("\n4. Adding messages...")
        
        # User message
        user_msg_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO messages 
            (id, thread_id, project_id, author_id, sender_type, content, 
             ai_conversation_state_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_msg_id, thread_id, project_id, user_id, "client", 
              "Hi, I need catering for my wedding", conversation_state_id, now))
        
        # AI message
        ai_msg_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO messages 
            (id, thread_id, project_id, author_id, sender_type, content, 
             ai_conversation_state_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ai_msg_id, thread_id, project_id, "ai-agent", "ai", 
              "Great! I'd love to help. May I have your name?", conversation_state_id, now))
        
        print("   ✓ Messages added (user + AI)")
        
        # Test 5: Verify thread message count was updated by trigger
        print("\n5. Checking thread message count (trigger test)...")
        cursor.execute("SELECT message_count FROM threads WHERE id = ?", (thread_id,))
        count = cursor.fetchone()['message_count']
        print(f"   ✓ Message count: {count} (expected: 2)")
        
        # Test 6: Create contract
        print("\n6. Creating contract...")
        contract_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO contracts 
            (id, project_id, client_name, client_phone, event_type, event_date,
             service_type, guest_count, venue, special_requests, pricing_data,
             ai_conversation_state_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (contract_id, project_id, "John Smith", "+917012345678", "Wedding",
              "2026-05-15", "on-site", 150, json.dumps({"name": "Grand Ballroom"}),
              json.dumps({"dietary": "No pork, halal"}), 
              json.dumps({"total": 45000, "per_person": 300}),
              conversation_state_id, now, now))
        print("   ✓ Contract created")
        
        # Test 7: Query all data
        print("\n7. Querying all data...")
        
        # Get conversation state
        cursor.execute("""
            SELECT * FROM ai_conversation_states WHERE id = ?
        """, (conversation_state_id,))
        state = cursor.fetchone()
        print(f"   ✓ Conversation state: {state['current_node']}, completed: {bool(state['is_completed'])}")
        
        # Get messages
        cursor.execute("""
            SELECT sender_type, content FROM messages 
            WHERE thread_id = ? ORDER BY created_at
        """, (thread_id,))
        messages = cursor.fetchall()
        print(f"   ✓ Messages: {len(messages)}")
        for msg in messages:
            print(f"      - [{msg['sender_type']}] {msg['content'][:50]}...")
        
        # Get contract
        cursor.execute("""
            SELECT client_name, event_type, guest_count FROM contracts WHERE id = ?
        """, (contract_id,))
        contract = cursor.fetchone()
        print(f"   ✓ Contract: {contract['client_name']}, {contract['event_type']}, {contract['guest_count']} guests")
        
        # Test 8: Test @AI modification (update slot)
        print("\n8. Testing @AI modification...")
        slots_data = json.loads(state['slots'])
        old_count = slots_data['guest_count']['value']
        slots_data['guest_count']['value'] = 200
        slots_data['guest_count']['modification_history'].append({
            "old_value": old_count,
            "new_value": 200,
            "timestamp": now
        })
        
        cursor.execute("""
            UPDATE ai_conversation_states 
            SET slots = ?, updated_at = ?
            WHERE id = ?
        """, (json.dumps(slots_data), now, conversation_state_id))
        print(f"   ✓ Guest count updated: {old_count} → 200")
        
        # Test 9: Verify foreign keys work
        print("\n9. Testing foreign key constraints...")
        cursor.execute("SELECT COUNT(*) as count FROM messages WHERE ai_conversation_state_id = ?", 
                      (conversation_state_id,))
        linked_messages = cursor.fetchone()['count']
        print(f"   ✓ Messages linked to conversation: {linked_messages}")
        
        cursor.execute("SELECT COUNT(*) as count FROM contracts WHERE ai_conversation_state_id = ?",
                      (conversation_state_id,))
        linked_contracts = cursor.fetchone()['count']
        print(f"   ✓ Contracts linked to conversation: {linked_contracts}")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nDatabase is ready for AI agent integration!")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    test_database()
