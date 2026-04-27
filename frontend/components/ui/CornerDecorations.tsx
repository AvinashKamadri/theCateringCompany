"use client";

import { usePathname } from 'next/navigation';

const ALL = [
  'image 1001977472.svg',
  'image 1001977473.svg',
  'image 1001977474.svg',
  'image 1001977475.svg',
  'image 1001977476.svg',
  'image 1001977477.svg',
  'image 1001977478.svg',
  'image 1001977479.svg',
  'image 1001977480.svg',
  'image 1001977481.svg',
  'image 1001977483.svg',
  'image 1001977484.svg',
  'image 1001977485.svg',
  'image 1001977486.svg',
  'image 1001977487.svg',
  'image 1001977489.svg',
  'image 1001977490.svg',
  'image 1001977491.svg',
  'image 1001977492.svg',
  'image 1001977493.svg',
  'image 1001977494.svg',
  'image 1001977495.svg',
  'image 1001977496.svg',
  'image 1001977497.svg',
  'image 1001977498.svg',
  'image 1001977499.svg',
  'image 1001977500.svg',
];

function seeded(seed: number) {
  let s = seed | 0;
  return () => {
    s = (Math.imul(1664525, s) + 1013904223) | 0;
    return (s >>> 0) / 0xffffffff;
  };
}

function strSeed(str: string) {
  let h = 5381;
  for (let i = 0; i < str.length; i++) h = ((h << 5) + h) ^ str.charCodeAt(i);
  return h;
}

type Edge = 'top' | 'left' | 'right';

type Placement = {
  src: string;
  edge: Edge;
  delay: number; // ms
  style: React.CSSProperties;
};

function buildPlacements(pathname: string): Placement[] {
  const rand = seeded(strSeed(pathname));

  // Shuffle
  const pool = [...ALL];
  for (let i = pool.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [pool[i], pool[j]] = [pool[j], pool[i]];
  }

  const src = (i: number) => `/corners/${encodeURIComponent(pool[i % pool.length])}`;
  const w   = () => 120 + Math.floor(rand() * 100); // 120–220px
  const op  = () => 0.6 + rand() * 0.3;             // 0.6–0.9
  const rot = () => (rand() - 0.5) * 50;            // ±25deg

  // Each slot: images anchored to an edge, partially cropped off-screen
  // top/left/right/bottom are set so the image center sits near or beyond the edge
  const placements: Placement[] = [];
  let idx = 0;

  let delayBase = 0;

  // ── TOP edge — 4 images spread horizontally, partially cropped at top ──
  const topPositions = [8, 28, 68, 88]; // % from left
  for (const leftPct of topPositions) {
    const size = w();
    const rotation = rot();
    placements.push({
      src: src(idx++),
      edge: 'top',
      delay: delayBase,
      style: {
        position: 'absolute',
        top: -(size * 0.35),
        left: `${leftPct}%`,
        width: size,
        // base transform without opacity — animation handles those
        transform: `translateX(-50%) rotate(${rotation}deg)`,
        opacity: op(),
      },
    });
    delayBase += 55 + Math.floor(rand() * 60);
  }

  // ── LEFT edge — 3 images spread vertically ──
  const leftPositions = [18, 45, 75];
  for (const topPct of leftPositions) {
    const size = w();
    const rotation = rot();
    placements.push({
      src: src(idx++),
      edge: 'left',
      delay: delayBase,
      style: {
        position: 'absolute',
        left: -(size * 0.4),
        top: `${topPct}%`,
        width: size,
        transform: `translateY(-50%) rotate(${rotation}deg)`,
        opacity: op(),
      },
    });
    delayBase += 55 + Math.floor(rand() * 60);
  }

  // ── RIGHT edge — 3 images spread vertically ──
  const rightPositions = [22, 50, 78];
  for (const topPct of rightPositions) {
    const size = w();
    const rotation = rot();
    placements.push({
      src: src(idx++),
      edge: 'right',
      delay: delayBase,
      style: {
        position: 'absolute',
        right: -(size * 0.4),
        top: `${topPct}%`,
        width: size,
        transform: `translateY(-50%) rotate(${rotation}deg)`,
        opacity: op(),
      },
    });
    delayBase += 55 + Math.floor(rand() * 60);
  }

  return placements;
}

// Per-edge keyframe names — each drifts in from its own screen edge.
const ANIM: Record<Edge, string> = {
  top:   'cd-enter-top',
  left:  'cd-enter-left',
  right: 'cd-enter-right',
};

export default function CornerDecorations() {
  const pathname = usePathname() ?? '/';
  const items = buildPlacements(pathname);

  return (
    <div
      className="fixed inset-0 pointer-events-none overflow-hidden"
      style={{ zIndex: 9 }}
      aria-hidden="true"
    >
      {items.map((img, i) => (
        <img
          key={`${pathname}-${i}`}
          src={img.src}
          alt=""
          draggable={false}
          style={{
            ...img.style,
            animationName: ANIM[img.edge],
            animationDuration: '600ms',
            animationTimingFunction: 'cubic-bezier(0.22, 1, 0.36, 1)',
            animationFillMode: 'both',
            animationDelay: `${img.delay}ms`,
          }}
        />
      ))}
    </div>
  );
}
