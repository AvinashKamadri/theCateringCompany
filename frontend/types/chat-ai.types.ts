/**
 * Types for AI Chat API Integration
 * Based on: CHAT_API_INTEGRATION_GUIDE.md
 * ML API Endpoint: http://localhost:8000/chat
 */

export interface ChatRequest {
  /** Conversation thread ID. Omit for new conversations */
  thread_id?: string;
  /** User's message to the AI agent (required) */
  message: string;
  /** User ID (optional) */
  author_id?: string;
  /** Project ID for organizing conversations (optional) */
  project_id?: string;
}

export interface ChatResponse {
  /** Conversation thread ID (use in subsequent requests) */
  thread_id: string;
  /** AI agent's response message */
  message: string;
  /** Current conversation node (e.g., "collect_name", "collect_date", "final") */
  current_node: string;
  /** Number of data points collected (0-16) */
  slots_filled: number;
  /** Total slots to collect (always 16) */
  total_slots: number;
  /** True when all information is collected */
  is_complete: boolean;
  /** Structured contract data (only when is_complete: true) */
  contract_data?: ContractData;
}

export interface ContractData {
  client_name: string;
  contact_email: string;
  contact_phone: string;
  event_type: string;
  event_date: string; // YYYY-MM-DD
  guest_count: number;
  service_type: string;
  menu_items: string[];
  dietary_restrictions: string[];
  budget_range: string;
  venue_name: string;
  venue_address: string;
  setup_time: string; // HH:MM
  service_time: string; // HH:MM
  addons: string[];
  modifications: string[];
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
}

export interface ChatState {
  messages: ChatMessage[];
  threadId?: string;
  isLoading: boolean;
  error?: string;
  progress: {
    filled: number;
    total: number;
  };
  isComplete: boolean;
  contractData?: ContractData;
}
