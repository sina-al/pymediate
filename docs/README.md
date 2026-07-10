# docs

PyMediate's documentation site — a Next.js application generated with
[Create Fumadocs](https://github.com/fuma-nama/fumadocs), with
[Static Export](https://nextjs.org/docs/app/guides/static-exports) configured. It is
built and deployed to GitHub Pages (<https://pymediate.sina-al.uk>) by
`.github/workflows/docs.yml` on pushes to `main`.

Site content is MDX under `content/` (`content/docs/` for the Docs section,
`content/articles/` for long-form essays). The `adr/` directory is *not* part of the
site — it holds the repo's architecture decision records, versioned here but deliberately
unpublished.

Run the development server (from the repo root, via [poe](../tasks.toml)):

```bash
uv run poe docs:install   # once
uv run poe docs:serve     # pnpm dev
uv run poe docs:check     # lint + type-check, same as CI
uv run poe docs:build     # static build into out/
```

or directly with `pnpm` from this directory. Open http://localhost:3000 with your
browser to see the result.

## Explore

In the project, you can see:

- `lib/source.ts`: Code for content source adapter, [`loader()`](https://fumadocs.dev/docs/headless/source-api) provides the interface to access your content.
- `lib/layout.shared.tsx`: Shared options for layouts, optional but preferred to keep.

| Route                     | Description                                            |
| ------------------------- | ------------------------------------------------------ |
| `app/(home)`              | The route group for your landing page and other pages. |
| `app/docs`                | The documentation layout and pages.                    |
| `app/api/search/route.ts` | The Route Handler for search.                          |

### Fumadocs MDX

A `source.config.ts` config file has been included, you can customise different options like frontmatter schema.

Read the [Introduction](https://fumadocs.dev/docs/mdx) for further details.

## Learn More

To learn more about Next.js and Fumadocs, take a look at the following
resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js
  features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.
- [Fumadocs](https://fumadocs.dev) - learn about Fumadocs
