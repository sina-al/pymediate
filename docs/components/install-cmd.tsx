'use client';
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/cn';

export function InstallCmd({ className }: { className?: string }) {
  const [copyStatus, setCopyStatus] = useState<'idle' | 'copied' | 'failed'>('idle');

  async function copy() {
    try {
      await navigator.clipboard.writeText('pip install pymediate');
      setCopyStatus('copied');
    } catch {
      setCopyStatus('failed');
    }
    window.setTimeout(() => setCopyStatus('idle'), 1600);
  }

  return (
    <button
      type="button"
      onClick={() => void copy()}
      aria-label={copyStatus === 'failed' ? 'Copy failed; retry install command' : 'Copy install command'}
      className={cn(
        'group inline-flex items-center gap-3 rounded-full border border-transparent',
        'bg-fd-card/50 px-5 py-2.5 font-mono text-sm text-fd-foreground/90',
        'backdrop-blur transition-colors hover:border-fd-primary/40 hover:bg-fd-card',
        className,
      )}
    >
      <span aria-hidden className="select-none text-fd-muted-foreground">
        $
      </span>
      pip install pymediate
      {copyStatus === 'copied' ? (
        <Check aria-hidden className="size-4 text-fd-primary" />
      ) : copyStatus === 'failed' ? (
        <span className="font-sans text-xs text-fd-muted-foreground">Could not copy</span>
      ) : (
        <Copy
          aria-hidden
          className="size-4 text-fd-muted-foreground transition-colors group-hover:text-fd-foreground"
        />
      )}
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {copyStatus === 'copied'
          ? 'Install command copied.'
          : copyStatus === 'failed'
            ? 'The install command could not be copied.'
            : ''}
      </span>
    </button>
  );
}
