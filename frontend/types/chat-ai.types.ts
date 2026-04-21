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

export interface InputHint {
  type: 'options' | 'date' | 'menu_picker';
  category?: string;
  options?: Array<{ value: string; label?: string }>;
  menu?: Array<{
    category: string;
    items: Array<{
      name: string;
      unit_price?: number;
      price_type?: string;
      description?: string;
    }>;
  }>;
  items?: Array<{
    name: string;
    unit_price?: number;
    price_type?: string;
    description?: string;
  }>;
  multi?: boolean;
  allow_text?: boolean;
  max_select?: number;
}

export interface ChatResponse {
  thread_id: string;
  project_id?: string;
  message: string;
  current_node: string;
  slots_filled: number;
  total_slots: number;
  is_complete: boolean;
  input_hint?: InputHint | null;
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
  email?: string;
  phone?: string;
  event_date: string;
  service_type: string;
  event_type: string;
  venue: string;
  guest_count: number | string;
  partner_name?: string;
  company_name?: string;
  honoree_name?: string;
  service_style?: string;
  cocktail_hour?: boolean | string;

  // Menu
  meal_style?: string;
  appetizer_style?: string;
  selected_dishes?: string | string[];
  appetizers?: string | string[];
  desserts?: string | string[];
  wedding_cake?: string;
  custom_menu?: string;
  menu_notes?: string;

  // Add-ons
  drinks?: boolean | string;
  bar_service?: boolean | string;
  bar_package?: string;
  bartender?: boolean | string;
  coffee_service?: boolean | string;
  tableware?: string;
  utensils?: string;
  linens?: boolean | string;
  rentals?: string | string[];
  florals?: string;
  labor_ceremony_setup?: boolean | string;
  labor_table_setup?: boolean | string;
  labor_table_preset?: boolean | string;
  labor_cleanup?: boolean | string;
  labor_trash?: boolean | string;
  travel_fee?: string;

  // Final details
  special_requests?: string;
  dietary_concerns?: string;
  additional_notes?: string;
  followup_call_requested?: boolean | string;

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
  messages: Array<{
    sender_type: 'user' | 'ai';
    content: string;
    author_id?: string;
    created_at?: string;
  }>;
}

export interface ChatMessage {
  role: 'user' | 'ai';
  content: string;
  timestamp: Date;
  inputHint?: InputHint | null;
  authorId?: string;
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
