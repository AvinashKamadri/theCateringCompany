"""
Interactive agent runner for testing the full catering intake flow.
Stores everything in PostgreSQL via Prisma. Run with: python run_agent.py
"""

import asyncio
import uuid
from orchestrator import AgentOrchestrator
from database.db_manager import close_client


async def main():
    thread_id = str(uuid.uuid4())
    print("=" * 60)
    print("  THE CATERING COMPANY - AI Intake Agent")
    print("=" * 60)
    print(f"  Thread: {thread_id}")
    print(f"  (All messages stored in PostgreSQL)")
    print(f"  Type 'quit' to exit\n")

    orchestrator = AgentOrchestrator()

    try:
        # Send initial message to trigger start/welcome
        result = await orchestrator.process_message(
            thread_id=thread_id,
            message="hi",
            author_id="test-user",
        )

        print(f"Agent [{result['current_node']}]: {result['content']}\n")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break

            if user_input.lower() in ("quit", "exit", "q"):
                print("Goodbye!")
                break

            if not user_input:
                continue

            result = await orchestrator.process_message(
                thread_id=thread_id,
                message=user_input,
                author_id="test-user",
            )

            node = result["current_node"]
            filled = result["slots_filled"]
            total = result["total_slots"]
            print(f"\nAgent [{node}] ({filled}/{total} slots): {result['content']}\n")

            if result["is_complete"]:
                print("=" * 60)
                print("  CONTRACT GENERATED! Check the database for full details.")
                print("=" * 60)
                break
    finally:
        await close_client()


if __name__ == "__main__":
    asyncio.run(main())
