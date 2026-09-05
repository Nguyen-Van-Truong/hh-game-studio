import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { hhWorldDemoBus } from "./vite.demo-bus.ts";

export default defineConfig({
  plugins: [react(), hhWorldDemoBus()],
  server: {
    host: "127.0.0.1",
    port: 5175,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 4175,
    strictPort: true,
  },
});
