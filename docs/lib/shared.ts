export const appName = 'PyMediate';
export const appTagline = 'A typed mediator for Python';
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
 * `repoId` and `categoryId` are public, non-secret values (not tokens) — the ones
 * the configurator at https://giscus.app generates for this repo and its "Comments"
 * discussion category. Threads map to article pages by pathname.
 */
export const giscusConfig = {
  repo: `${gitConfig.user}/${gitConfig.repo}`,
  repoId: 'R_kgDOQExYuA',
  category: 'Comments',
  categoryId: 'DIC_kwDOQExYuM4DBAXt',
} as const;

/**
 * Base path the site is served under (e.g. `/pymediate` on GitHub Pages).
 * Inlined at build time; empty in local dev unless set.
 */
export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';
