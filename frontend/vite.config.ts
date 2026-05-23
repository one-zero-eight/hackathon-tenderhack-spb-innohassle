import { defineConfig, loadEnv } from 'vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxyTarget = (env.VITE_DEV_PROXY_TARGET || 'http://api:8000').replace(/\/$/, '')
  const targetOrigin = proxyTarget.replace(/\/api$/, '')
  const stripApiPrefix = /^https?:\/\/(api|localhost|127\.0\.0\.1)(:\d+)?$/i.test(targetOrigin)

  return {
    server: {
      proxy: {
        '/api': {
          target: targetOrigin,
          changeOrigin: true,
          // Caddy/public API keeps /api; direct FastAPI container serves /prices/* without prefix.
          rewrite: stripApiPrefix ? (path) => path.replace(/^\/api/, '') : (path) => path,
        },
        '/search-api': {
          target: targetOrigin,
          changeOrigin: true,
        },
        '/yandex-suggest': {
          target: 'https://suggest.yandex.ru',
          changeOrigin: true,
          rewrite: () => '/suggest-ya.cgi',
        },
      },
      watch: {
        usePolling: true,
      },
      host: true,
    },
    plugins: [
      tanstackRouter({
        target: 'react',
        semicolons: true,
        quoteStyle: 'single',
        autoCodeSplitting: true,
        routeFileIgnorePrefix: '-',
        routesDirectory: 'src/app/routes',
        generatedRouteTree: 'src/app/routeTree.gen.ts',
      }),
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
      },
    },
  }
})
