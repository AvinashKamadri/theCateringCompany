"use client";

import { useState } from 'react';
import Link from 'next/link';
import {
  ChevronLeft,
  FolderKanban,
  Users,
  CheckCircle2,
  Circle,
  UtensilsCrossed,
  HelpCircle,
  Lightbulb,
} from 'lucide-react';
import type { ContractData } from '@/types/chat-ai.types';

interface ChatSidebarProps {
  contractData?: Partial<ContractData>;
  slotsFilled: number;
  totalSlots: number;
}

const FIELD_LABELS: Record<string, string> = {
  name:             'Client Name',
  event_date:       'Event Date',
  service_type:     'Service Type',
  event_type:       'Event Type',
  venue:            'Venue',
  guest_count:      'Guest Count',
  service_style:    'Service Style',
  selected_dishes:  'Menu Selection',
  appetizers:       'Appetizers',
  menu_notes:       'Menu Notes',
  utensils:         'Utensils',
  desserts:         'Desserts',
  rentals:          'Rentals',
  florals:          'Florals',
  special_requests: 'Special Requests',
  dietary_concerns: 'Dietary Concerns',
  additional_notes: 'Additional Notes',
};

export function ChatSidebar({ contractData, slotsFilled, totalSlots }: ChatSidebarProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Determine which fields are filled
  const filledFields = contractData
    ? Object.keys(contractData).filter((key) => {
        const value = contractData[key as keyof typeof contractData];
        return value !== undefined && value !== null && value !== '';
      })
    : [];

  const recommendedFields = Object.keys(FIELD_LABELS)
    .filter((key) => !filledFields.includes(key))
    .slice(0, 3);

  return (
    <>
      {/* Hover trigger area */}
      <div
        className="fixed right-0 top-0 bottom-0 w-4 z-40 hover:bg-blue-500/5 transition"
        onMouseEnter={() => setIsExpanded(true)}
      />

      {/* Sidebar */}
      <div
        className={`fixed right-0 top-0 bottom-0 bg-white border-l border-gray-200 shadow-2xl z-50 transition-transform duration-300 ease-in-out ${
          isExpanded ? 'translate-x-0' : 'translate-x-full'
        }`}
        style={{ width: '320px' }}
        onMouseLeave={() => setIsExpanded(false)}
      >
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-500 to-purple-600 p-4 flex items-center justify-between">
          <h3 className="text-white font-semibold">Event Details</h3>
          <button
            onClick={() => setIsExpanded(false)}
            className="text-white/80 hover:text-white transition"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto h-full pb-4">
          {/* Progress Section */}
          <div className="p-4 border-b border-gray-200">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-700">Contract Progress</span>
              <span className="text-sm font-semibold text-gray-900">
                {slotsFilled} / {totalSlots}
              </span>
            </div>
            <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-purple-600 transition-all duration-500"
                style={{ width: `${(slotsFilled / totalSlots) * 100}%` }}
              />
            </div>
          </div>

          {/* Filled Fields */}
          {filledFields.length > 0 && (
            <div className="p-4 border-b border-gray-200">
              <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600" />
                Information Collected
              </h4>
              <div className="space-y-2">
                {filledFields.slice(0, 5).map((field) => (
                  <div key={field} className="flex items-start gap-2 text-sm">
                    <CheckCircle2 className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{FIELD_LABELS[field] || field}</span>
                  </div>
                ))}
                {filledFields.length > 5 && (
                  <p className="text-xs text-gray-500 pl-6">
                    +{filledFields.length - 5} more fields
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Recommended to Answer */}
          {recommendedFields.length > 0 && (
            <div className="p-4 border-b border-gray-200">
              <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
                <Lightbulb className="w-4 h-4 text-amber-500" />
                Recommended to Answer
              </h4>
              <div className="space-y-2">
                {recommendedFields.map((field) => (
                  <div key={field} className="flex items-start gap-2 text-sm">
                    <Circle className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-600">{FIELD_LABELS[field] || field}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="p-4 border-b border-gray-200">
            <h4 className="text-sm font-semibold text-gray-900 mb-3">Quick Actions</h4>
            <div className="space-y-2">
              <Link
                href="/menu"
                className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition text-sm group"
              >
                <UtensilsCrossed className="w-4 h-4 text-gray-600 group-hover:text-blue-600" />
                <span className="text-gray-700 group-hover:text-blue-600 font-medium">
                  Browse Menu
                </span>
              </Link>
              <button
                className="w-full flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition text-sm group"
                onClick={() => {
                  // This will be handled by the chat component
                  window.dispatchEvent(new CustomEvent('chat:help'));
                }}
              >
                <HelpCircle className="w-4 h-4 text-gray-600 group-hover:text-blue-600" />
                <span className="text-gray-700 group-hover:text-blue-600 font-medium">
                  Request Help
                </span>
              </button>
            </div>
          </div>

          {/* Projects (Placeholder) */}
          <div className="p-4 border-b border-gray-200">
            <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <FolderKanban className="w-4 h-4" />
              Recent Projects
            </h4>
            <p className="text-xs text-gray-500">No projects yet</p>
          </div>

          {/* Collaborators (Placeholder) */}
          <div className="p-4">
            <h4 className="text-sm font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Users className="w-4 h-4" />
              Collaborators
            </h4>
            <div className="flex -space-x-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-semibold ring-2 ring-white">
                AI
              </div>
            </div>
            <p className="text-xs text-gray-500 mt-2">AI Assistant helping you</p>
          </div>
        </div>
      </div>
    </>
  );
}
