"use client";

import { useState } from 'react';
import { Bot, Users, Sparkles } from 'lucide-react';
import { AiChat } from './ai-chat';
import type { ContractData } from '@/types/chat-ai.types';

interface AiAssistantToggleProps {
  projectId: string;
  onComplete?: (contractData: ContractData) => void;
  children: React.ReactNode; // Regular chat UI
}

export function AiAssistantToggle({ projectId, onComplete, children }: AiAssistantToggleProps) {
  const [mode, setMode] = useState<'team' | 'ai'>('team');

  return (
    <div className="h-full flex flex-col">
      {/* Mode Selector */}
      <div className="border-b border-gray-200 bg-white px-4 py-3">
        <div className="inline-flex rounded-lg border border-gray-300 p-1 bg-gray-50">
          <button
            onClick={() => setMode('team')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'team'
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Users className="w-4 h-4" />
            Team Chat
          </button>
          <button
            onClick={() => setMode('ai')}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'ai'
                ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            AI Assistant
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {mode === 'team' ? (
          children
        ) : (
          <AiChat projectId={projectId} onComplete={onComplete} />
        )}
      </div>
    </div>
  );
}
