import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv, type ProxyOptions } from "vite";

const API_PATHS = [
  "/jobs",
  "/applications",
  "/interviews",
  "/hiring",
  "/health",
];

export default defineConfig(({ mode }) => {
  // Read .env / .env.local so the API port can be set per machine without
  // editing this file or remembering a shell variable.
  const env = loadEnv(mode, process.cwd(), "");

  const target = env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

  // The API is a separate FastAPI service in development. Proxying keeps every
  // request same-origin, so the app needs no CORS config and no base-URL
  // switching between dev and a production build.
  const apiProxy: ProxyOptions = {
    target,
    changeOrigin: true,
    configure: (proxy) => {
      proxy.on("error", (error: Error & { code?: string }) => {
        if (error.code === "ECONNREFUSED") {
          // The default proxy error is a bare stack trace; say what to do
          // about it instead.
          console.error(
            `\n[api] Nothing is listening on ${target}.\n` +
              `      Start the backend:  uv run uvicorn app.main:app --reload --port 8000\n` +
              `      Or set a different port in Frontend/.env.local:\n` +
              `      VITE_API_TARGET=http://127.0.0.1:8090\n`,
          );
        }
      });
    },
  };

  return {
    plugins: [react()],

    server: {
      port: 5173,
      proxy: Object.fromEntries(API_PATHS.map((path) => [path, apiProxy])),
    },

    build: {
      // FastAPI serves the build from app/static/dashboard, so assets must be
      // requested from that prefix rather than the site root.
      outDir: "../app/static/dashboard",
      emptyOutDir: true,
    },

    base: "/dashboard/",
  };
});
