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
 * Base path the site is served under (e.g. `/pymediate` on GitHub Pages).
 * Inlined at build time; empty in local dev unless set.
 */
export const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? '';
