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

type Placement = {
  src: string;
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

  // ── TOP edge — 4 images spread horizontally, partially cropped at top ──
  const topPositions = [8, 28, 68, 88]; // % from left
  for (const leftPct of topPositions) {
    const size = w();
    placements.push({ src: src(idx++), style: {
      position: 'absolute',
      top: -(size * 0.35),
      left: `${leftPct}%`,
      width: size,
      transform: `translateX(-50%) rotate(${rot()}deg)`,
      opacity: op(),
    }});
  }

  // ── LEFT edge — 3 images spread vertically ──
  const leftPositions = [18, 45, 75];
  for (const topPct of leftPositions) {
    const size = w();
    placements.push({ src: src(idx++), style: {
      position: 'absolute',
      left: -(size * 0.4),
      top: `${topPct}%`,
      width: size,
      transform: `translateY(-50%) rotate(${rot()}deg)`,
      opacity: op(),
    }});
  }

  // ── RIGHT edge — 3 images spread vertically ──
  const rightPositions = [22, 50, 78];
  for (const topPct of rightPositions) {
    const size = w();
    placements.push({ src: src(idx++), style: {
      position: 'absolute',
      right: -(size * 0.4),
      top: `${topPct}%`,
      width: size,
      transform: `translateY(-50%) rotate(${rot()}deg)`,
      opacity: op(),
    }});
  }

  return placements;
}

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
        <img key={i} src={img.src} alt="" draggable={false} style={img.style} />
      ))}
    </div>
  );
}
