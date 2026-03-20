/**
 * Types for AI Chat API Integration
 * Based on Desktop TheCateringCompany ML Agent API
 * ML API Endpoint: http://localhost:8000/chat
 */

export interface ChatRequest {
  thread_id?: string;
  message: string;
  author_id?: string;
  project_id?: string;
  user_id?: string;
}

export interface ChatResponse {
  thread_id: string;
  project_id?: string;
  message: string;
  current_node: string;
  slots_filled: number;
  total_slots: number;
  is_complete: boolean;
  /** ML-internal contract ID (Desktop agent saves to its own DB) */
  contract_id?: string | null;
  /** Full contract data dict (TheCateringCompanyAgent format, if present) */
  contract_data?: Record<string, any> | null;
}

/**
 * Filled slot values from GET /conversation/{thread_id}
 * Matches the Desktop TheCateringCompany SLOT_NAMES
 */
export interface ContractData {
  // Basic info
  name: string;
  event_date: string;        // YYYY-MM-DD
  service_type: string;      // drop-off | on-site
  event_type: string;        // Wedding | Corporate | Birthday | Social | Custom
  venue: string;
  guest_count: number | string;
  service_style?: string;    // cocktail hour | reception | both
  // Menu — ML agent returns these as comma-separated strings (e.g. "Chicken Tikka, Pasta")
  selected_dishes?: string | string[];
  appetizers?: string | string[];
  menu_notes?: string;
  // Add-ons
  utensils?: string;
  desserts?: string;
  rentals?: string;
  florals?: string;
  // Final details
  special_requests?: string;
  dietary_concerns?: string;
  additional_notes?: string;
  // Carry the thread_id so the page can pass it downstream if needed
  thread_id?: string;
}

/** Full conversation state from GET /conversation/{thread_id} */
export interface ConversationState {
  thread_id: string;
  project_id: string;
  current_node: string;
  is_completed: boolean;
  slots_filled: number;
  slots: ContractData;
  messages: Array<{ sender_type: 'user' | 'ai'; content: string }>;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
}

export interface ChatState {
  messages: ChatMessage[];
  threadId?: string;
  projectId?: string;
  isLoading: boolean;
  error?: string;
  progress: {
    filled: number;
    total: number;
  };
  isComplete: boolean;
  contractData?: ContractData;
}
