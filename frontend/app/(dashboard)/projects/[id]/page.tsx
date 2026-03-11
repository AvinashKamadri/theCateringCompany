"use client";

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api/client';
import { toast } from 'sonner';
import { Calendar, Users, MapPin, FileText, MessageSquare, Loader2, ArrowLeft } from 'lucide-react';

interface Contract {
  id: string;
  status: string;
  title: string;
  body: any;
  total_amount: number | null;
  created_at: string;
  version_number: number;
}

interface Project {
  id: string;
  title: string;
  event_date: string | null;
  event_end_date: string | null;
  guest_count: number | null;
  status: string;
  ai_event_summary: any;
  venue_id: string | null;
  created_at: string;
  updated_at: string;
  latestActiveContract: Contract | null;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchProject();
  }, [projectId]);

  const fetchProject = async () => {
    try {
      setLoading(true);
      console.log('🔍 Fetching project:', projectId);

      const data = await apiClient.get(`/projects/${projectId}`);
      console.log('✅ Project loaded:', data);
      console.log('📋 Latest contract:', data.latestActiveContract);
      console.log('📊 AI Event Summary:', data.ai_event_summary);
      console.log('📦 Full response:', JSON.stringify(data, null, 2));

      setProject(data as Project);
      setError(null);
    } catch (err: any) {
      console.error('❌ Failed to load project:', err);
      setError(err.message || 'Failed to load project');
      toast.error('Failed to load project details');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
          <p className="text-gray-600">Loading project details...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center max-w-md">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 mb-4">
            <p className="text-red-600 font-medium mb-2">Failed to load project</p>
            <p className="text-red-500 text-sm">{error}</p>
          </div>
          <button
            onClick={() => router.push('/projects')}
            className="text-blue-600 hover:text-blue-700 font-medium"
          >
            ← Back to Projects
          </button>
        </div>
      </div>
    );
  }

  const eventSummary = project.ai_event_summary || {};
  const contract = project.latestActiveContract;

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => router.push('/projects')}
            className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            Back to Projects
          </button>

          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">{project.title}</h1>
              <p className="text-gray-600 mt-1">Project ID: {project.id}</p>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => router.push(`/projects/${project.id}/chat`)}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                <MessageSquare className="h-4 w-4" />
                Chat
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Event Details */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h2 className="text-xl font-semibold text-gray-900 mb-4">Event Details</h2>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {project.event_date && (
                  <div className="flex items-start gap-3">
                    <Calendar className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Event Date</p>
                      <p className="font-medium text-gray-900">
                        {new Date(project.event_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                )}

                {project.guest_count && (
                  <div className="flex items-start gap-3">
                    <Users className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Guest Count</p>
                      <p className="font-medium text-gray-900">{project.guest_count} guests</p>
                    </div>
                  </div>
                )}

                {eventSummary.venue_name && (
                  <div className="flex items-start gap-3">
                    <MapPin className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Venue</p>
                      <p className="font-medium text-gray-900">{eventSummary.venue_name}</p>
                      {eventSummary.venue_address && (
                        <p className="text-sm text-gray-600">{eventSummary.venue_address}</p>
                      )}
                    </div>
                  </div>
                )}

                {eventSummary.event_type && (
                  <div className="flex items-start gap-3">
                    <FileText className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div>
                      <p className="text-sm text-gray-500">Event Type</p>
                      <p className="font-medium text-gray-900">{eventSummary.event_type}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Client Information */}
              {(eventSummary.client_name || eventSummary.contact_email || eventSummary.contact_phone) && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Client Information</h3>
                  <div className="space-y-2">
                    {eventSummary.client_name && (
                      <div>
                        <span className="text-sm text-gray-500">Name: </span>
                        <span className="font-medium text-gray-900">{eventSummary.client_name}</span>
                      </div>
                    )}
                    {eventSummary.contact_email && (
                      <div>
                        <span className="text-sm text-gray-500">Email: </span>
                        <span className="font-medium text-gray-900">{eventSummary.contact_email}</span>
                      </div>
                    )}
                    {eventSummary.contact_phone && (
                      <div>
                        <span className="text-sm text-gray-500">Phone: </span>
                        <span className="font-medium text-gray-900">{eventSummary.contact_phone}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Menu Items */}
              {eventSummary.menu_items && eventSummary.menu_items.length > 0 && (
                <div className="mt-6 pt-6 border-t border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-900 mb-3">Menu Items</h3>
                  <ul className="list-disc list-inside space-y-1">
                    {eventSummary.menu_items.map((item: string, idx: number) => (
                      <li key={idx} className="text-gray-700">{item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* AI Event Summary (Full Data) */}
            {Object.keys(eventSummary).length > 0 && (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-4">Full Event Summary</h2>
                <pre className="bg-gray-50 p-4 rounded-lg overflow-auto text-sm">
                  {JSON.stringify(eventSummary, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Status Card */}
            <div className="bg-white rounded-lg shadow-sm p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Project Status</h3>
              <div className="space-y-3">
                <div>
                  <span className="text-sm text-gray-500">Status</span>
                  <div className="mt-1">
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                      project.status === 'active' ? 'bg-green-100 text-green-800' :
                      project.status === 'draft' ? 'bg-gray-100 text-gray-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {project.status}
                    </span>
                  </div>
                </div>
                <div>
                  <span className="text-sm text-gray-500">Created</span>
                  <p className="font-medium text-gray-900 mt-1">
                    {new Date(project.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            </div>

            {/* Contract Card */}
            {contract ? (
              <>
                <div className="bg-white rounded-lg shadow-sm p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Contract Summary</h3>
                  <div className="space-y-3">
                    <div>
                      <span className="text-sm text-gray-500">Status</span>
                      <div className="mt-1">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                          contract.status === 'signed' ? 'bg-green-100 text-green-800' :
                          contract.status === 'pending_staff_approval' ? 'bg-yellow-100 text-yellow-800' :
                          contract.status === 'sent' ? 'bg-blue-100 text-blue-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {contract.status.replace(/_/g, ' ')}
                        </span>
                      </div>
                    </div>
                    <div>
                      <span className="text-sm text-gray-500">Version</span>
                      <p className="font-medium text-gray-900 mt-1">v{contract.version_number}</p>
                    </div>
                    <div>
                      <span className="text-sm text-gray-500">Contract ID</span>
                      <p className="font-mono text-xs text-gray-600 mt-1 break-all">{contract.id}</p>
                    </div>
                    {contract.total_amount && (
                      <div>
                        <span className="text-sm text-gray-500">Total Amount</span>
                        <p className="font-medium text-gray-900 mt-1">
                          ${contract.total_amount.toLocaleString()}
                        </p>
                      </div>
                    )}

                    <button
                      onClick={() => router.push(`/contracts/${contract.id}`)}
                      className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                    >
                      View Full Contract
                    </button>
                  </div>
                </div>

                {/* Contract Details */}
                {contract.body && (
                  <div className="bg-white rounded-lg shadow-sm p-6">
                    <h3 className="text-lg font-semibold text-gray-900 mb-4">Contract Details</h3>

                    {/* Client Info */}
                    {contract.body.client_info && (
                      <div className="mb-4 pb-4 border-b border-gray-200">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Client</h4>
                        <div className="space-y-1 text-sm">
                          {contract.body.client_info.name && (
                            <p><span className="text-gray-500">Name:</span> {contract.body.client_info.name}</p>
                          )}
                          {contract.body.client_info.email && (
                            <p><span className="text-gray-500">Email:</span> {contract.body.client_info.email}</p>
                          )}
                          {contract.body.client_info.phone && (
                            <p><span className="text-gray-500">Phone:</span> {contract.body.client_info.phone}</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Event Info */}
                    {contract.body.event_details && (
                      <div className="mb-4 pb-4 border-b border-gray-200">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Event</h4>
                        <div className="space-y-1 text-sm">
                          {contract.body.event_details.type && (
                            <p><span className="text-gray-500">Type:</span> {contract.body.event_details.type}</p>
                          )}
                          {contract.body.event_details.date && (
                            <p><span className="text-gray-500">Date:</span> {contract.body.event_details.date}</p>
                          )}
                          {contract.body.event_details.guest_count && (
                            <p><span className="text-gray-500">Guests:</span> {contract.body.event_details.guest_count}</p>
                          )}
                          {contract.body.event_details.service_type && (
                            <p><span className="text-gray-500">Service:</span> {contract.body.event_details.service_type}</p>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Menu */}
                    {contract.body.menu?.items && contract.body.menu.items.length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Menu</h4>
                        <ul className="list-disc list-inside space-y-1 text-sm text-gray-600">
                          {contract.body.menu.items.map((item: any, idx: number) => (
                            <li key={idx}>{item.name || item}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Full Contract Data */}
                    <details className="mt-4">
                      <summary className="text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900">
                        View Full Contract Data
                      </summary>
                      <pre className="mt-2 bg-gray-50 p-3 rounded text-xs overflow-auto max-h-96">
                        {JSON.stringify(contract.body, null, 2)}
                      </pre>
                    </details>
                  </div>
                )}
              </>
            ) : (
              <div className="bg-white rounded-lg shadow-sm p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No Contract</h3>
                <p className="text-sm text-gray-600">No contract has been generated for this project yet.</p>
                <button
                  onClick={() => router.push(`/projects/${projectId}/chat`)}
                  className="w-full mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  Start AI Chat to Generate Contract
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
