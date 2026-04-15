'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import Link from 'next/link';
import { gsap } from 'gsap';
import './MagicBento.css';

/* ─── Types ─────────────────────────────────────────────────── */
export interface BentoItem {
  id: string;
  href: string;
  label?: string;          // top-left badge
  title: string;
  subtitle?: string;
  meta?: string;
  badge?: { text: string; className: string };
  accentColor?: string;    // hex, used for particle + glow tint
}

interface MagicBentoProps {
  items: BentoItem[];
  glowColor?: string;      // "r, g, b"
  particleCount?: number;
  enableSpotlight?: boolean;
  enableBorderGlow?: boolean;
  enableTilt?: boolean;
  clickEffect?: boolean;
}

/* ─── Helpers ───────────────────────────────────────────────── */
function hexToRgb(hex: string): string {
  const m = hex.replace('#', '').match(/.{2}/g);
  if (!m) return '0,0,0';
  return m.map((v) => parseInt(v, 16)).join(', ');
}

const MOBILE_BP = 768;

/* ─── ParticleCard ──────────────────────────────────────────── */
function ParticleCard({
  item,
  glowColor,
  particleCount,
  enableTilt,
  clickEffect,
  enableBorderGlow,
}: {
  item: BentoItem;
  glowColor: string;
  particleCount: number;
  enableTilt: boolean;
  clickEffect: boolean;
  enableBorderGlow: boolean;
}) {
  const cardRef = useRef<HTMLAnchorElement>(null);
  const particlesRef = useRef<HTMLElement[]>([]);
  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const isHoveredRef = useRef(false);
  const rgb = item.accentColor ? hexToRgb(item.accentColor) : glowColor;

  const clearParticles = useCallback(() => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = [];
    particlesRef.current.forEach((p) => {
      gsap.to(p, {
        scale: 0, opacity: 0, duration: 0.3, ease: 'back.in(1.7)',
        onComplete: () => p.parentNode?.removeChild(p),
      });
    });
    particlesRef.current = [];
  }, []);

  const spawnParticles = useCallback(() => {
    if (!cardRef.current || !isHoveredRef.current) return;
    const { width, height } = cardRef.current.getBoundingClientRect();
    for (let i = 0; i < particleCount; i++) {
      const tid = setTimeout(() => {
        if (!isHoveredRef.current || !cardRef.current) return;
        const el = document.createElement('div') as HTMLElement;
        el.className = 'bento-particle';
        el.style.cssText = `left:${Math.random() * width}px;top:${Math.random() * height}px;background:rgba(${rgb},1);box-shadow:0 0 6px rgba(${rgb},0.6);`;
        cardRef.current.appendChild(el);
        particlesRef.current.push(el);
        gsap.fromTo(el, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, ease: 'back.out(1.7)' });
        gsap.to(el, { x: (Math.random() - 0.5) * 80, y: (Math.random() - 0.5) * 80, rotation: Math.random() * 360, duration: 2 + Math.random() * 2, ease: 'none', repeat: -1, yoyo: true });
        gsap.to(el, { opacity: 0.3, duration: 1.5, ease: 'power2.inOut', repeat: -1, yoyo: true });
      }, i * 80);
      timeoutsRef.current.push(tid);
    }
  }, [particleCount, rgb]);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;

    const onEnter = () => { isHoveredRef.current = true; spawnParticles(); };
    const onLeave = () => {
      isHoveredRef.current = false;
      clearParticles();
      if (enableTilt) gsap.to(el, { rotateX: 0, rotateY: 0, duration: 0.3, ease: 'power2.out' });
    };
    const onMove = (e: MouseEvent) => {
      if (!enableTilt) return;
      const r = el.getBoundingClientRect();
      const rx = ((e.clientY - r.top) / r.height - 0.5) * -12;
      const ry = ((e.clientX - r.left) / r.width - 0.5) * 12;
      gsap.to(el, { rotateX: rx, rotateY: ry, duration: 0.15, ease: 'power2.out', transformPerspective: 1000 });
      el.style.setProperty('--glow-x', `${((e.clientX - r.left) / r.width) * 100}%`);
      el.style.setProperty('--glow-y', `${((e.clientY - r.top) / r.height) * 100}%`);
      el.style.setProperty('--glow-intensity', '1');
    };
    const onClick = (e: MouseEvent) => {
      if (!clickEffect) return;
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left, y = e.clientY - r.top;
      const maxD = Math.max(Math.hypot(x, y), Math.hypot(x - r.width, y), Math.hypot(x, y - r.height), Math.hypot(x - r.width, y - r.height));
      const ripple = document.createElement('div');
      ripple.style.cssText = `position:absolute;width:${maxD * 2}px;height:${maxD * 2}px;border-radius:50%;background:radial-gradient(circle,rgba(${rgb},0.3) 0%,rgba(${rgb},0.1) 40%,transparent 70%);left:${x - maxD}px;top:${y - maxD}px;pointer-events:none;z-index:100;`;
      el.appendChild(ripple);
      gsap.fromTo(ripple, { scale: 0, opacity: 1 }, { scale: 1, opacity: 0, duration: 0.7, ease: 'power2.out', onComplete: () => ripple.remove() });
    };

    el.addEventListener('mouseenter', onEnter);
    el.addEventListener('mouseleave', onLeave);
    el.addEventListener('mousemove', onMove);
    el.addEventListener('click', onClick);
    return () => {
      isHoveredRef.current = false;
      el.removeEventListener('mouseenter', onEnter);
      el.removeEventListener('mouseleave', onLeave);
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('click', onClick);
      clearParticles();
    };
  }, [spawnParticles, clearParticles, enableTilt, clickEffect]);

  return (
    <Link
      ref={cardRef}
      href={item.href}
      className={`bento-card${enableBorderGlow ? ' bento-card--glow' : ''}`}
      style={{ '--glow-color': rgb } as React.CSSProperties}
    >
      {/* Top row */}
      <div className="flex items-start justify-between">
        {item.label && (
          <span className="text-[11px] font-medium text-neutral-400 uppercase tracking-widest">
            {item.label}
          </span>
        )}
        {item.badge && (
          <span className={`ml-auto px-2 py-0.5 rounded-full text-[10px] font-semibold ${item.badge.className}`}>
            {item.badge.text}
          </span>
        )}
      </div>

      {/* Bottom content */}
      <div className="mt-auto">
        {item.meta && (
          <p className="text-xs text-neutral-400 mb-1">{item.meta}</p>
        )}
        <h3 className="text-sm font-semibold text-neutral-900 leading-snug line-clamp-2">{item.title}</h3>
        {item.subtitle && (
          <p className="text-xs text-neutral-500 mt-0.5 line-clamp-1">{item.subtitle}</p>
        )}
      </div>
    </Link>
  );
}

/* ─── Spotlight ─────────────────────────────────────────────── */
function Spotlight({ gridRef, glowColor, radius }: { gridRef: React.RefObject<HTMLDivElement | null>; glowColor: string; radius: number }) {
  useEffect(() => {
    const spotlight = document.createElement('div');
    spotlight.className = 'bento-spotlight';
    spotlight.style.background = `radial-gradient(circle, rgba(${glowColor},0.12) 0%, rgba(${glowColor},0.06) 25%, rgba(${glowColor},0.02) 50%, transparent 70%)`;
    document.body.appendChild(spotlight);

    const proximity = radius * 0.5;
    const fadeD = radius * 0.75;

    const onMove = (e: MouseEvent) => {
      if (!gridRef.current) return;
      const section = gridRef.current.closest('.bento-section') as HTMLElement | null;
      const rect = section?.getBoundingClientRect();
      const inside = rect && e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom;

      const cards = gridRef.current.querySelectorAll<HTMLElement>('.bento-card');
      if (!inside) {
        gsap.to(spotlight, { opacity: 0, duration: 0.3 });
        cards.forEach((c) => { c.style.setProperty('--glow-intensity', '0'); });
        return;
      }

      let minD = Infinity;
      cards.forEach((c) => {
        const cr = c.getBoundingClientRect();
        const cx = cr.left + cr.width / 2, cy = cr.top + cr.height / 2;
        const d = Math.max(0, Math.hypot(e.clientX - cx, e.clientY - cy) - Math.max(cr.width, cr.height) / 2);
        minD = Math.min(minD, d);
        const gi = d <= proximity ? 1 : d <= fadeD ? (fadeD - d) / (fadeD - proximity) : 0;
        c.style.setProperty('--glow-x', `${((e.clientX - cr.left) / cr.width) * 100}%`);
        c.style.setProperty('--glow-y', `${((e.clientY - cr.top) / cr.height) * 100}%`);
        c.style.setProperty('--glow-intensity', gi.toString());
        c.style.setProperty('--glow-radius', `${radius}px`);
      });

      gsap.to(spotlight, { left: e.clientX, top: e.clientY, duration: 0.1, ease: 'power2.out' });
      const targetOp = minD <= proximity ? 0.7 : minD <= fadeD ? ((fadeD - minD) / (fadeD - proximity)) * 0.7 : 0;
      gsap.to(spotlight, { opacity: targetOp, duration: 0.2, ease: 'power2.out' });
    };

    const onLeave = () => { gsap.to(spotlight, { opacity: 0, duration: 0.3 }); };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseleave', onLeave);
    return () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseleave', onLeave);
      spotlight.parentNode?.removeChild(spotlight);
    };
  }, [gridRef, glowColor, radius]);

  return null;
}

/* ─── MagicBento ────────────────────────────────────────────── */
export default function MagicBento({
  items,
  glowColor = '0, 0, 0',
  particleCount = 8,
  enableSpotlight = true,
  enableBorderGlow = true,
  enableTilt = true,
  clickEffect = true,
}: MagicBentoProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth <= MOBILE_BP);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  if (items.length === 0) return null;

  return (
    <div className="bento-section">
      {enableSpotlight && !isMobile && (
        <Spotlight gridRef={gridRef} glowColor={glowColor} radius={300} />
      )}
      <div ref={gridRef} className="bento-grid">
        {items.map((item) => (
          <ParticleCard
            key={item.id}
            item={item}
            glowColor={glowColor}
            particleCount={isMobile ? 0 : particleCount}
            enableTilt={!isMobile && enableTilt}
            clickEffect={clickEffect}
            enableBorderGlow={enableBorderGlow}
          />
        ))}
      </div>
    </div>
  );
}
