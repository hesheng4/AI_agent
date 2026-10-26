import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

// Vite 配置 — 构建到 dist/，由 FastAPI 服务
// base: '/static/' 让构建产物引用 /static/assets/...，与后端 app.mount('/static') 对齐
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      // base 与 vite base 对齐，确保 SW 资源路径正确
      base: '/static/',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      workbox: {
        // E8: 离线缓存策略
        globPatterns: ['**/*.{js,css,html,svg,png,woff,woff2}'],
        // 预缓存上限 2MB（超出走 runtime caching）
        maximumFileSizeToCacheInBytes: 2 * 1024 * 1024,
        runtimeCaching: [
          // API 响应一律不落盘缓存（隐私）：/auth/me、/billing/usage、
          // /library/papers 等已认证私人响应写入 Cache Storage 后，
          // 共享机器上离线 5 分钟内可读。API 可用性由网络层保证。
          {
            urlPattern: /^https?:\/\/[^/]*\/api\/v1\/.*$/,
            handler: 'NetworkOnly',
          },
          // 字体 — CacheFirst（长期缓存）
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-stylesheets',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-webfonts',
              expiration: { maxEntries: 30, maxAgeSeconds: 60 * 60 * 24 * 365 },
            },
          },
          // FontAwesome CDN — CacheFirst
          {
            urlPattern: /^https:\/\/cdnjs\.cloudflare\.com\/.*$/,
            handler: 'CacheFirst',
            options: {
              cacheName: 'fontawesome',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      manifest: {
        name: '墨观 · 学术天文台',
        short_name: '墨观',
        description: '一站式科研协作平台：文献检索、引用图谱、实验设计、论文写作',
        theme_color: '#16110D',
        background_color: '#16110D',
        display: 'standalone',
        scope: '/static/',
        start_url: '/static/',
        lang: 'zh-CN',
        icons: [
          { src: '/static/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/static/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: '/static/icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  base: '/static/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/static': 'http://localhost:8000',
    },
  },
});
