"use client";

import { useState, useEffect, useRef } from 'react';
import { Send, Loader2, CheckCircle2, Circle, Sparkles } from 'lucide-react';
import { chatAiApi } from '@/lib/api/chat-ai';
import type { ChatMessage, ChatState, ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { CommandDialog } from './command-dialog';
import { ChatSidebar } from './chat-sidebar';

interface AiChatProps {
  projectId?: string;
  authorId?: string;
  onComplete?: (contractData: ContractData) => void;
}

export function AiChat({ projectId, authorId, onComplete }: AiChatProps) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    progress: { filled: 0, total: 16 },
    isComplete: false,
  });
  const [input, setInput] = useState('');
  const [commandDialog, setCommandDialog] = useState<{ isOpen: boolean; command: 'menu' | 'events' | null }>({
    isOpen: false,
    command: null,
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages]);

  // Start conversation on mount
  useEffect(() => {
    handleSendMessage('Hello! I need help planning my event.');
  }, []);

  // Listen for help requests from sidebar
  useEffect(() => {
    const handleHelp = () => {
      handleSendMessage('/help - I need assistance from your team');
    };
    window.addEventListener('chat:help', handleHelp);
    return () => window.removeEventListener('chat:help', handleHelp);
  }, []);

  const handleSendMessage = async (messageText?: string) => {
    const content = messageText || input.trim();
    if (!content || state.isLoading) return;

    // Check for commands
    if (content.startsWith('/')) {
      const command = content.toLowerCase();
      if (command.startsWith('/menu')) {
        setCommandDialog({ isOpen: true, command: 'menu' });
        setInput('');
        return;
      }
      if (command.startsWith('/event')) {
        setCommandDialog({ isOpen: true, command: 'events' });
        setInput('');
        return;
      }
      if (command.startsWith('/help')) {
        // Send help request message
        toast.success('Help request sent! Our team will assist you shortly.');
      }
    }

    // Clear input
    setInput('');

    // Add user message to UI
    const userMessage: ChatMessage = {
      role: 'user',
      content,
      timestamp: new Date(),
    };

    setState((prev) => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      error: undefined,
    }));

    try {
      // Send to ML API
      const response = await chatAiApi.sendMessageWithRetry({
        message: content,
        threadId: state.threadId,
        projectId,
        authorId,
      });

      // Add AI response to UI
      const aiMessage: ChatMessage = {
        role: 'ai',
        content: response.message,
        timestamp: new Date(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, aiMessage],
        threadId: response.thread_id,
        progress: {
          filled: response.slots_filled,
          total: response.total_slots,
        },
        isComplete: response.is_complete,
        isLoading: false,
      }));

      // Handle completion — fetch full slot data from conversation endpoint
      if (response.is_complete) {
        toast.success('Event details collected! Saving your project...');
        try {
          const conversation = await chatAiApi.getConversation(response.thread_id);
          const slots = { ...conversation.slots, thread_id: response.thread_id };
          setState((prev) => ({ ...prev, contractData: slots }));
          onComplete?.(slots);
        } catch (err) {
          console.error('Failed to fetch conversation slots:', err);
          toast.error('Could not retrieve event details. Please try again.');
        }
      }
    } catch (error: any) {
      console.error('Failed to send message:', error);
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to send message. Please try again.',
      }));
      toast.error('Failed to send message');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const progressPercentage = (state.progress.filled / state.progress.total) * 100;

  const handleCommandSelect = (selectedOption: string) => {
    // Send the selected option as a message
    handleSendMessage(`I'm interested in ${selectedOption}`);
  };

  return (
    <>
      <CommandDialog
        isOpen={commandDialog.isOpen}
        command={commandDialog.command}
        onClose={() => setCommandDialog({ isOpen: false, command: null })}
        onSelect={handleCommandSelect}
      />
      <ChatSidebar
        contractData={state.contractData}
        slotsFilled={state.progress.filled}
        totalSlots={state.progress.total}
      />
      <div className="flex flex-col h-full bg-white">
      {/* Header with Progress */}
      <div className="border-b border-gray-200 px-6 py-4 bg-gradient-to-r from-blue-50 to-purple-50">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">
              TheCateringCompany
            </h2>
            <p className="text-sm text-gray-600">
              Let's plan your perfect event together
            </p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-600 font-medium">
              {state.isComplete ? 'All details collected!' : 'Gathering event details'}
            </span>
            <span className="text-gray-900 font-semibold">
              {state.progress.filled} / {state.progress.total}
            </span>
          </div>
          <div className="relative h-2 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {state.messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
              <span
                className={`text-xs mt-1 block ${
                  msg.role === 'user' ? 'text-blue-100' : 'text-gray-500'
                }`}
              >
                {msg.timestamp.toLocaleTimeString([], {
                  hour: '2-digit',
                  minute: '2-digit',
                })}
              </span>
            </div>
          </div>
        ))}

        {/* Loading Indicator */}
        {state.isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl px-4 py-3">
              <Loader2 className="w-5 h-5 text-gray-600 animate-spin" />
            </div>
          </div>
        )}

        {/* Error Message */}
        {state.error && (
          <div className="flex justify-center">
            <div className="bg-red-50 text-red-600 rounded-lg px-4 py-2 text-sm">
              {state.error}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Contract Summary (shown when complete) */}
      {state.isComplete && state.contractData && (
        <div className="border-t border-gray-200 bg-green-50 px-6 py-4">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <h3 className="font-semibold text-green-900 mb-2">Event Summary</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-green-700 font-medium">Client:</span>
                  <span className="text-green-900 ml-2">{state.contractData.client_name}</span>
                </div>
                <div>
                  <span className="text-green-700 font-medium">Event:</span>
                  <span className="text-green-900 ml-2">{state.contractData.event_type}</span>
                </div>
                <div>
                  <span className="text-green-700 font-medium">Date:</span>
                  <span className="text-green-900 ml-2">{state.contractData.event_date}</span>
                </div>
                <div>
                  <span className="text-green-700 font-medium">Guests:</span>
                  <span className="text-green-900 ml-2">{state.contractData.guest_count}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      {!state.isComplete && (
        <div className="border-t border-gray-200 px-6 py-4 bg-white">
          {/* Show "Generate Contract Now" button if enough data collected */}
          {state.progress.filled >= 8 && state.contractData && (
            <div className="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-xl">
              <div className="flex items-center justify-between">
                <div className="flex-1">
                  <p className="text-sm font-medium text-blue-900">
                    Have enough details to generate contract
                  </p>
                  <p className="text-xs text-blue-600 mt-0.5">
                    {state.progress.filled}/{state.progress.total} slots filled
                  </p>
                </div>
                <button
                  onClick={() => onComplete?.(state.contractData!)}
                  className="ml-3 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-blue-700 transition-all whitespace-nowrap"
                >
                  Generate Contract
                </button>
              </div>
            </div>
          )}

          <div className="flex items-end gap-3">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type your message..."
              className="flex-1 resize-none border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[52px] max-h-[120px]"
              rows={1}
              disabled={state.isLoading}
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={!input.trim() || state.isLoading}
              className="bg-gradient-to-br from-blue-500 to-purple-600 text-white p-3 rounded-xl hover:from-blue-600 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex-shrink-0"
            >
              {state.isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-5 h-5" />
              )}
            </button>
          </div>
          <div className="flex items-center justify-between mt-2">
            <p className="text-xs text-gray-500">
              Press Enter to send, Shift+Enter for new line
            </p>
            <p className="text-xs text-gray-400">
              Try: <span className="text-blue-600 font-mono">/menu</span>{' '}
              <span className="text-blue-600 font-mono">/events</span>{' '}
              <span className="text-blue-600 font-mono">/help</span>
            </p>
          </div>
        </div>
      )}

      {/* Complete CTA */}
      {state.isComplete && (
        <div className="border-t border-gray-200 px-6 py-4 bg-white">
          <button
            onClick={() => onComplete?.(state.contractData!)}
            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 text-white py-3 rounded-xl font-semibold hover:from-green-600 hover:to-emerald-700 transition-all"
          >
            Review & Create Project
          </button>
        </div>
      )}
    </div>
    </>
  );
}
