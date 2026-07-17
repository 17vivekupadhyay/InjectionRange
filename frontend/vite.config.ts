import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In Docker Compose the backend is reachable as http://backend:8000 (service name);
// for local `npm run dev` it's http://localhost:8000. Configurable via env.
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": target,
      "/health": target,
    },
  },
});
