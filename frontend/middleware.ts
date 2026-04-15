import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

interface JwtPayload {
  sub: string;
  email: string;
  role?: string;
  exp?: number;
}

/**
 * Decode JWT payload without verifying signature.
 * Returns null if malformed or expired.
 */
function decodeJwt(token: string): JwtPayload | null {
  try {
    const payload: JwtPayload = JSON.parse(
      atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/'))
    );
    if (typeof payload.exp === 'number' && payload.exp * 1000 < Date.now()) {
      return null; // expired
    }
    return payload;
  } catch {
    return null;
  }
}

// Routes only accessible when NOT authenticated
const AUTH_ROUTES = ['/signin', '/signup'];

// Routes that require authentication
const PROTECTED_ROUTES = ['/dashboard', '/projects', '/crm', '/messages', '/contracts', '/chat', '/staff'];

// Routes that require staff role
const STAFF_ONLY_ROUTES = ['/staff', '/crm'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const jwtCookie = request.cookies.get('app_jwt');
  const payload = jwtCookie?.value ? decodeJwt(jwtCookie.value) : null;
  const isAuthenticated = !!payload;
  const isStaff = payload?.role === 'staff' ||
    (payload?.email?.endsWith('@catering-company.com') ?? false);

  const isAuthRoute = AUTH_ROUTES.some((r) => pathname.startsWith(r));
  const isProtectedRoute = PROTECTED_ROUTES.some((r) => pathname.startsWith(r));
  const isStaffOnlyRoute = STAFF_ONLY_ROUTES.some((r) => pathname.startsWith(r));

  // 1. Unauthenticated user → protected route: send to signin with return URL
  if (isProtectedRoute && !isAuthenticated) {
    const url = new URL('/signin', request.url);
    url.searchParams.set('redirect', pathname + request.nextUrl.search);
    return NextResponse.redirect(url);
  }

  // 2. Authenticated user → auth route (signin/signup): send to projects
  if (isAuthRoute && isAuthenticated) {
    return NextResponse.redirect(new URL('/projects', request.url));
  }

  // 3. Non-staff user → staff-only route: send to projects (silent 403)
  if (isStaffOnlyRoute && isAuthenticated && !isStaff) {
    return NextResponse.redirect(new URL('/projects', request.url));
  }

  // 4. Root path: redirect based on auth state
  if (pathname === '/') {
    return NextResponse.redirect(
      new URL(isAuthenticated ? '/projects' : '/signin', request.url)
    );
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/',
    '/dashboard/:path*',
    '/projects/:path*',
    '/crm/:path*',
    '/messages/:path*',
    '/contracts/:path*',
    '/chat/:path*',
    '/staff/:path*',
    '/signin',
    '/signup',
  ],
};
