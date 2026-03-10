import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasAuthCookie = request.cookies.has('app_jwt');

  // Protected routes that require authentication
  const protectedRoutes = ['/dashboard', '/projects', '/crm', '/messages', '/contracts'];
  const isProtectedRoute = protectedRoutes.some((route) => pathname.startsWith(route));

  // Auth routes that should redirect if already authenticated
  const authRoutes = ['/signin', '/signup'];
  const isAuthRoute = authRoutes.some((route) => pathname.startsWith(route));

  // If trying to access protected route without auth, redirect to signin
  if (isProtectedRoute && !hasAuthCookie) {
    const url = new URL('/signin', request.url);
    url.searchParams.set('redirect', pathname);
    return NextResponse.redirect(url);
  }

  // If trying to access auth routes while authenticated, redirect to projects
  if (isAuthRoute && hasAuthCookie) {
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
    '/signin',
    '/signup',
  ],
};
