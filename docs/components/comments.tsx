'use client';

import Giscus from '@giscus/react';
import type { Theme } from '@giscus/react';
import { useTheme } from 'next-themes';
import { giscusConfig } from '@/lib/shared';

/**
 * Map the site's resolved next-themes value to a Giscus theme. Before the theme
 * provider has resolved (server render / first client paint) we fall back to
 * `preferred_color_scheme`, so a reader with a dark OS preference still sees the
 * widget in dark on first paint; once resolved it tracks the explicit toggle.
 */
function giscusTheme(resolved: string | undefined): Theme {
  if (resolved === 'dark') return 'dark';
  if (resolved === 'light') return 'light';
  return 'preferred_color_scheme';
}

/**
 * GitHub Discussions comment thread for a page, rendered via Giscus.
 *
 * Threads map to the page's pathname and live in the repo's "Comments"
 * category. The widget is additive: if the Giscus script is blocked the rest of
 * the page still renders. Repo/category IDs come from `giscusConfig`.
 */
export function Comments() {
  const { resolvedTheme } = useTheme();

  return (
    <Giscus
      repo={giscusConfig.repo as `${string}/${string}`}
      repoId={giscusConfig.repoId}
      category={giscusConfig.category}
      categoryId={giscusConfig.categoryId}
      mapping="pathname"
      reactionsEnabled="1"
      emitMetadata="0"
      inputPosition="top"
      theme={giscusTheme(resolvedTheme)}
      lang="en"
      loading="lazy"
    />
  );
}
