import { useId } from 'react';
import { cn } from '@/lib/cn';

/**
 * The PyMediate "dispatch node" mark: message paths converging through a
 * single gradient node. Original artwork — renders crisply down to 16px.
 */
export function LogoMark({ className, size = 24 }: { className?: string; size?: number }) {
  const id = useId();
  const gradient = `pm-mark-${id}`;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="PyMediate"
      className={className}
    >
      <defs>
        <linearGradient id={gradient} x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#22d3ee" />
          <stop offset="1" stopColor="#8b5cf6" />
        </linearGradient>
      </defs>
      {/* four message paths, tapering as they approach the node */}
      <path d="M3.2 5.4 L5.4 3.2 L11.7 11.7 Z" fill={`url(#${gradient})`} opacity="0.85" />
      <path d="M26.6 3.2 L28.8 5.4 L20.3 11.7 Z" fill={`url(#${gradient})`} opacity="0.6" />
      <path d="M3.2 26.6 L5.4 28.8 L11.7 20.3 Z" fill={`url(#${gradient})`} opacity="0.6" />
      <path d="M28.8 26.6 L26.6 28.8 L20.3 20.3 Z" fill={`url(#${gradient})`} opacity="0.85" />
      {/* the dispatch node */}
      <path d="M16 9.4 L22.6 16 L16 22.6 L9.4 16 Z" fill={`url(#${gradient})`} />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2 font-semibold tracking-tight', className)}>
      <LogoMark size={22} />
      <span className="text-[15px]">pymediate</span>
    </span>
  );
}
