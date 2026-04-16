import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

const isMountedWindowsFs =
  process.platform === "linux" && process.cwd().startsWith("/mnt/");
const usePolling =
  process.env.CHOKIDAR_USEPOLLING === "true" || isMountedWindowsFs;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "0.0.0.0",
    port: 5200,
    watch: usePolling
      ? {
          usePolling: true,
          interval: 150,
        }
      : undefined,
    allowedHosts: ["colin.tailbfa0dd.ts.net"],
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/media": "http://127.0.0.1:8000",
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
