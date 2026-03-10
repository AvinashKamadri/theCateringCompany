"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { AiChat } from '@/components/chat/ai-chat';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';

export default function AiIntakePage() {
  const router = useRouter();
  const [isSaving, setIsSaving] = useState(false);

  const handleComplete = async (contractData: ContractData) => {
    setIsSaving(true);

    try {
      console.log('💾 Saving AI-generated project...', contractData);

      // Save contract data to backend using new AI intake endpoint
      const response = await apiClient.post('/projects/ai-intake', {
        client_name: contractData.client_name,
        contact_email: contractData.contact_email,
        contact_phone: contractData.contact_phone,
        event_type: contractData.event_type,
        event_date: contractData.event_date,
        guest_count: contractData.guest_count,
        service_type: contractData.service_type,
        menu_items: contractData.menu_items,
        dietary_restrictions: contractData.dietary_restrictions,
        budget_range: contractData.budget_range,
        venue_name: contractData.venue_name,
        venue_address: contractData.venue_address,
        setup_time: contractData.setup_time,
        service_time: contractData.service_time,
        addons: contractData.addons,
        modifications: contractData.modifications,
      });

      console.log('✅ Project created:', response);
      toast.success('Project created successfully!');

      // Redirect to the new project
      if (response.project?.id) {
        router.push(`/projects/${response.project.id}`);
      } else {
        toast.success('Project saved! Redirecting to projects list...');
        router.push('/projects');
      }
    } catch (error: any) {
      console.error('❌ Failed to save project:', error);
      toast.error(error.message || 'Failed to save project. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              TCC Premium Catering
            </h1>
            <p className="text-sm text-gray-600 mt-1">
              AI-powered event intake
            </p>
          </div>
          {isSaving && (
            <div className="flex items-center gap-2 text-blue-600">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
              <span className="text-sm font-medium">Saving project...</span>
            </div>
          )}
        </div>
      </header>

      {/* Chat Container */}
      <div className="flex-1 overflow-hidden">
        <div className="max-w-4xl mx-auto h-full py-6">
          <div className="bg-white rounded-2xl shadow-lg h-full overflow-hidden">
            <AiChat onComplete={handleComplete} />
          </div>
        </div>
      </div>
    </div>
  );
}
