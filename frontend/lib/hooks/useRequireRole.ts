'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store/auth-store';

const STAFF_DOMAIN = '@catering-company.com';

/**
 * Redirects the user if they don't have the required role.
 * Use this inside page components that need role-based protection
 * beyond what the middleware already handles.
 *
 * @param role  'staff' | 'host' | 'any' (default: 'any')
 * @param redirectTo  Where to send unauthorized users (default: '/projects')
 */
export function useRequireRole(
  role: 'staff' | 'host' | 'any' = 'any',
  redirectTo = '/projects',
) {
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();

  const isStaff = user?.email?.endsWith(STAFF_DOMAIN) ?? false;
  const userRole: 'staff' | 'host' = isStaff ? 'staff' : 'host';

  useEffect(() => {
    if (!isAuthenticated) return; // middleware handles unauthenticated redirect
    if (role === 'any') return;   // no role constraint
    if (role !== userRole) {
      router.replace(redirectTo);
    }
  }, [isAuthenticated, role, userRole, redirectTo, router]);

  return { userRole, isStaff, isAuthenticated };
}
