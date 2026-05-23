import { defineConfig } from 'vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
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
})
