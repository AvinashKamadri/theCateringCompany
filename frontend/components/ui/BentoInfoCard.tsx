'use client';

import { useRef, useEffect, useCallback } from 'react';
import { gsap } from 'gsap';
import './MagicBento.css';

interface BentoInfoCardProps {
  children: React.ReactNode;
  className?: string;
  enableTilt?: boolean;
  glowColor?: string; // "r, g, b"
}

/**
 * A non-navigational bento card with glow border + optional subtle tilt.
 * Use for content sections on detail pages (project, contract).
 */
export default function BentoInfoCard({
  children,
  className = '',
  enableTilt = true,
  glowColor = '0, 0, 0',
}: BentoInfoCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);

  const onMove = useCallback(
    (e: MouseEvent) => {
      const el = cardRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      el.style.setProperty('--glow-x', `${((e.clientX - r.left) / r.width) * 100}%`);
      el.style.setProperty('--glow-y', `${((e.clientY - r.top) / r.height) * 100}%`);
      el.style.setProperty('--glow-intensity', '1');
      if (enableTilt) {
        const rx = ((e.clientY - r.top) / r.height - 0.5) * -6;
        const ry = ((e.clientX - r.left) / r.width - 0.5) * 6;
        gsap.to(el, { rotateX: rx, rotateY: ry, duration: 0.2, ease: 'power2.out', transformPerspective: 1000 });
      }
    },
    [enableTilt],
  );

  const onLeave = useCallback(() => {
    const el = cardRef.current;
    if (!el) return;
    el.style.setProperty('--glow-intensity', '0');
    if (enableTilt) gsap.to(el, { rotateX: 0, rotateY: 0, duration: 0.4, ease: 'power2.out' });
  }, [enableTilt]);

  useEffect(() => {
    const el = cardRef.current;
    if (!el) return;
    el.addEventListener('mousemove', onMove);
    el.addEventListener('mouseleave', onLeave);
    return () => {
      el.removeEventListener('mousemove', onMove);
      el.removeEventListener('mouseleave', onLeave);
    };
  }, [onMove, onLeave]);

  return (
    <div
      ref={cardRef}
      className={`bento-card bento-card--glow ${className}`}
      style={
        {
          cursor: 'default',
          minHeight: 'unset',
          '--glow-color': glowColor,
        } as React.CSSProperties
      }
    >
      {children}
    </div>
  );
}
