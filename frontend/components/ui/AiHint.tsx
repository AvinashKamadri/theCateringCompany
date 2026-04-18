'use client';

import { Sparkles } from 'lucide-react';
import { useState, useEffect } from 'react';

interface AiHintProps {
  message: string;
  /** Tooltip placement relative to the icon. Defaults to bottom-left. */
  placement?: 'bottom-left' | 'bottom-right' | 'top-right' | 'top-left';
  /** Milliseconds between auto-peek animations. Default 12_000. */
  peekEveryMs?: number;
}

/**
 * Small AI icon that pulses periodically to draw the eye and shows a
 * tooltip message on hover. Use beside action buttons where users might
 * not know what the action does.
 */
export default function AiHint({
  message,
  placement = 'bottom-left',
  peekEveryMs = 12_000,
}: AiHintProps) {
  const [peeking, setPeeking] = useState(false);

  useEffect(() => {
    // Peek once shortly after mount, then on an interval.
    const initial = window.setTimeout(() => setPeeking(true), 1_200);
    const off1 = window.setTimeout(() => setPeeking(false), 4_500);
    const interval = window.setInterval(() => {
      setPeeking(true);
      window.setTimeout(() => setPeeking(false), 3_200);
    }, peekEveryMs);
    return () => {
      window.clearTimeout(initial);
      window.clearTimeout(off1);
      window.clearInterval(interval);
    };
  }, [peekEveryMs]);

  const pos = {
    'bottom-left':  'top-full mt-2 right-0',
    'bottom-right': 'top-full mt-2 left-0',
    'top-left':     'bottom-full mb-2 right-0',
    'top-right':    'bottom-full mb-2 left-0',
  }[placement];

  return (
    <span className="relative inline-flex group">
      <span
        className={`inline-flex h-7 w-7 items-center justify-center rounded-full cursor-help select-none
                    bg-gradient-to-br from-neutral-800 to-black text-white
                    shadow-[inset_0_1px_0_rgba(255,255,255,0.15),0_4px_12px_-4px_rgba(0,0,0,0.4)]
                    transition-transform duration-300
                    group-hover:scale-110 ${peeking ? 'tc-ai-peek' : ''}`}
        aria-label="AI hint"
      >
        <Sparkles className="h-3.5 w-3.5" />
      </span>
      <span
        className={`absolute ${pos} z-20 w-60 rounded-xl px-3 py-2 text-xs leading-snug
                    bg-neutral-900 text-neutral-100 shadow-xl border border-neutral-800
                    opacity-0 -translate-y-1 pointer-events-none
                    group-hover:opacity-100 group-hover:translate-y-0
                    ${peeking ? 'opacity-100 translate-y-0' : ''}
                    transition-all duration-200`}
      >
        {message}
      </span>
    </span>
  );
}
