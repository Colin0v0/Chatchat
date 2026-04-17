/// <reference types="node" />

import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const isMountedWindowsFs =
  process.platform === "linux" && process.cwd().startsWith("/mnt/");
const usePolling =
  process.env.CHOKIDAR_USEPOLLING === "true" || isMountedWindowsFs;
const devApiOrigin = process.env.CHATCHAT_DEV_API_ORIGIN?.trim() || "http://127.0.0.1:8050";
const allowedHosts = (process.env.CHATCHAT_DEV_ALLOWED_HOSTS ?? "")
  .split(",")
  .map((item) => item.trim())
  .filter(Boolean);

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
    ...(allowedHosts.length ? { allowedHosts } : {}),
    proxy: {
      "/api": devApiOrigin,
      "/media": devApiOrigin,
    },
  },
  build: {
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
