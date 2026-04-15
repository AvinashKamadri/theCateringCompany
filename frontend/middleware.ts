import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

/**
 * Lightweight JWT expiry check — no signature verification needed here,
 * that's the backend's job. We just need to know if the token is expired
 * so we don't bounce the user in a loop when the cookie is stale.
 */
function isJwtExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    // exp is in seconds; Date.now() is ms
    return typeof payload.exp === 'number' && payload.exp * 1000 < Date.now();
  } catch {
    return true; // malformed = treat as expired
  }
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const jwtCookie = request.cookies.get('app_jwt');
  const hasValidCookie = !!jwtCookie?.value && !isJwtExpired(jwtCookie.value);

  // Protected routes that require authentication
  const protectedRoutes = ['/dashboard', '/projects', '/crm', '/messages', '/contracts', '/chat', '/staff'];
  const isProtectedRoute = protectedRoutes.some((route) => pathname.startsWith(route));

  // Auth routes that should redirect if already authenticated
  const authRoutes = ['/signin', '/signup'];
  const isAuthRoute = authRoutes.some((route) => pathname.startsWith(route));

  // If trying to access protected route without a valid (non-expired) cookie → signin
  if (isProtectedRoute && !hasValidCookie) {
    const url = new URL('/signin', request.url);
    url.searchParams.set('redirect', pathname + request.nextUrl.search);
    return NextResponse.redirect(url);
  }

  // If trying to access auth routes with a valid cookie → projects
  if (isAuthRoute && hasValidCookie) {
    return NextResponse.redirect(new URL('/projects', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
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
