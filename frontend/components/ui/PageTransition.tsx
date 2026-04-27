"use client";

import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';

type Phase = 'idle' | 'exiting' | 'entering';

export default function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const prevPathname = useRef(pathname);
  const [phase, setPhase] = useState<Phase>('idle');
  const [displayChildren, setDisplayChildren] = useState(children);

  useEffect(() => {
    if (pathname === prevPathname.current) {
      // Same route re-render (e.g. query param change) — update content only.
      setDisplayChildren(children);
      return;
    }

    prevPathname.current = pathname;

    // Exit → swap content → enter
    setPhase('exiting');
    const exitTimer = setTimeout(() => {
      setDisplayChildren(children);
      setPhase('entering');
      const enterTimer = setTimeout(() => setPhase('idle'), 400);
      return () => clearTimeout(enterTimer);
    }, 180); // exit anim duration

    return () => clearTimeout(exitTimer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // On the very first mount just show normally.
  useEffect(() => {
    setPhase('entering');
    const t = setTimeout(() => setPhase('idle'), 400);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      data-phase={phase}
      className="tc-transition-root"
      style={{ willChange: 'opacity, transform' }}
    >
      {displayChildren}
    </div>
  );
}
