import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    // Optional face check (D-007): always the browser build of @vladmandic/human. Its package root resolves to the
    // Node build (needs @tensorflow/tfjs-node) when Next bundles client components for SSR.
    resolveAlias: { "@vladmandic/human": "./node_modules/@vladmandic/human/dist/human.esm.js" },
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
