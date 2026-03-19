"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth-store';
import { AppNav } from '@/components/layout/app-nav';

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);

  // Wait for Zustand to rehydrate from localStorage before checking auth.
  // Without this, isAuthenticated is false on first render even for logged-in
  // users, causing an immediate redirect to /signin → middleware sends them
  // back to /projects because the cookie is valid.
  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated && !isAuthenticated) router.push('/signin');
  }, [hydrated, isAuthenticated, router]);

  if (!hydrated || !isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-neutral-50">
      <AppNav />
      <main className="pt-14">{children}</main>
    </div>
  );
}
