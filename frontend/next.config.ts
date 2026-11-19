import type { NextConfig } from "next";

// API_URL se lee de frontend/.env.local (plantilla en frontend/.env.example).
// En Docker llega como variable de entorno desde docker-compose.yml.
// Puerto local por defecto de la API: 8001 (el 8000 suele estar ocupado por Docker Desktop).
const DEFAULT_API_URL = "http://127.0.0.1:8001";

function withoutTrailingSlashes(url: string): string {
  let end = url.length;
  while (end > 0 && url[end - 1] === "/") end--;
  return url.slice(0, end);
}

const nextConfig: NextConfig = {
  // Solo en `next dev`: permite abrir la app desde la IP de la red local (p. ej. http://192.168.1.10:3000
  // o desde el celular). Sin esto, Next bloquea su conexión de desarrollo y la página no termina de cargar.
  allowedDevOrigins: ["192.168.*.*"],
  turbopack: {
    root: process.cwd(),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  rewrites() {
    const apiUrl = withoutTrailingSlashes(process.env.API_URL || DEFAULT_API_URL);
    return Promise.resolve([
      { source: "/api/:path*", destination: `${apiUrl}/api/:path*` },
      { source: "/health", destination: `${apiUrl}/health` },
    ]);
  },
};

export default nextConfig;
