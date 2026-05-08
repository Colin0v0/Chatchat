/// <reference types="node" />

import { cp, readdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const projectRoot = dirname(fileURLToPath(import.meta.url));
const publicDir = resolve(projectRoot, "public");
const distDir = resolve(projectRoot, "dist");
const isMountedWindowsFs =
  process.platform === "linux" && process.cwd().startsWith("/mnt/");
const usePolling =
  process.env.CHOKIDAR_USEPOLLING === "true" || isMountedWindowsFs;
const devApiOrigin = process.env.CHATCHAT_DEV_API_ORIGIN?.trim() || "http://127.0.0.1:8050";
const allowedHosts = Array.from(
  new Set([
    "colin.tailbfa0dd.ts.net",
    ...(process.env.CHATCHAT_DEV_ALLOWED_HOSTS ?? "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  ]),
);
const REACT_CORE_PACKAGES = ["react", "react-dom", "scheduler", "react-router", "react-router-dom"];
const MARKDOWN_PACKAGES = [
  "react-markdown",
  "remark-gfm",
  "remark-math",
  "rehype-katex",
  "unified",
  "micromark",
  "mdast-util",
  "hast-util",
  "unist-util",
  "vfile",
  "property-information",
  "space-separated-tokens",
  "comma-separated-tokens",
  "decode-named-character-reference",
  "markdown-table",
  "trim-lines",
  "trough",
  "zwitch",
];
const DIAGRAM_GRAPH_PACKAGES = ["cytoscape", "cytoscape-cose-bilkent", "dagre", "elkjs"];

function hasNodePackage(id: string, packageNames: string[]) {
  const normalizedId = id.replaceAll("\\", "/");
  return packageNames.some((packageName) => normalizedId.includes(`/node_modules/${packageName}/`));
}

function manualChunkForVendor(id: string) {
  if (!id.includes("node_modules")) {
    return;
  }

  // 中文注释：按真实依赖链拆包，避免 React/Markdown/Mermaid 的子依赖又回流进主包。
  if (hasNodePackage(id, REACT_CORE_PACKAGES)) {
    return "react-core";
  }

  if (hasNodePackage(id, ["lucide-react"])) {
    return "ui-icons";
  }

  if (hasNodePackage(id, ["katex"])) {
    return "math-rendering";
  }

  if (hasNodePackage(id, MARKDOWN_PACKAGES)) {
    return "markdown-runtime";
  }

  if (hasNodePackage(id, DIAGRAM_GRAPH_PACKAGES)) {
    return "diagram-graph";
  }
}

function copyRuntimePublicAssets() {
  return {
    name: "chatchat-copy-runtime-public-assets",
    apply: "build" as const,
    async closeBundle() {
      const entries = await readdir(publicDir, { withFileTypes: true });
      await Promise.all(
        entries
          // 宠物源素材和调试切帧保留在仓库里，但生产包只需要 import 进来的 src 资产。
          .filter((entry) => entry.name !== "pets")
          .map((entry) => cp(resolve(publicDir, entry.name), resolve(distDir, entry.name), { recursive: true })),
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), copyRuntimePublicAssets()],
  server: {
    host: "0.0.0.0",
    port: 5200,
    strictPort: true,
    watch: usePolling
      ? {
          usePolling: true,
          interval: 150,
        }
      : undefined,
    allowedHosts,
    proxy: {
      "/api": devApiOrigin,
      "/media": devApiOrigin,
    },
  },
  build: {
    copyPublicDir: false,
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: manualChunkForVendor,
      },
    },
  },
});
