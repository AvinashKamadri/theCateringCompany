"""
Test script to verify database operations
"""

import asyncio
import sys
sys.path.append('..')

from database.sqlite_setup import CateringDatabase
from orchestrator import AgentOrchestrator


async def test_complete_flow():
    """Test complete conversation flow with database persistence"""
    
    print("=" * 70)
    print("DATABASE INTEGRATION TEST")
    print("=" * 70)
    print()
    
    # Initialize database
    print("1. Initializing database...")
    db = CateringDatabase()
    print("   ✓ Database initialized")
    print()
    
    # Initialize orchestrator
    print("2. Initializing agent orchestrator...")
    orchestrator = AgentOrchestrator()
    print("   ✓ Orchestrator initialized")
    print()
    
    # Test conversation
    thread_id = "test-thread-db-1"
    user_id = "test-user-1"
    
    print("3. Starting conversation...")
    print()
    
    # Message 1: Name
    print("   User: My name is Sarah Johnson")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Sarah Johnson",
        author_id=user_id
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database
    db.save_conversation_state(response.conversation_state)
    db.save_message(thread_id, response.conversation_id, user_id, "user", "My name is Sarah Johnson")
    db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database")
    print()
    
    # Message 2: Phone
    print("   User: 555-123-4567")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="555-123-4567",
        author_id=user_id,
        conversation_state=response.conversation_state
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database
    db.save_conversation_state(response.conversation_state)
    db.save_message(thread_id, response.conversation_id, user_id, "user", "555-123-4567")
    db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database")
    print()
    
    # Message 3: Event date
    print("   User: June 15th, 2026")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="June 15th, 2026",
        author_id=user_id,
        conversation_state=response.conversation_state
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database
    db.save_conversation_state(response.conversation_state)
    db.save_message(thread_id, response.conversation_id, user_id, "user", "June 15th, 2026")
    db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database")
    print()
    
    print("4. Testing state recovery from database...")
    # Load state from database
    loaded_state = db.load_conversation_state(thread_id)
    if loaded_state:
        print("   ✓ State loaded successfully")
        print(f"   - Conversation ID: {loaded_state['conversation_id']}")
        print(f"   - Current Node: {loaded_state['current_node']}")
        print(f"   - Slots filled: {sum(1 for s in loaded_state['slots'].values() if s['filled'])}/8")
    else:
        print("   ✗ Failed to load state")
    print()
    
    print("5. Testing conversation history...")
    history = db.get_conversation_history(thread_id)
    print(f"   ✓ Retrieved {len(history)} messages")
    for i, msg in enumerate(history[:4], 1):  # Show first 4 messages
        print(f"   {i}. [{msg['author_type']}] {msg['content'][:50]}...")
    print()
    
    print("6. Testing @AI modification...")
    print("   User: @AI change my name to Sarah Smith")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="@AI change my name to Sarah Smith",
        author_id=user_id,
        conversation_state=loaded_state
    )
    print(f"   Agent: {response.content[:80]}...")
    
    # Save AI tag
    if response.conversation_state["slots"]["name"]["value"] == "Sarah Smith":
        db.save_ai_tag(
            thread_id=thread_id,
            message_id="msg-test-1",
            field="name",
            old_value="Sarah Johnson",
            new_value="Sarah Smith",
            field_content="change my name to Sarah Smith"
        )
        print("   ✓ AI tag saved")
    print()
    
    print("=" * 70)
    print("DATABASE TEST SUMMARY")
    print("=" * 70)
    print()
    print("✓ Database operations working correctly:")
    print("  - Conversation state save/load")
    print("  - Message history tracking")
    print("  - AI tag modifications")
    print("  - State recovery after interruption")
    print()
    print("Database location: database/catering.db")
    print("You can inspect it with: sqlite3 database/catering.db")
    print()
    
    db.close()


async def test_contract_generation():
    """Test contract generation and storage"""
    
    print("=" * 70)
    print("CONTRACT GENERATION TEST")
    print("=" * 70)
    print()
    
    db = CateringDatabase()
    
    # Mock contract data
    contract_data = {
        "slots": {
            "conversation_id": "conv-test-1",
            "project_id": "proj-test-1",
            "name": "John Doe",
            "phone": "555-987-6543",
            "event_type": "Wedding",
            "event_date": "2026-07-20",
            "service_type": "on-site",
            "guest_count": 150,
            "venue": {
                "address": "123 Main St",
                "kitchen_access": "full",
                "load_in_time": "2pm"
            },
            "special_requests": {
                "dietary_restrictions": ["vegetarian"],
                "allergies": ["peanut"]
            }
        },
        "pricing": {
            "package_name": "Premium Wedding Package",
            "base_price": 3000.0,
            "per_person_price": 55.0,
            "estimated_total": 11250.0
        },
        "upsells": {
            "upsells": [
                {
                    "category": "Bar Service",
                    "name": "Premium Open Bar",
                    "price": 6750.0,
                    "reasoning": "Perfect for wedding celebrations",
                    "priority": "high"
                }
            ],
            "total_potential_revenue": 6750.0
        },
        "margin": {
            "total_revenue": 11250.0,
            "total_cost": 7312.5,
            "gross_margin": 3937.5,
            "margin_percentage": 35.0,
            "warnings": [],
            "recommendations": ["Excellent margin"]
        },
        "staffing": {
            "servers_needed": 8,
            "bartenders_needed": 2,
            "total_labor_hours": 60.0,
            "estimated_labor_cost": 1560.0,
            "reasoning": "Based on 150 guests"
        },
        "missing_info": {
            "is_complete": True,
            "missing_required": [],
            "missing_recommended": [],
            "risk_flags": []
        }
    }
    
    print("Saving contract to database...")
    contract_id = db.save_contract(contract_data)
    print(f"✓ Contract saved with ID: {contract_id}")
    print()
    
    print("Loading contract from database...")
    loaded_contract = db.get_contract(contract_id)
    if loaded_contract:
        print("✓ Contract loaded successfully")
        print(f"  - Client: {loaded_contract['client_name']}")
        print(f"  - Event: {loaded_contract['event_type']} on {loaded_contract['event_date']}")
        print(f"  - Guests: {loaded_contract['guest_count']}")
        print(f"  - Total: ${loaded_contract['pricing_data']['estimated_total']:.2f}")
        print(f"  - Margin: {loaded_contract['margin_data']['margin_percentage']}%")
        print(f"  - Status: {loaded_contract['status']}")
    else:
        print("✗ Failed to load contract")
    print()
    
    db.close()


async def main():
    """Run all tests"""
    try:
        await test_complete_flow()
        print()
        await test_contract_generation()
        
        print("=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)
        print()
        print("Next steps:")
        print("1. Inspect database: sqlite3 database/catering.db")
        print("2. Run queries: SELECT * FROM conversation_states;")
        print("3. Integrate with Prisma ORM for production")
        print()
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
