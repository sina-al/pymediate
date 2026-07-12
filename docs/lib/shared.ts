export const appName = 'PyMediate';
export const appTagline = 'Type-safe request dispatch for modern Python';
export const docsRoute = '/docs';
export const docsImageRoute = '/og/docs';
export const docsContentRoute = '/llms.mdx/docs';

export const gitConfig = {
  user: 'sina-al',
  repo: 'pymediate',
  branch: 'main',
};

export const pypiUrl = 'https://pypi.org/project/pymediate/';

/**
 * Giscus configuration for the article comment threads.
 *
 * `repoId` and `categoryId` are public, non-secret values (not tokens) — generate
 * them from the configurator at https://giscus.app after two one-time setup steps:
 *
 *   1. Install the giscus GitHub App (https://github.com/apps/giscus) on the repo.
 *   2. Create a Discussions category named "Comments" using an *open* format
 *      (not the "Announcements" format — that restricts thread creation to
 *      maintainers and breaks commenting).
 *
 * Then paste the generated `repoId` / `categoryId` below, replacing the placeholders.
 * Threads map to article pages by pathname.
 */
export const giscusConfig = {
  repo: `${gitConfig.user}/${gitConfig.repo}`,
  // TODO(giscus setup): replace with the real repo ID from https://giscus.app
  repoId: 'PLACEHOLDER_REPO_ID',
  category: 'Comments',
  // TODO(giscus setup): replace with the "Comments" category ID from https://giscus.app
  categoryId: 'PLACEHOLDER_CATEGORY_ID',
} as const;

/**
 * Base path the site is served under (e.g. `/pymediate` on GitHub Pages).
 * Inlined at build time; empty in local dev unless set.
 */
export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';
