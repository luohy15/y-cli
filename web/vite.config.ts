import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  server: {
    proxy: {
      "/v1": "http://localhost:8000",
      "/auth": "http://localhost:8000",
    },
  },
});
