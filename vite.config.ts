import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const platform = process.env.TAURI_ENV_PLATFORM ?? process.platform;
const buildPlatform =
  platform === "win32" || platform === "windows"
    ? "windows"
    : platform === "darwin" || platform === "macos"
      ? "macos"
      : "linux";

export default defineConfig({
  plugins: [react()],
  define: {
    __BUILD_PLATFORM__: JSON.stringify(buildPlatform)
  },
  server: {
    port: 1420,
    strictPort: true
  }
});

