"use client";

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { FolderKanban, Users, FileText, LogOut, Menu, X, Sparkles } from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { cn } from '@/lib/utils';

const ALL_NAVIGATION = [
  { name: 'CRM',       href: '/crm',      icon: Users,        staffOnly: true,  clientOnly: false },
  { name: 'AI Intake', href: '/chat',     icon: Sparkles,     staffOnly: false, clientOnly: true  },
  { name: 'Projects',  href: '/projects', icon: FolderKanban, staffOnly: false, clientOnly: false },
  { name: 'Contracts', href: '/contracts', icon: FileText,    staffOnly: false, clientOnly: true  },
];

export function AppNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuthStore();
  const isStaff = user?.role === 'staff' || user?.email?.toLowerCase().endsWith('@catering-company.com');
  const navigation = ALL_NAVIGATION.filter((item) => {
    if (item.staffOnly && !isStaff) return false;
    if (item.clientOnly && isStaff) return false;
    return true;
  });
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    try { await apiClient.post('/auth/logout', {}); } catch { /* continue */ }
    // Clear the JWT cookie so middleware stops treating this session as authenticated
    document.cookie = 'app_jwt=; path=/; max-age=0; SameSite=Lax';
    logout();
    router.push('/signin');
  };

  const userInitial = user?.email?.charAt(0).toUpperCase() ?? '?';

  return (
    <nav className="bg-white border-b border-neutral-200 fixed top-0 left-0 right-0 z-50 h-14">
      <div className="px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between">
        {/* Left: logo + nav */}
        <div className="flex items-center gap-7">
          <Link href="/projects" className="flex items-center gap-2 shrink-0">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-black">
              <span className="text-xs font-bold text-white">TC</span>
            </div>
            <span className="text-sm font-semibold text-black hidden sm:block tracking-tight">
              TheCateringCompany
            </span>
          </Link>

          <div className="hidden md:flex items-center gap-0.5">
            {navigation.map((item) => {
              const isActive = item.href === '/chat'
                ? pathname === '/chat'
                : pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
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
        </div>

        {/* Right: user + logout */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-neutral-100 border border-neutral-200">
              <span className="text-xs font-semibold text-black">{userInitial}</span>
            </div>
            <span className="text-sm text-neutral-600 hidden lg:block">{user?.email}</span>
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

      {/* Mobile dropdown */}
      {isMobileMenuOpen && (
        <div className="md:hidden border-t border-neutral-200 bg-white">
          <div className="px-4 py-2 space-y-0.5">
            {navigation.map((item) => {
              const isActive = item.href === '/chat'
                ? pathname === '/chat'
                : pathname.startsWith(item.href);
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
