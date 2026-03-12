import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// All routes are PUBLIC on the frontend.
// Auth is enforced only at the API level (backend JWT guards).
// This middleware simply passes every request through.
export function middleware(request: NextRequest) {
    return NextResponse.next();
}

export const config = {
    matcher: [
        /*
         * Match all request paths except for the ones starting with:
         * - api (Next.js API routes)
         * - _next/static (static files)
         * - _next/image (image optimization files)
         * - favicon.ico (favicon file)
         * - hero-bg.png (public assets)
         */
        '/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$).*)',
    ],
};
