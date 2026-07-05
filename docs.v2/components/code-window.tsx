import { highlight } from 'fumadocs-core/highlight';
import { cn } from '@/lib/cn';

/**
 * A macOS-style window frame around server-highlighted Python code.
 * Uses the same shiki themes as the docs code blocks; theme switching is
 * handled by fumadocs' `.shiki` CSS via the `--shiki-light/dark` variables.
 */
export async function CodeWindow({
  code,
  title,
  className,
}: {
  code: string;
  title?: string;
  className?: string;
}) {
  const rendered = await highlight(code, {
    lang: 'python',
    themes: { light: 'github-light-default', dark: 'poimandres' },
    defaultColor: false,
    components: {
      pre: (props) => (
        <pre
          {...props}
          className={cn(
            'shiki overflow-x-auto p-4 text-[13px] leading-relaxed',
            'bg-(--shiki-light-bg) dark:bg-(--shiki-dark-bg)',
          )}
        />
      ),
    },
  });

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-fd-border shadow-lg shadow-black/5 dark:shadow-black/30',
        className,
      )}
    >
      <div className="flex items-center gap-1.5 border-b border-fd-border bg-fd-card px-4 py-2.5">
        <span aria-hidden className="size-2.5 rounded-full bg-fd-foreground/15" />
        <span aria-hidden className="size-2.5 rounded-full bg-fd-foreground/15" />
        <span aria-hidden className="size-2.5 rounded-full bg-fd-foreground/15" />
        {title ? (
          <span className="ms-2 font-mono text-xs text-fd-muted-foreground">{title}</span>
        ) : null}
      </div>
      {rendered}
    </div>
  );
}
