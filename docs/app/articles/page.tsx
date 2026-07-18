import Link from 'next/link';
import type { Metadata } from 'next';
import { ArrowRight } from 'lucide-react';
import { articlesSource, formatArticleDate, readingTimeMinutes } from '@/lib/articles';

export const metadata: Metadata = {
  title: 'Articles',
  description:
    'Long-form essays on coupling, application architecture, and the ideas behind PyMediate.',
};

export default async function ArticlesIndex() {
  const pages = [...articlesSource.getPages()].sort((a, b) =>
    b.data.date.localeCompare(a.data.date),
  );
  const entries = await Promise.all(
    pages.map(async (page) => ({ page, minutes: await readingTimeMinutes(page) })),
  );

  return (
    <main className="flex-1">
      <section className="relative overflow-hidden">
        <div aria-hidden className="pm-hero-glow absolute inset-0" />
        <div aria-hidden className="pm-grid-bg absolute inset-0" />
        <div className="relative mx-auto max-w-3xl px-6 pt-20 pb-12">
          <h1 className="pm-fade-up text-4xl font-semibold tracking-tight">Articles</h1>
          <p
            className="pm-fade-up mt-4 max-w-xl text-pretty text-fd-muted-foreground"
            style={{ animationDelay: '60ms' }}
          >
            Long-form articles about coupling, application architecture, and the design
            context for PyMediate. Release notes are published on GitHub.
          </p>
        </div>
      </section>

      <section className="mx-auto flex max-w-3xl flex-col gap-4 px-6 pb-24">
        {entries.map(({ page, minutes }) => (
          <Link
            key={page.url}
            href={page.url}
            className="group rounded-xl border border-fd-border bg-fd-card/50 p-6 transition-colors hover:border-fd-primary/40 sm:p-8"
          >
            <p className="font-mono text-xs text-fd-muted-foreground">
              {formatArticleDate(page.data.date)} · {minutes} min read
            </p>
            <h2 className="mt-3 text-xl font-semibold tracking-tight sm:text-2xl">
              {page.data.title}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-fd-muted-foreground">
              {page.data.description}
            </p>
            <span className="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-fd-primary">
              Read the article
              <ArrowRight
                aria-hidden
                className="size-4 transition-transform group-hover:translate-x-0.5"
              />
            </span>
          </Link>
        ))}
      </section>
    </main>
  );
}
