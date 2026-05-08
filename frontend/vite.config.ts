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
    rollupOptions: {
      output: {
        manualChunks: {
          "react-core": ["react", "react-dom"],
          markdown: ["react-markdown", "remark-gfm"],
          "ui-icons": ["lucide-react"],
        },
      },
    },
  },
});
