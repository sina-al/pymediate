import { articles } from 'collections/server';
import { loader } from 'fumadocs-core/source';

// See https://fumadocs.dev/docs/headless/source-api for more info
export const articlesSource = loader({
  baseUrl: '/articles',
  source: articles.toFumadocsSource(),
  plugins: [],
});

export type ArticlePage = (typeof articlesSource)['$inferPage'];

export async function readingTimeMinutes(page: ArticlePage): Promise<number> {
  const text = await page.data.getText('processed');
  const words = text.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

export function formatArticleDate(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
    timeZone: 'UTC',
  });
}
