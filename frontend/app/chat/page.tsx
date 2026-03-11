"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { AiChat } from '@/components/chat/ai-chat';
import type { ContractData } from '@/types/chat-ai.types';
import { toast } from 'sonner';
import { apiClient } from '@/lib/api/client';
import { useAuthStore } from '@/lib/store/auth-store';

const STAFF_DOMAINS = ['@flashbacklabs.com', '@flashbacklabs.inc'];

export default function AiIntakePage() {
  const router = useRouter();
  const { user } = useAuthStore();
  const [isSaving, setIsSaving] = useState(false);

  // Staff users belong on the contracts page, not the client intake chat
  const isStaff = STAFF_DOMAINS.some((d) => user?.email?.toLowerCase().endsWith(d));
  useEffect(() => {
    if (isStaff) router.replace('/contracts');
  }, [isStaff, router]);

  const handleComplete = async (contractData: ContractData) => {
    setIsSaving(true);

    try {
      console.log('Saving AI-generated project...', contractData);

      const s = contractData;

      const addons = [
        s.utensils && s.utensils !== 'no'  ? `Utensils: ${s.utensils}` : null,
        s.desserts && s.desserts !== 'no'  ? `Desserts: ${s.desserts}` : null,
        s.rentals  && s.rentals  !== 'no'  ? `Rentals: ${s.rentals}`   : null,
        s.florals  && s.florals  !== 'no'  ? `Florals: ${s.florals}`   : null,
      ].filter(Boolean) as string[];

      const response = await apiClient.post('/projects/ai-intake', {
        client_name:          s.name,
        event_type:           s.event_type,
        event_date:           s.event_date,
        guest_count:          s.guest_count ? Number(s.guest_count) : undefined,
        service_type:         s.service_type,
        venue_name:           s.venue,
        venue_address:        s.venue,
        menu_items:           Array.isArray(s.selected_dishes) ? s.selected_dishes : [],
        dietary_restrictions: s.dietary_concerns ? [s.dietary_concerns] : [],
        addons,
        modifications:        s.special_requests && s.special_requests !== 'none'
                                ? [s.special_requests] : [],
        generate_contract:    true,
      });

      const data = response as any;

      if (data.contract) {
        toast.success('Project & Contract created! Pending staff approval.');
      } else {
        toast.success('Project created successfully!');
      }

      if (data.project?.id) {
        router.push(`/projects/${data.project.id}`);
      } else {
        router.push('/projects');
      }
    } catch (error: any) {
      console.error('Failed to save project:', error);
      toast.error(error.message || 'Failed to save project. Please try again.');
    } finally {
      setIsSaving(false);
    }
  };

  if (isStaff) return null;

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">The Catering Company</h1>
            <p className="text-sm text-gray-600 mt-1">AI-powered event intake</p>
          </div>
          {isSaving && (
            <div className="flex items-center gap-2 text-blue-600">
              <div className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
              <span className="text-sm font-medium">Saving project...</span>
            </div>
          )}
        </div>
      </header>
      <div className="flex-1 overflow-hidden">
        <div className="max-w-4xl mx-auto h-full py-6">
          <div className="bg-white rounded-2xl shadow-lg h-full overflow-hidden">
            <AiChat onComplete={handleComplete} authorId={user?.id} />
          </div>
        </div>
      </div>
    </div>
  );
}
