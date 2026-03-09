"use client";

import { useState } from 'react';
import {
  Users,
  TrendingUp,
  DollarSign,
  Calendar,
  Phone,
  Mail,
  MapPin,
  AlertTriangle,
  Star,
  Plus,
} from 'lucide-react';
import { cn } from '@/lib/utils';

type PipelineStage = 'inquiry' | 'qualified' | 'proposal_sent' | 'negotiation' | 'won' | 'lost';

interface Lead {
  id: string;
  name: string;
  email: string;
  phone: string;
  company?: string;
  event_type: string;
  event_date: string;
  guest_count: number;
  budget?: number;
  stage: PipelineStage;
  score: number; // 0-100
  risk_level: 'low' | 'medium' | 'high';
  created_at: string;
  last_contact: string;
}

// Mock data
const mockLeads: Lead[] = [
  {
    id: '1',
    name: 'Sarah Johnson',
    email: 'sarah.j@example.com',
    phone: '(555) 123-4567',
    company: 'Tech Corp',
    event_type: 'corporate',
    event_date: '2026-05-15',
    guest_count: 200,
    budget: 15000,
    stage: 'proposal_sent',
    score: 85,
    risk_level: 'low',
    created_at: '2026-03-01',
    last_contact: '2026-03-07',
  },
  {
    id: '2',
    name: 'Michael Chen',
    email: 'm.chen@weddings.com',
    phone: '(555) 234-5678',
    event_type: 'wedding',
    event_date: '2026-07-20',
    guest_count: 150,
    budget: 25000,
    stage: 'negotiation',
    score: 92,
    risk_level: 'low',
    created_at: '2026-02-28',
    last_contact: '2026-03-08',
  },
  {
    id: '3',
    name: 'Emily Davis',
    email: 'emily.d@example.com',
    phone: '(555) 345-6789',
    event_type: 'birthday',
    event_date: '2026-04-10',
    guest_count: 50,
    budget: 5000,
    stage: 'qualified',
    score: 65,
    risk_level: 'medium',
    created_at: '2026-03-05',
    last_contact: '2026-03-06',
  },
];

const stageConfig = {
  inquiry: { label: 'Inquiry', color: 'bg-gray-100 text-gray-700', order: 0 },
  qualified: { label: 'Qualified', color: 'bg-blue-100 text-blue-700', order: 1 },
  proposal_sent: { label: 'Proposal Sent', color: 'bg-purple-100 text-purple-700', order: 2 },
  negotiation: { label: 'Negotiation', color: 'bg-yellow-100 text-yellow-700', order: 3 },
  won: { label: 'Won', color: 'bg-green-100 text-green-700', order: 4 },
  lost: { label: 'Lost', color: 'bg-red-100 text-red-700', order: 5 },
};

export default function CRMPage() {
  const [leads] = useState<Lead[]>(mockLeads);
  const [viewMode, setViewMode] = useState<'pipeline' | 'list'>('pipeline');

  const stats = {
    totalLeads: leads.length,
    qualified: leads.filter((l) => l.stage !== 'inquiry' && l.stage !== 'lost').length,
    totalValue: leads.reduce((sum, l) => sum + (l.budget || 0), 0),
    avgScore: Math.round(leads.reduce((sum, l) => sum + l.score, 0) / leads.length),
  };

  const getLeadsByStage = (stage: PipelineStage) => {
    return leads.filter((l) => l.stage === stage);
  };

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return 'text-green-600 bg-green-100';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100';
      case 'high':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">CRM Dashboard</h1>
              <p className="text-sm text-gray-500 mt-1">Manage leads and track your pipeline</p>
            </div>
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
              <Plus className="h-5 w-5" />
              New Lead
            </button>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-4 gap-4 mt-6">
            <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-600 rounded-lg">
                  <Users className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Total Leads</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.totalLeads}</p>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-600 rounded-lg">
                  <TrendingUp className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Qualified</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.qualified}</p>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-purple-600 rounded-lg">
                  <DollarSign className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Pipeline Value</p>
                  <p className="text-2xl font-bold text-gray-900">
                    ${(stats.totalValue / 1000).toFixed(0)}K
                  </p>
                </div>
              </div>
            </div>

            <div className="bg-gradient-to-br from-yellow-50 to-yellow-100 rounded-lg p-4">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-yellow-600 rounded-lg">
                  <Star className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm text-gray-600">Avg Score</p>
                  <p className="text-2xl font-bold text-gray-900">{stats.avgScore}</p>
                </div>
              </div>
            </div>
          </div>

          {/* View Mode Toggle */}
          <div className="flex gap-2 mt-6">
            <button
              onClick={() => setViewMode('pipeline')}
              className={cn(
                'px-4 py-2 rounded-lg transition',
                viewMode === 'pipeline'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              Pipeline View
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'px-4 py-2 rounded-lg transition',
                viewMode === 'list'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              List View
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        {viewMode === 'pipeline' ? (
          /* Pipeline View */
          <div className="grid grid-cols-6 gap-4">
            {(Object.keys(stageConfig) as PipelineStage[])
              .sort((a, b) => stageConfig[a].order - stageConfig[b].order)
              .map((stage) => {
                const stageLeads = getLeadsByStage(stage);
                const stageValue = stageLeads.reduce((sum, l) => sum + (l.budget || 0), 0);

                return (
                  <div key={stage} className="bg-gray-100 rounded-lg p-4">
                    <div className="mb-4">
                      <h3 className="font-semibold text-gray-900">{stageConfig[stage].label}</h3>
                      <p className="text-xs text-gray-500 mt-1">
                        {stageLeads.length} leads • ${(stageValue / 1000).toFixed(0)}K
                      </p>
                    </div>

                    <div className="space-y-3">
                      {stageLeads.map((lead) => (
                        <div key={lead.id} className="bg-white rounded-lg p-3 shadow-sm border border-gray-200">
                          <div className="flex items-start justify-between mb-2">
                            <h4 className="font-medium text-sm text-gray-900">{lead.name}</h4>
                            <div className="flex items-center gap-1">
                              <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                              <span className="text-xs text-gray-600">{lead.score}</span>
                            </div>
                          </div>

                          <div className="space-y-1">
                            <p className="text-xs text-gray-600 capitalize">{lead.event_type}</p>
                            <p className="text-xs text-gray-500">{lead.guest_count} guests</p>
                            {lead.budget && (
                              <p className="text-xs font-medium text-gray-900">
                                ${lead.budget.toLocaleString()}
                              </p>
                            )}
                          </div>

                          {lead.risk_level !== 'low' && (
                            <div className="mt-2">
                              <span
                                className={cn(
                                  'inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium',
                                  getRiskColor(lead.risk_level)
                                )}
                              >
                                <AlertTriangle className="h-3 w-3" />
                                {lead.risk_level} risk
                              </span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
          </div>
        ) : (
          /* List View */
          <div className="bg-white rounded-lg border border-gray-200">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Lead
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Event
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Stage
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Score
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Value
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Risk
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {leads.map((lead) => (
                  <tr key={lead.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div>
                        <p className="font-medium text-gray-900">{lead.name}</p>
                        <div className="flex items-center gap-3 mt-1">
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Mail className="h-3 w-3" />
                            {lead.email}
                          </span>
                          <span className="text-xs text-gray-500 flex items-center gap-1">
                            <Phone className="h-3 w-3" />
                            {lead.phone}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm text-gray-900 capitalize">{lead.event_type}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          {new Date(lead.event_date).toLocaleDateString()}
                        </span>
                        <span className="text-xs text-gray-500 flex items-center gap-1">
                          <Users className="h-3 w-3" />
                          {lead.guest_count}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={cn(
                          'inline-flex px-2 py-1 rounded-full text-xs font-medium',
                          stageConfig[lead.stage].color
                        )}
                      >
                        {stageConfig[lead.stage].label}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full"
                            style={{ width: `${lead.score}%` }}
                          />
                        </div>
                        <span className="text-sm text-gray-600">{lead.score}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <p className="text-sm font-medium text-gray-900">
                        {lead.budget ? `$${lead.budget.toLocaleString()}` : '-'}
                      </p>
                    </td>
                    <td className="px-6 py-4">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium',
                          getRiskColor(lead.risk_level)
                        )}
                      >
                        {lead.risk_level !== 'low' && <AlertTriangle className="h-3 w-3" />}
                        {lead.risk_level}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
