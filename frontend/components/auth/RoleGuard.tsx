'use client';

import { useRequireRole } from '@/lib/hooks/useRequireRole';

interface RoleGuardProps {
  role: 'staff' | 'host';
  redirectTo?: string;
  /** Shown while role check resolves (optional — usually instant) */
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

/**
 * Wraps a page or section that requires a specific role.
 * Middleware handles the redirect at the edge, but this provides
 * a client-side safety net and renders a fallback during hydration.
 *
 * Usage:
 *   <RoleGuard role="staff">
 *     <StaffOnlyContent />
 *   </RoleGuard>
 */
export function RoleGuard({ role, redirectTo = '/projects', fallback = null, children }: RoleGuardProps) {
  const { userRole, isAuthenticated } = useRequireRole(role, redirectTo);

  // While Zustand rehydrates from localStorage, don't flash forbidden content
  if (!isAuthenticated || userRole !== role) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
