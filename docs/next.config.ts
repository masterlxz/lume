import type { NextConfig } from "next";
import { createMDX } from "fumadocs-mdx/next";

const withMDX = createMDX();

// Set by the "Deploy Docs" GitHub Actions workflow to produce a static
// export for GitHub Pages (see .github/workflows/deploy-docs.yml). Unset
// (the default) for local dev/docker-compose, which runs `next dev`/`next
// start` against the live API and needs dynamic rendering (the reference
// pages call openapi.preloadOpenAPIPage() at request time in dev).
const basePath = process.env.NEXT_BASE_PATH;

const nextConfig: NextConfig = {
  ...(basePath
    ? {
        output: "export",
        basePath,
        images: { unoptimized: true },
        // Without this, `/docs` exports as the flat file `docs.html`, and
        // GitHub Pages 404s on `/docs/` (trailing slash) since there's no
        // `docs/index.html` — confirmed live (masterlxz.github.io/lume/docs/
        // 404'd before this). `index.html`-per-folder output works for both
        // slash variants everywhere static hosts serve directory indexes.
        trailingSlash: true,
      }
    : {}),
};

export default withMDX(nextConfig);
