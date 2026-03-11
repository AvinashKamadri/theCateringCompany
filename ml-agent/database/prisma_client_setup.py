"""
Prisma Client Python setup and integration

This module provides Prisma ORM integration for the Catering AI Agent.
Works with both SQLite (development) and PostgreSQL (production).

Installation:
    pip install prisma

Setup:
    1. Update schema.prisma with your database
    2. Run: prisma db push
    3. Run: prisma generate

Usage:
    from database.prisma_client_setup import get_prisma_client
    
    db = await get_prisma_client()
    
    # Save conversation state
    await db.conversationstate.upsert(...)
    
    # Load conversation state
    state = await db.conversationstate.find_unique(...)
"""

import json
from typing import Optional, Dict, Any
from datetime import datetime
from prisma import Prisma
from prisma.models import ConversationState, Contract, AiTag, Message


# Global Prisma client instance
_prisma_client: Optional[Prisma] = None


async def get_prisma_client() -> Prisma:
    """
    Get or create Prisma client instance.
    
    Returns:
        Prisma client instance
    """
    global _prisma_client
    
    if _prisma_client is None:
        _prisma_client = Prisma()
        await _prisma_client.connect()
    
    return _prisma_client


async def close_prisma_client():
    """Close Prisma client connection"""
    global _prisma_client
    
    if _prisma_client is not None:
        await _prisma_client.disconnect()
        _prisma_client = None


class PrismaDatabaseManager:
    """
    Database manager using Prisma Client Python.
    
    Provides high-level methods for database operations.
    """
    
    def __init__(self):
        """Initialize database manager"""
        self.db: Optional[Prisma] = None
    
    async def connect(self):
        """Connect to database"""
        self.db = await get_prisma_client()
    
    async def disconnect(self):
        """Disconnect from database"""
        await close_prisma_client()
        self.db = None
    
    async def save_conversation_state(self, state: Dict[str, Any]) -> ConversationState:
        """
        Save or update conversation state.
        
        Args:
            state: Conversation state dictionary
            
        Returns:
            ConversationState model
        """
        if not self.db:
            await self.connect()
        
        conversation_id = state.get("conversation_id")
        
        # Serialize messages
        messages_json = json.dumps([
            msg.dict() if hasattr(msg, 'dict') else str(msg) 
            for msg in state.get("messages", [])
        ])
        
        # Upsert conversation state
        conversation = await self.db.conversationstate.upsert(
            where={
                "conversationId": conversation_id
            },
            data={
                "create": {
                    "conversationId": conversation_id,
                    "projectId": state.get("project_id"),
                    "threadId": state.get("thread_id"),
                    "currentNode": state.get("current_node"),
                    "slots": json.dumps(state.get("slots", {})),
                    "messages": messages_json,
                    "metadata": json.dumps(state.get("metadata", {})),
                    "isCompleted": state.get("current_node") == "done"
                },
                "update": {
                    "currentNode": state.get("current_node"),
                    "slots": json.dumps(state.get("slots", {})),
                    "messages": messages_json,
                    "metadata": json.dumps(state.get("metadata", {})),
                    "isCompleted": state.get("current_node") == "done",
                    "updatedAt": datetime.now()
                }
            }
        )
        
        return conversation
    
    async def load_conversation_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load conversation state by thread ID.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            Conversation state dictionary or None
        """
        if not self.db:
            await self.connect()
        
        conversation = await self.db.conversationstate.find_first(
            where={
                "threadId": thread_id
            },
            order={
                "updatedAt": "desc"
            }
        )
        
        if not conversation:
            return None
        
        return {
            "conversation_id": conversation.conversationId,
            "project_id": conversation.projectId,
            "thread_id": conversation.threadId,
            "current_node": conversation.currentNode,
            "slots": json.loads(conversation.slots),
            "messages": json.loads(conversation.messages),
            "metadata": json.loads(conversation.metadata) if conversation.metadata else {},
            "next_action": None,
            "error": None
        }
    
    async def save_contract(self, contract_data: Dict[str, Any]) -> Contract:
        """
        Save contract to database.
        
        Args:
            contract_data: Contract data dictionary
            
        Returns:
            Contract model
        """
        if not self.db:
            await self.connect()
        
        slots = contract_data.get("slots", {})
        
        contract = await self.db.contract.create(
            data={
                "conversationId": slots.get("conversation_id", "unknown"),
                "projectId": slots.get("project_id", "unknown"),
                "clientName": slots.get("name"),
                "clientPhone": slots.get("phone"),
                "eventType": slots.get("event_type"),
                "eventDate": slots.get("event_date"),
                "serviceType": slots.get("service_type"),
                "guestCount": slots.get("guest_count"),
                "venue": json.dumps(slots.get("venue", {})),
                "specialRequests": json.dumps(slots.get("special_requests", {})),
                "pricingData": json.dumps(contract_data.get("pricing", {})),
                "upsellsData": json.dumps(contract_data.get("upsells", {})),
                "marginData": json.dumps(contract_data.get("margin", {})),
                "staffingData": json.dumps(contract_data.get("staffing", {})),
                "missingInfoData": json.dumps(contract_data.get("missing_info", {})),
                "status": "draft"
            }
        )
        
        return contract
    
    async def get_contract(self, contract_id: str) -> Optional[Contract]:
        """
        Get contract by ID.
        
        Args:
            contract_id: Contract identifier
            
        Returns:
            Contract model or None
        """
        if not self.db:
            await self.connect()
        
        return await self.db.contract.find_unique(
            where={
                "id": contract_id
            }
        )
    
    async def save_ai_tag(
        self, 
        thread_id: str, 
        message_id: str, 
        field: str,
        old_value: str, 
        new_value: str, 
        field_content: str
    ) -> AiTag:
        """
        Save AI tag modification.
        
        Args:
            thread_id: Thread identifier
            message_id: Message identifier
            field: Field that was modified
            old_value: Previous value
            new_value: New value
            field_content: Original modification text
            
        Returns:
            AiTag model
        """
        if not self.db:
            await self.connect()
        
        tag = await self.db.aitag.create(
            data={
                "threadId": thread_id,
                "messageId": message_id,
                "field": field,
                "oldValue": old_value,
                "newValue": new_value,
                "fieldContent": field_content
            }
        )
        
        return tag
    
    async def save_message(
        self,
        thread_id: str,
        conversation_id: str,
        author_id: str,
        author_type: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> Message:
        """
        Save message to database.
        
        Args:
            thread_id: Thread identifier
            conversation_id: Conversation identifier
            author_id: Author identifier
            author_type: "user" or "agent"
            content: Message content
            metadata: Optional metadata dictionary
            
        Returns:
            Message model
        """
        if not self.db:
            await self.connect()
        
        message = await self.db.message.create(
            data={
                "threadId": thread_id,
                "conversationId": conversation_id,
                "authorId": author_id,
                "authorType": author_type,
                "content": content,
                "metadata": json.dumps(metadata) if metadata else None
            }
        )
        
        return message
    
    async def get_conversation_history(self, thread_id: str) -> list[Message]:
        """
        Get all messages for a thread.
        
        Args:
            thread_id: Thread identifier
            
        Returns:
            List of Message models
        """
        if not self.db:
            await self.connect()
        
        messages = await self.db.message.find_many(
            where={
                "threadId": thread_id
            },
            order={
                "createdAt": "asc"
            }
        )
        
        return messages
    
    async def get_contracts_by_project(self, project_id: str) -> list[Contract]:
        """
        Get all contracts for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            List of Contract models
        """
        if not self.db:
            await self.connect()
        
        contracts = await self.db.contract.find_many(
            where={
                "projectId": project_id
            },
            order={
                "createdAt": "desc"
            }
        )
        
        return contracts
    
    async def update_contract_status(
        self, 
        contract_id: str, 
        status: str,
        pdf_url: Optional[str] = None,
        signed_at: Optional[datetime] = None
    ) -> Contract:
        """
        Update contract status.
        
        Args:
            contract_id: Contract identifier
            status: New status (draft, sent, signed, cancelled)
            pdf_url: Optional PDF URL
            signed_at: Optional signature timestamp
            
        Returns:
            Updated Contract model
        """
        if not self.db:
            await self.connect()
        
        update_data = {
            "status": status,
            "updatedAt": datetime.now()
        }
        
        if pdf_url:
            update_data["pdfUrl"] = pdf_url
        
        if signed_at:
            update_data["signedAt"] = signed_at
        
        contract = await self.db.contract.update(
            where={
                "id": contract_id
            },
            data=update_data
        )
        
        return contract


# Convenience function
async def get_database_manager() -> PrismaDatabaseManager:
    """
    Get database manager instance.
    
    Returns:
        PrismaDatabaseManager instance
    """
    manager = PrismaDatabaseManager()
    await manager.connect()
    return manager


if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("Testing Prisma Client Python connection...")
        
        try:
            manager = await get_database_manager()
            print("✓ Connected to database successfully!")
            
            # Test query
            conversations = await manager.db.conversationstate.find_many(take=5)
            print(f"✓ Found {len(conversations)} conversations")
            
            await manager.disconnect()
            print("✓ Disconnected successfully")
            
        except Exception as e:
            print(f"✗ Error: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(test())
