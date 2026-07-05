'use client';
import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/cn';

export function InstallCmd({ className }: { className?: string }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    void navigator.clipboard.writeText('pip install pymediate');
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label="Copy install command"
      className={cn(
        'group inline-flex items-center gap-3 rounded-full border border-fd-border',
        'bg-fd-card/70 px-5 py-2.5 font-mono text-sm text-fd-foreground/90',
        'backdrop-blur transition-colors hover:border-fd-primary/40 hover:bg-fd-card',
        className,
      )}
    >
      <span aria-hidden className="select-none text-fd-muted-foreground">
        $
      </span>
      pip install pymediate
      {copied ? (
        <Check aria-hidden className="size-4 text-fd-primary" />
      ) : (
        <Copy
          aria-hidden
          className="size-4 text-fd-muted-foreground transition-colors group-hover:text-fd-foreground"
        />
      )}
    </button>
  );
}
