import { createMDX } from 'fumadocs-mdx/next';

const withMDX = createMDX();

// Set NEXT_PUBLIC_BASE_PATH (e.g. "/pymediate") when deploying under a
// sub-path such as GitHub Pages. Leave unset for local dev / root deploys.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH;

/** @type {import('next').NextConfig} */
const config = {
  output: 'export',
  reactStrictMode: true,
  ...(basePath ? { basePath } : {}),
};

export default withMDX(config);
