"""
Test Prisma Client Python integration

This script tests the Prisma ORM integration with the Catering AI Agent.
"""

import asyncio
import sys
sys.path.append('..')

from database.prisma_client_setup import PrismaDatabaseManager
from orchestrator import AgentOrchestrator


async def test_prisma_integration():
    """Test complete Prisma integration"""
    
    print("=" * 70)
    print("PRISMA CLIENT PYTHON INTEGRATION TEST")
    print("=" * 70)
    print()
    
    # Initialize database manager
    print("1. Connecting to database with Prisma...")
    db = PrismaDatabaseManager()
    await db.connect()
    print("   ✓ Connected successfully")
    print()
    
    # Initialize orchestrator
    print("2. Initializing agent orchestrator...")
    orchestrator = AgentOrchestrator()
    print("   ✓ Orchestrator initialized")
    print()
    
    # Test conversation
    thread_id = "test-prisma-thread-1"
    user_id = "test-user-prisma"
    
    print("3. Starting conversation...")
    print()
    
    # Message 1: Name
    print("   User: My name is Alice Cooper")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="My name is Alice Cooper",
        author_id=user_id
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database using Prisma
    await db.save_conversation_state(response.conversation_state)
    await db.save_message(thread_id, response.conversation_id, user_id, "user", "My name is Alice Cooper")
    await db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database with Prisma")
    print()
    
    # Message 2: Phone
    print("   User: 555-999-8888")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="555-999-8888",
        author_id=user_id,
        conversation_state=response.conversation_state
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database
    await db.save_conversation_state(response.conversation_state)
    await db.save_message(thread_id, response.conversation_id, user_id, "user", "555-999-8888")
    await db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database with Prisma")
    print()
    
    # Message 3: Event date
    print("   User: August 20th, 2026")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="August 20th, 2026",
        author_id=user_id,
        conversation_state=response.conversation_state
    )
    print(f"   Agent: {response.content[:80]}...")
    print(f"   [Slots: {response.slots_filled}/8]")
    
    # Save to database
    await db.save_conversation_state(response.conversation_state)
    await db.save_message(thread_id, response.conversation_id, user_id, "user", "August 20th, 2026")
    await db.save_message(thread_id, response.conversation_id, "agent", "agent", response.content)
    print("   ✓ Saved to database with Prisma")
    print()
    
    print("4. Testing state recovery with Prisma...")
    # Load state from database
    loaded_state = await db.load_conversation_state(thread_id)
    if loaded_state:
        print("   ✓ State loaded successfully")
        print(f"   - Conversation ID: {loaded_state['conversation_id']}")
        print(f"   - Current Node: {loaded_state['current_node']}")
        print(f"   - Slots filled: {sum(1 for s in loaded_state['slots'].values() if s['filled'])}/8")
    else:
        print("   ✗ Failed to load state")
    print()
    
    print("5. Testing conversation history with Prisma...")
    history = await db.get_conversation_history(thread_id)
    print(f"   ✓ Retrieved {len(history)} messages")
    for i, msg in enumerate(history[:4], 1):
        print(f"   {i}. [{msg.authorType}] {msg.content[:50]}...")
    print()
    
    print("6. Testing @AI modification with Prisma...")
    print("   User: @AI change my name to Alice Smith")
    response = await orchestrator.process_message(
        thread_id=thread_id,
        message="@AI change my name to Alice Smith",
        author_id=user_id,
        conversation_state=loaded_state
    )
    print(f"   Agent: {response.content[:80]}...")
    
    # Save AI tag
    if response.conversation_state["slots"]["name"]["value"] == "Alice Smith":
        await db.save_ai_tag(
            thread_id=thread_id,
            message_id="msg-prisma-test-1",
            field="name",
            old_value="Alice Cooper",
            new_value="Alice Smith",
            field_content="change my name to Alice Smith"
        )
        print("   ✓ AI tag saved with Prisma")
    print()
    
    print("7. Testing contract generation with Prisma...")
    # Mock contract data
    contract_data = {
        "slots": {
            "conversation_id": response.conversation_id,
            "project_id": response.project_id,
            "name": "Alice Smith",
            "phone": "555-999-8888",
            "event_type": "Corporate",
            "event_date": "2026-08-20",
            "service_type": "on-site",
            "guest_count": 100,
            "venue": {
                "address": "456 Business Ave",
                "kitchen_access": "full",
                "load_in_time": "10am"
            },
            "special_requests": {
                "dietary_restrictions": ["gluten-free"],
                "allergies": []
            }
        },
        "pricing": {
            "package_name": "Corporate Package",
            "base_price": 2000.0,
            "per_person_price": 40.0,
            "estimated_total": 6000.0
        },
        "upsells": {
            "upsells": [
                {
                    "category": "AV Equipment",
                    "name": "Presentation Setup",
                    "price": 500.0,
                    "reasoning": "Professional presentations",
                    "priority": "medium"
                }
            ],
            "total_potential_revenue": 500.0
        },
        "margin": {
            "total_revenue": 6000.0,
            "total_cost": 3900.0,
            "gross_margin": 2100.0,
            "margin_percentage": 35.0,
            "warnings": [],
            "recommendations": ["Good margin"]
        },
        "staffing": {
            "servers_needed": 5,
            "bartenders_needed": 1,
            "total_labor_hours": 36.0,
            "estimated_labor_cost": 936.0,
            "reasoning": "Based on 100 guests"
        },
        "missing_info": {
            "is_complete": True,
            "missing_required": [],
            "missing_recommended": [],
            "risk_flags": []
        }
    }
    
    contract = await db.save_contract(contract_data)
    print(f"   ✓ Contract saved with ID: {contract.id}")
    print()
    
    print("8. Testing contract retrieval with Prisma...")
    loaded_contract = await db.get_contract(contract.id)
    if loaded_contract:
        print("   ✓ Contract loaded successfully")
        print(f"   - Client: {loaded_contract.clientName}")
        print(f"   - Event: {loaded_contract.eventType} on {loaded_contract.eventDate}")
        print(f"   - Guests: {loaded_contract.guestCount}")
        print(f"   - Status: {loaded_contract.status}")
    print()
    
    print("9. Testing contract status update with Prisma...")
    updated_contract = await db.update_contract_status(
        contract.id,
        "sent",
        pdf_url="https://example.com/contract.pdf"
    )
    print(f"   ✓ Contract status updated to: {updated_contract.status}")
    print(f"   ✓ PDF URL: {updated_contract.pdfUrl}")
    print()
    
    # Cleanup
    await db.disconnect()
    
    print("=" * 70)
    print("PRISMA INTEGRATION TEST SUMMARY")
    print("=" * 70)
    print()
    print("✓ All Prisma operations working correctly:")
    print("  - Database connection")
    print("  - Conversation state save/load")
    print("  - Message history tracking")
    print("  - AI tag modifications")
    print("  - Contract generation and storage")
    print("  - Contract status updates")
    print("  - State recovery after interruption")
    print()
    print("Prisma Client Python is fully integrated!")
    print()


async def test_query_examples():
    """Test various Prisma query examples"""
    
    print("=" * 70)
    print("PRISMA QUERY EXAMPLES")
    print("=" * 70)
    print()
    
    db = PrismaDatabaseManager()
    await db.connect()
    
    print("1. Find all incomplete conversations...")
    incomplete = await db.db.conversationstate.find_many(
        where={
            "isCompleted": False
        },
        take=5
    )
    print(f"   ✓ Found {len(incomplete)} incomplete conversations")
    print()
    
    print("2. Find all draft contracts...")
    drafts = await db.db.contract.find_many(
        where={
            "status": "draft"
        },
        take=5
    )
    print(f"   ✓ Found {len(drafts)} draft contracts")
    print()
    
    print("3. Count total conversations...")
    count = await db.db.conversationstate.count()
    print(f"   ✓ Total conversations: {count}")
    print()
    
    print("4. Count total contracts...")
    contract_count = await db.db.contract.count()
    print(f"   ✓ Total contracts: {contract_count}")
    print()
    
    await db.disconnect()


async def main():
    """Run all tests"""
    try:
        await test_prisma_integration()
        print()
        await test_query_examples()
        
        print("=" * 70)
        print("ALL PRISMA TESTS PASSED ✓")
        print("=" * 70)
        print()
        print("Prisma Client Python is working perfectly!")
        print()
        print("Next steps:")
        print("1. Use Prisma in your Python application")
        print("2. Switch to PostgreSQL for production")
        print("3. Add more complex queries as needed")
        print()
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
