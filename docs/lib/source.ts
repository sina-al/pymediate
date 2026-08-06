import { docs } from 'collections/server';
import { loader } from 'fumadocs-core/source';
import { docsContentRoute, docsImageRoute, docsRoute } from './shared';

// See https://fumadocs.dev/docs/headless/source-api for more info
export const source = loader({
  baseUrl: docsRoute,
  source: docs.toFumadocsSource(),
  plugins: [],
});

export function getPageImage(page: (typeof source)['$inferPage']) {
  const segments = [...page.slugs, 'image.png'];

  return {
    segments,
    url: `${docsImageRoute}/${segments.join('/')}`,
  };
}

export function getPageMarkdownUrl(page: (typeof source)['$inferPage']) {
  const segments = [...page.slugs, 'content.md'];

  return {
    segments,
    url: `${docsContentRoute}/${segments.join('/')}`,
  };
}

// Markers consumed by the repo's doc-example test runner (`poe test:docs`, which executes
// every python fence on this site). They are invisible in the rendered page but would
// otherwise show up verbatim in the raw markdown these routes serve, so strip them here —
// the single choke point shared by /llms.mdx/**/content.md and /llms-full.txt.
const PMD_METADATA_COMMENT = /^[ \t]*\{\/\*\s*pmd-(?:metadata|note):.*?\*\/\}[ \t]*\r?\n\r?\n?/gm;

export async function getLLMText(page: (typeof source)['$inferPage']) {
  const processed = await page.data.getText('processed');

  return `# ${page.data.title} (${page.url})

${processed.replace(PMD_METADATA_COMMENT, '')}`;
}
