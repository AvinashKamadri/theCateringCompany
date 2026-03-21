"use client";

import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send } from 'lucide-react';
import type { Collaborator } from '@/types/messages.types';
import { cn } from '@/lib/utils';

interface MessageInputProps {
  onSendMessage: (content: string, mentionedUserIds: string[]) => void;
  collaborators: Collaborator[];
  onTyping?: () => void;
  disabled?: boolean;
}

interface MentionSuggestion extends Collaborator {
  index: number;
}

export function MessageInput({
  onSendMessage,
  collaborators,
  onTyping,
  disabled,
}: MessageInputProps) {
  const [content, setContent] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [selectedMentionIndex, setSelectedMentionIndex] = useState(0);
  const [mentionedUsers, setMentionedUsers] = useState<string[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | undefined>(undefined);

  const filteredCollaborators = collaborators.filter((c) =>
    c.email.toLowerCase().includes(mentionFilter.toLowerCase())
  );

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  }, [content]);

  const handleContentChange = (value: string) => {
    setContent(value);

    // Trigger typing indicator
    if (onTyping) {
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
      onTyping();
      typingTimeoutRef.current = setTimeout(() => {
        // Stop typing indicator after 3 seconds
      }, 3000);
    }

    // Check for @ mention trigger
    const cursorPos = textareaRef.current?.selectionStart || 0;
    const textBeforeCursor = value.substring(0, cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    if (lastAtIndex !== -1 && lastAtIndex === cursorPos - 1) {
      setShowMentions(true);
      setMentionFilter('');
      setSelectedMentionIndex(0);
    } else if (lastAtIndex !== -1 && cursorPos > lastAtIndex) {
      const textAfterAt = textBeforeCursor.substring(lastAtIndex + 1);
      if (textAfterAt.includes(' ') || textAfterAt.includes('\n')) {
        setShowMentions(false);
      } else {
        setShowMentions(true);
        setMentionFilter(textAfterAt);
      }
    } else {
      setShowMentions(false);
    }
  };

  const insertMention = (collaborator: Collaborator) => {
    const cursorPos = textareaRef.current?.selectionStart || 0;
    const textBeforeCursor = content.substring(0, cursorPos);
    const textAfterCursor = content.substring(cursorPos);
    const lastAtIndex = textBeforeCursor.lastIndexOf('@');

    const newContent =
      textBeforeCursor.substring(0, lastAtIndex) +
      `@[${collaborator.id}:${collaborator.email}] ` +
      textAfterCursor;

    setContent(newContent);
    setShowMentions(false);
    setMentionFilter('');

    // Add to mentioned users
    if (!mentionedUsers.includes(collaborator.id)) {
      setMentionedUsers([...mentionedUsers, collaborator.id]);
    }

    // Focus back on textarea
    setTimeout(() => {
      textareaRef.current?.focus();
    }, 0);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (showMentions && filteredCollaborators.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedMentionIndex((prev) =>
          prev < filteredCollaborators.length - 1 ? prev + 1 : prev
        );
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedMentionIndex((prev) => (prev > 0 ? prev - 1 : 0));
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        insertMention(filteredCollaborators[selectedMentionIndex]);
      } else if (e.key === 'Escape') {
        setShowMentions(false);
      }
    } else if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSend = () => {
    if (content.trim() && !disabled) {
      onSendMessage(content, mentionedUsers);
      setContent('');
      setMentionedUsers([]);
    }
  };

  return (
    <div className="relative border-t border-gray-200 bg-white p-4">
      {/* Mention suggestions dropdown */}
      {showMentions && filteredCollaborators.length > 0 && (
        <div className="absolute bottom-full left-4 right-4 mb-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-48 overflow-y-auto">
          {filteredCollaborators.map((collaborator, index) => (
            <button
              key={collaborator.id}
              type="button"
              onClick={() => insertMention(collaborator)}
              className={cn(
                'w-full px-4 py-2 text-left hover:bg-gray-100 flex items-center gap-2',
                index === selectedMentionIndex && 'bg-blue-50'
              )}
            >
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center text-sm font-medium">
                {collaborator.email[0].toUpperCase()}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-gray-900">{collaborator.email}</div>
                <div className="text-xs text-gray-500">{collaborator.role}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      <div className="flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => handleContentChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... (use @ to mention)"
          disabled={disabled}
          rows={1}
          className="flex-1 resize-none rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed min-h-[40px] max-h-[120px]"
        />
        <button
          onClick={handleSend}
          disabled={!content.trim() || disabled}
          className="flex items-center justify-center w-10 h-10 rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
        >
          <Send className="h-5 w-5" />
        </button>
      </div>

      <p className="text-xs text-gray-500 mt-2">
        Press <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-xs">Enter</kbd> to send,{' '}
        <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-xs">Shift+Enter</kbd> for new line
      </p>
    </div>
  );
}
