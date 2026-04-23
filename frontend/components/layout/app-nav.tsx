"use client";

import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { LogOut } from 'lucide-react';
import { useAuthStore } from '@/lib/store/auth-store';
import { apiClient } from '@/lib/api/client';
import { useEffect, useRef, useState } from 'react';
import { gsap } from 'gsap';
import './PillNav.css';

const hostItems = [
  { label: 'Plan My Event', href: '/chat' },
  { label: 'My Events',     href: '/projects' },
  { label: 'Contracts',     href: '/contracts' },
];

const staffItems = [
  { label: 'All Events',  href: '/projects' },
  { label: 'Contracts',   href: '/contracts' },
  { label: 'CRM',         href: '/crm' },
  { label: 'Menu',        href: '/menu' },
  { label: 'Inventory',   href: '/inventory' },
];

const ease = 'power3.easeOut';

export function AppNav() {
  const router   = useRouter();
  const pathname = usePathname();
  const { user, logout } = useAuthStore();

  const isStaff  = user?.email?.endsWith('@catering-company.com') ?? false;
  const navItems = isStaff ? staffItems : hostItems;

  const handleLogout = async () => {
    try { await apiClient.post('/auth/logout', {}); } catch { /* continue */ }
    document.cookie = 'app_jwt=; path=/; max-age=0; SameSite=Lax';
    logout();
    router.push('/signin');
  };

  const emailPrefix = user?.email?.split('@')[0] ?? '';
  const displayName = emailPrefix.split(/[._-]/).map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ');
  const userInitial = displayName.charAt(0).toUpperCase() || '?';

  const activeHref = navItems.find((item) =>
    item.href === '/chat' ? pathname === '/chat' : pathname?.startsWith(item.href)
  )?.href;

  // GSAP pill hover refs
  const circleRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const tlRefs     = useRef<gsap.core.Timeline[]>([]);
  const tweenRefs  = useRef<gsap.core.Tween[]>([]);

  useEffect(() => {
    const layout = () => {
      circleRefs.current.forEach((circle, i) => {
        if (!circle?.parentElement) return;
        const pill = circle.parentElement;
        const { width: w, height: h } = pill.getBoundingClientRect();
        if (!w || !h) return;
        const R = ((w * w) / 4 + h * h) / (2 * h);
        const D = Math.ceil(2 * R) + 2;
        const delta = Math.ceil(R - Math.sqrt(Math.max(0, R * R - (w * w) / 4))) + 1;
        circle.style.width  = `${D}px`;
        circle.style.height = `${D}px`;
        circle.style.bottom = `-${delta}px`;
        gsap.set(circle, { xPercent: -50, scale: 0, transformOrigin: `50% ${D - delta}px` });

        const label = pill.querySelector('.pill-label') as HTMLElement | null;
        const hover = pill.querySelector('.pill-label-hover') as HTMLElement | null;
        if (label) gsap.set(label, { y: 0 });
        if (hover) gsap.set(hover, { y: h + 12, opacity: 0 });

        tlRefs.current[i]?.kill();
        const tl = gsap.timeline({ paused: true });
        tl.to(circle, { scale: 1.2, xPercent: -50, duration: 2, ease, overwrite: 'auto' }, 0);
        if (label) tl.to(label, { y: -(h + 8), duration: 2, ease, overwrite: 'auto' }, 0);
        if (hover) {
          gsap.set(hover, { y: Math.ceil(h + 100), opacity: 0 });
          tl.to(hover, { y: 0, opacity: 1, duration: 2, ease, overwrite: 'auto' }, 0);
        }
        tlRefs.current[i] = tl;
      });
    };
    layout();
    window.addEventListener('resize', layout);
    document.fonts?.ready?.then(layout).catch(() => {});
    return () => window.removeEventListener('resize', layout);
  }, [navItems]);

  const handleEnter = (i: number) => {
    const tl = tlRefs.current[i]; if (!tl) return;
    tweenRefs.current[i]?.kill();
    tweenRefs.current[i] = tl.tweenTo(tl.duration(), { duration: 0.3, ease, overwrite: 'auto' }) as gsap.core.Tween;
  };
  const handleLeave = (i: number) => {
    const tl = tlRefs.current[i]; if (!tl) return;
    tweenRefs.current[i]?.kill();
    tweenRefs.current[i] = tl.tweenTo(0, { duration: 0.2, ease, overwrite: 'auto' }) as gsap.core.Tween;
  };

  const cssVars = {
    '--base': '#141414',
    '--pill-bg': '#ffffff',
    '--hover-text': '#ffffff',
    '--pill-text': '#141414',
  } as React.CSSProperties;

  return (
    <div
      className="fixed top-3 left-1/2 -translate-x-1/2 z-50 flex items-center px-3 py-2 bg-[#141414] rounded-full shadow-[0_8px_32px_-8px_rgba(0,0,0,0.55)] w-[min(calc(100vw-2rem),820px)]"
      style={cssVars}
    >
      {/* ── Left: logo ── */}
      <Link
        href="/"
        className="flex items-center justify-center w-9 h-9 rounded-full bg-white/10 border border-white/20 shrink-0 text-white font-bold text-sm hover:bg-white/20 transition-colors"
      >
        TC
      </Link>

      {/* ── Center: nav pills ── */}
      <div className="flex-1 flex justify-center">
        <ul className="pill-list" role="menubar" style={{ height: '38px' }}>
          {navItems.map((item, i) => (
            <li key={item.href} role="none" style={{ display: 'flex', height: '100%' }}>
              <Link
                role="menuitem"
                href={item.href}
                className={`pill${activeHref === item.href ? ' is-active' : ''}`}
                onMouseEnter={() => handleEnter(i)}
                onMouseLeave={() => handleLeave(i)}
              >
                <span
                  className="hover-circle"
                  aria-hidden="true"
                  ref={(el) => { circleRefs.current[i] = el; }}
                />
                <span className="label-stack">
                  <span className="pill-label">{item.label}</span>
                  <span className="pill-label-hover" aria-hidden="true">{item.label}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </div>

      {/* ── Right: user + logout ── */}
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-medium text-neutral-300 hidden lg:block">{displayName}</span>
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white/15 border border-white/20">
          <span className="text-xs font-semibold text-white">{userInitial}</span>
        </div>
        <button
          onClick={handleLogout}
          title="Log out"
          className="p-1.5 rounded-full text-neutral-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
