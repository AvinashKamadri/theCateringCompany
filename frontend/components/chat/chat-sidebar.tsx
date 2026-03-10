"use client";

import { Calendar, MapPin, Users, FileText, DollarSign } from 'lucide-react';

interface ChatSidebarProps {
  projectData?: {
    name: string;
    event_type: string;
    event_date: string;
    guest_count: number;
    venue_name?: string;
    budget?: number;
    contract_status?: string;
  };
}

export function ChatSidebar({ projectData }: ChatSidebarProps) {
  if (!projectData) {
    return (
      <div className="w-80 border-l border-gray-200 bg-gray-50 p-6">
        <p className="text-sm text-gray-500">No project selected</p>
      </div>
    );
  }

  return (
    <div className="w-80 border-l border-gray-200 bg-gray-50 overflow-y-auto">
      <div className="p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Event Details</h2>

        <div className="space-y-4">
          {/* Event Type */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <FileText className="h-4 w-4" />
              <span>Event Type</span>
            </div>
            <p className="text-sm font-medium text-gray-900 capitalize">{projectData.event_type}</p>
          </div>

          {/* Event Date */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Calendar className="h-4 w-4" />
              <span>Event Date</span>
            </div>
            <p className="text-sm font-medium text-gray-900">
              {new Date(projectData.event_date).toLocaleDateString('en-US', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>

          {/* Guest Count */}
          <div className="bg-white rounded-lg p-4 border border-gray-200">
            <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
              <Users className="h-4 w-4" />
              <span>Guest Count</span>
            </div>
            <p className="text-sm font-medium text-gray-900">{projectData.guest_count} guests</p>
          </div>

          {/* Venue */}
          {projectData.venue_name && (
            <div className="bg-white rounded-lg p-4 border border-gray-200">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <MapPin className="h-4 w-4" />
                <span>Venue</span>
              </div>
              <p className="text-sm font-medium text-gray-900">{projectData.venue_name}</p>
            </div>
          )}

          {/* Budget */}
          {projectData.budget && (
            <div className="bg-white rounded-lg p-4 border border-gray-200">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <DollarSign className="h-4 w-4" />
                <span>Budget</span>
              </div>
              <p className="text-sm font-medium text-gray-900">
                ${projectData.budget.toLocaleString()}
              </p>
            </div>
          )}

          {/* Contract Status */}
          {projectData.contract_status && (
            <div className="bg-white rounded-lg p-4 border border-gray-200">
              <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
                <FileText className="h-4 w-4" />
                <span>Contract Status</span>
              </div>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  projectData.contract_status === 'signed'
                    ? 'bg-green-100 text-green-800'
                    : projectData.contract_status === 'sent'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-800'
                }`}
              >
                {projectData.contract_status}
              </span>
            </div>
          )}
        </div>

        {/* Additional info section */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <h3 className="text-sm font-medium text-gray-900 mb-3">Quick Actions</h3>
          <div className="space-y-2">
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-white rounded-lg transition">
              View Contract
            </button>
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-white rounded-lg transition">
              View Menu
            </button>
            <button className="w-full text-left px-3 py-2 text-sm text-gray-700 hover:bg-white rounded-lg transition">
              View Timeline
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
