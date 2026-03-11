"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, XCircle, Clock, Eye, Send, Loader2, AlertCircle } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';
import { toast } from 'sonner';

interface Contract {
  id: string;
  title: string;
  status: string;
  created_at: string;
  body: any;
  projects_contracts_project_idToprojects: {
    id: string;
    title: string;
    event_date: string;
    guest_count: number;
    ai_event_summary: any;
  };
  users_contracts_created_byTousers: {
    email: string;
  };
}

// Helper to get projects data regardless of relation name
const getProject = (contract: Contract) => contract.projects_contracts_project_idToprojects;

export default function StaffContractsPage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // Check if user is staff
  const isStaff = user?.email?.endsWith('@flashbacklabs.com') || user?.email?.endsWith('@flashbacklabs.inc');

  useEffect(() => {
    if (!isStaff) {
      toast.error('Access denied. Staff accounts only.');
      router.push('/projects');
      return;
    }
    fetchPendingContracts();
  }, [isStaff]);

  const fetchPendingContracts = async () => {
    try {
      console.log('📋 Fetching pending contracts...');
      const data: any = await apiClient.get('/staff/contracts/pending');
      setContracts(data.contracts || []);
      console.log(`✅ Loaded ${data.contracts?.length || 0} pending contracts`);
    } catch (error: any) {
      console.error('❌ Failed to fetch contracts:', error);
      toast.error(error.message || 'Failed to load contracts');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (contractId: string) => {
    if (!confirm('Approve this contract and send to client for signature?')) return;

    setActionLoading(true);
    try {
      console.log(`✅ Approving contract ${contractId}...`);
      const result: any = await apiClient.post(`/staff/contracts/${contractId}/approve`, {
        message: 'Contract approved by staff',
      });

      toast.success('Contract approved and sent to client!');
      console.log(`✅ Contract approved. SignWell Doc ID: ${result.signwell_document_id}`);

      // Refresh list
      await fetchPendingContracts();
      setSelectedContract(null);
    } catch (error: any) {
      console.error('❌ Failed to approve contract:', error);
      toast.error(error.message || 'Failed to approve contract');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async (contractId: string) => {
    if (!rejectReason.trim()) {
      toast.error('Please provide a reason for rejection');
      return;
    }

    setActionLoading(true);
    try {
      console.log(`❌ Rejecting contract ${contractId}...`);
      await apiClient.post(`/staff/contracts/${contractId}/reject`, {
        reason: rejectReason,
      });

      toast.success('Contract rejected');
      console.log(`✅ Contract rejected`);

      // Refresh list
      await fetchPendingContracts();
      setSelectedContract(null);
      setRejectReason('');
    } catch (error: any) {
      console.error('❌ Failed to reject contract:', error);
      toast.error(error.message || 'Failed to reject contract');
    } finally {
      setActionLoading(false);
    }
  };

  const getClientInfo = (contract: Contract) => {
    const project = getProject(contract);
    const aiData = project?.ai_event_summary ? JSON.parse(project.ai_event_summary) : {};
    const creatorEmail = contract.users_contracts_created_byTousers?.email || '';
    const fallbackName = creatorEmail ? creatorEmail.split('@')[0] : 'Client';

    return {
      name: contract.body?.client_info?.name || aiData.client_name || fallbackName,
      email: contract.body?.client_info?.email || aiData.contact_email || creatorEmail,
      phone: contract.body?.client_info?.phone || aiData.contact_phone || 'N/A',
    };
  };

  if (!isStaff) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600">Only staff accounts can access this page.</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Contract Approvals</h1>
          <p className="text-gray-600">
            Review and approve contracts before sending to clients for e-signature
          </p>
          <div className="mt-4 flex items-center gap-2 text-sm">
            <div className="px-3 py-1 bg-green-100 text-green-700 rounded-full">
              Staff Access: {user?.email}
            </div>
            <div className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full">
              {contracts.length} Pending
            </div>
          </div>
        </div>

        {contracts.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm p-12 text-center">
            <Clock className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No Pending Contracts</h3>
            <p className="text-gray-600">All contracts have been reviewed!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Contracts List */}
            <div className="space-y-4">
              {contracts.map((contract) => {
                const client = getClientInfo(contract);
                return (
                  <div
                    key={contract.id}
                    className={`bg-white rounded-xl shadow-sm p-6 cursor-pointer transition-all hover:shadow-md ${
                      selectedContract?.id === contract.id ? 'ring-2 ring-blue-500' : ''
                    }`}
                    onClick={() => setSelectedContract(contract)}
                  >
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 mb-1">{contract.title}</h3>
                        <p className="text-sm text-gray-600">{getProject(contract)?.title}</p>
                      </div>
                      <span className="px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
                        Pending Review
                      </span>
                    </div>

                    <div className="space-y-2 text-sm">
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">Client:</span>
                        <span className="font-medium">{client.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">Email:</span>
                        <span className="text-gray-700">{client.email}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">Event Date:</span>
                        <span className="text-gray-700">
                          {new Date(getProject(contract)?.event_date).toLocaleDateString()}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-gray-500">Guests:</span>
                        <span className="text-gray-700">{getProject(contract)?.guest_count || 'N/A'}</span>
                      </div>
                    </div>

                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedContract(contract);
                        }}
                        className="flex-1 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
                      >
                        <Eye className="w-4 h-4 inline mr-2" />
                        Review
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Contract Details Panel */}
            {selectedContract ? (
              <div className="bg-white rounded-xl shadow-sm p-6 lg:sticky lg:top-6 max-h-[calc(100vh-8rem)] overflow-y-auto">
                <h2 className="text-xl font-bold text-gray-900 mb-4">Contract Details</h2>

                {/* Contract Info */}
                <div className="space-y-4 mb-6">
                  <div>
                    <label className="text-sm text-gray-500 block mb-1">Contract Title</label>
                    <p className="font-medium">{selectedContract.title}</p>
                  </div>

                  <div>
                    <label className="text-sm text-gray-500 block mb-1">Client Information</label>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
                      <p><strong>Name:</strong> {getClientInfo(selectedContract).name}</p>
                      <p><strong>Email:</strong> {getClientInfo(selectedContract).email}</p>
                      <p><strong>Phone:</strong> {getClientInfo(selectedContract).phone}</p>
                    </div>
                  </div>

                  <div>
                    <label className="text-sm text-gray-500 block mb-1">Event Details</label>
                    <div className="bg-gray-50 rounded-lg p-4 space-y-2 text-sm">
                      <p><strong>Type:</strong> {selectedContract.body?.event_details?.type || 'N/A'}</p>
                      <p><strong>Date:</strong> {new Date(getProject(selectedContract)?.event_date).toLocaleDateString()}</p>
                      <p><strong>Guests:</strong> {getProject(selectedContract)?.guest_count || 'N/A'}</p>
                      <p><strong>Service:</strong> {selectedContract.body?.event_details?.service_type || 'N/A'}</p>
                    </div>
                  </div>

                  {selectedContract.body?.menu && (
                    <div>
                      <label className="text-sm text-gray-500 block mb-1">Menu Items</label>
                      <div className="bg-gray-50 rounded-lg p-4 text-sm">
                        <ul className="list-disc list-inside space-y-1">
                          {selectedContract.body.menu.items?.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}
                </div>

                {/* Rejection Reason (if rejecting) */}
                {rejectReason !== null && (
                  <div className="mb-6">
                    <label className="text-sm text-gray-700 block mb-2 font-medium">
                      Rejection Reason *
                    </label>
                    <textarea
                      value={rejectReason}
                      onChange={(e) => setRejectReason(e.target.value)}
                      placeholder="Explain why this contract is being rejected..."
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 focus:border-transparent resize-none"
                      rows={4}
                    />
                  </div>
                )}

                {/* Action Buttons */}
                <div className="flex gap-3">
                  <button
                    onClick={() => handleApprove(selectedContract.id)}
                    disabled={actionLoading}
                    className="flex-1 bg-green-600 text-white px-4 py-3 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center gap-2"
                  >
                    {actionLoading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin" />
                        Processing...
                      </>
                    ) : (
                      <>
                        <CheckCircle className="w-5 h-5" />
                        Approve & Send
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => {
                      if (rejectReason) {
                        handleReject(selectedContract.id);
                      } else {
                        setRejectReason('');
                      }
                    }}
                    disabled={actionLoading}
                    className="flex-1 bg-red-600 text-white px-4 py-3 rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-semibold flex items-center justify-center gap-2"
                  >
                    <XCircle className="w-5 h-5" />
                    Reject
                  </button>
                </div>

                <p className="text-xs text-gray-500 mt-4 text-center">
                  Approving will send the contract to the client via SignWell for e-signature
                </p>
              </div>
            ) : (
              <div className="bg-white rounded-xl shadow-sm p-12 text-center lg:sticky lg:top-6">
                <Eye className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">Select a Contract</h3>
                <p className="text-gray-600">Click on a contract to review details</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
