"use client";

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { FolderKanban, Users, FileText, LogOut, Menu, X, Sparkles, Package } from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';

const hostNavigation = [
  { name: 'Plan My Event',  href: '/chat',       icon: Sparkles },
  { name: 'My Events',      href: '/projects',   icon: FolderKanban },
  { name: 'Contracts',      href: '/contracts',  icon: FileText },
];

const staffNavigation = [
  { name: 'All Events',     href: '/projects',   icon: FolderKanban },
  { name: 'Contracts',      href: '/contracts',  icon: FileText },
  { name: 'CRM Dashboard',  href: '/crm',        icon: Users },
  { name: 'Inventory',      href: '/inventory',  icon: Package },
];

export function AppNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const isStaff = user?.email?.endsWith('@catering-company.com') ?? false;
  const navItems = isStaff ? staffNavigation : hostNavigation;

  const handleLogout = async () => {
    try { await apiClient.post('/auth/logout', {}); } catch { /* continue */ }
    // Clear the JWT cookie so middleware stops treating this session as authenticated
    document.cookie = 'app_jwt=; path=/; max-age=0; SameSite=Lax';
    logout();
    router.push('/signin');
  };

  // Display name: use email prefix formatted nicely
  const emailPrefix = user?.email?.split('@')[0] ?? '';
  const displayName = emailPrefix
    .split(/[._-]/)
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(' ');

  const userInitial = displayName.charAt(0).toUpperCase() || '?';

  return (
    <nav className="fixed top-3 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-1.5rem)] max-w-5xl h-12 rounded-full bg-white/70 backdrop-blur-xl backdrop-saturate-150 border border-white/60 shadow-[0_8px_28px_-10px_rgba(0,0,0,0.18),inset_0_1px_0_rgba(255,255,255,0.8)]">
      <div className="relative px-3 sm:px-5 h-full flex items-center">
        {/* Left: logo */}
        <Link href="/projects" className="flex items-center gap-2 shrink-0">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-black">
            <span className="text-xs font-bold text-white">TC</span>
          </div>
          <span className="text-sm font-semibold text-black hidden sm:block tracking-tight">
            The Catering company
          </span>
        </Link>

        {/* Center: nav */}
        <div className="hidden md:flex items-center gap-0.5 absolute left-1/2 -translate-x-1/2">
          {navItems.map((item) => {
            const isActive = item.href === '/chat'
              ? pathname === '/chat'
              : !!pathname?.startsWith(item.href);
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-2xl text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-black text-white'
                    : 'text-neutral-600 hover:text-black hover:bg-neutral-100'
                )}
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.name}
              </Link>
            );
          })}
        </div>

        {/* Right: user display + logout */}
        <div className="flex items-center gap-3 ml-auto">
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-sm text-neutral-700 font-medium hidden lg:block">{displayName}</span>
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-neutral-900 border border-neutral-700 shrink-0">
              <span className="text-xs font-semibold text-white">{userInitial}</span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            title="Log out"
            className="p-1.5 text-neutral-400 hover:text-black hover:bg-neutral-100 rounded-md transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
          <button
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            className="md:hidden p-1.5 text-neutral-400 hover:text-black hover:bg-neutral-100 rounded-md"
          >
            {isMobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown — separate pill below the navbar so the rounded nav
          doesn't clip the menu. */}
      {isMobileMenuOpen && (
        <div className="md:hidden absolute top-[calc(100%+8px)] left-0 right-0 rounded-2xl bg-white/85 backdrop-blur-xl backdrop-saturate-150 border border-white/60 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.22),inset_0_1px_0_rgba(255,255,255,0.8)] overflow-hidden">
          <div className="px-3 py-2 space-y-0.5">
            {navItems.map((item) => {
              const isActive = item.href === '/chat'
                ? pathname === '/chat'
                : !!pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-black text-white'
                      : 'text-neutral-600 hover:text-black hover:bg-neutral-100'
                  )}
                >
                  <item.icon className="h-4 w-4" />
                  {item.name}
                </Link>
              );
            })}
            <div className="pt-2 mt-2 border-t border-neutral-100">
              <div className="px-3 py-2 text-xs text-neutral-400">{user?.email}</div>
              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-3 px-3 py-2.5 text-sm font-medium text-neutral-600 hover:text-black hover:bg-neutral-100 rounded-md transition-colors"
              >
                <LogOut className="h-4 w-4" />
                Log out
              </button>
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
