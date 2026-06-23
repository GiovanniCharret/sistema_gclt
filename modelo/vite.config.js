import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Mock de design (Classificação de Beneficiários / Anexo V) — porta 5175.
export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    port: 5175,
  },
});
