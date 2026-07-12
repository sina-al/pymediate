import Link from 'next/link';
import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { articlesSource, formatArticleDate, readingTimeMinutes } from '@/lib/articles';
import { getMDXComponents } from '@/components/mdx';
import { Comments } from '@/components/comments';

export default async function ArticlePage(props: PageProps<'/articles/[slug]'>) {
  const { slug } = await props.params;
  const page = articlesSource.getPage([slug]);
  if (!page) notFound();

  const MDX = page.data.body;
  const minutes = await readingTimeMinutes(page);

  return (
    <main className="flex-1">
      <section className="relative overflow-hidden">
        <div aria-hidden className="pm-hero-glow absolute inset-0" />
        <div aria-hidden className="pm-grid-bg absolute inset-0" />
        <header className="relative mx-auto max-w-2xl px-6 pt-16 pb-10">
          <Link
            href="/articles"
            className="inline-flex items-center gap-1.5 text-sm text-fd-muted-foreground transition-colors hover:text-fd-foreground"
          >
            <ArrowLeft aria-hidden className="size-4" />
            Articles
          </Link>
          <h1 className="mt-6 text-balance text-4xl font-semibold tracking-tight sm:text-5xl">
            {page.data.title}
          </h1>
          <p className="mt-5 text-pretty text-lg text-fd-muted-foreground">
            {page.data.description}
          </p>
          <div className="mt-7 flex items-center gap-3 text-sm text-fd-muted-foreground">
            {/* plain <img>: the site is statically exported, so next/image would not optimize it anyway */}
            <img
              src={`https://github.com/${page.data.author}.png?size=96`}
              alt=""
              width={32}
              height={32}
              className="size-8 rounded-full border border-fd-border"
            />
            <a
              href={`https://github.com/${page.data.author}`}
              rel="noreferrer noopener"
              className="font-medium text-fd-foreground transition-colors hover:text-fd-primary"
            >
              {page.data.author}
            </a>
            <span aria-hidden>·</span>
            <time dateTime={page.data.date}>{formatArticleDate(page.data.date)}</time>
            <span aria-hidden>·</span>
            <span>{minutes} min read</span>
          </div>
        </header>
      </section>

      <article className="prose mx-auto max-w-2xl px-6 pb-16">
        <MDX components={getMDXComponents()} />
      </article>

      <section className="mx-auto max-w-2xl px-6 pb-24">
        <div className="pm-gradient-border rounded-2xl p-8 text-center">
          <p className="text-fd-muted-foreground">
            Want to see what this looks like in practice?
          </p>
          <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
            <Link
              href="/docs/getting-started/quick-start"
              className="inline-flex items-center gap-1.5 rounded-full bg-fd-primary px-5 py-2.5 text-sm font-medium text-fd-primary-foreground transition-opacity hover:opacity-90"
            >
              Quick start
              <ArrowRight aria-hidden className="size-4" />
            </Link>
            <Link
              href="/docs"
              className="inline-flex items-center rounded-full border border-fd-border px-5 py-2.5 text-sm font-medium transition-colors hover:bg-fd-accent"
            >
              Introduction
            </Link>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-2xl px-6 pb-24">
        <h2 className="mb-6 text-lg font-semibold tracking-tight">Comments</h2>
        <Comments />
      </section>
    </main>
  );
}

export function generateStaticParams() {
  return articlesSource.getPages().map((page) => ({ slug: page.slugs[0] }));
}

export async function generateMetadata(
  props: PageProps<'/articles/[slug]'>,
): Promise<Metadata> {
  const { slug } = await props.params;
  const page = articlesSource.getPage([slug]);
  if (!page) notFound();

  return {
    title: page.data.title,
    description: page.data.description,
  };
}
