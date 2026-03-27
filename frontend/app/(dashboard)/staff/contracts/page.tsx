"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Contract review has moved to the CRM dashboard.
export default function StaffContractsRedirect() {
  const router = useRouter();
  useEffect(() => { router.replace('/crm'); }, [router]);
  return null;
}
