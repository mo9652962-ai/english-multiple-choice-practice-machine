import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import legacy from '@vitejs/plugin-legacy'
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const readMetadata = (name: string, fallback: string) => {
  try {
    const value = readFileSync(resolve(projectRoot, name), 'utf8').trim()
    return value || fallback
  } catch {
    return fallback
  }
}

const appVersion = readMetadata('VERSION', '2.1.3')
const releaseDate = readMetadata('RELEASE_DATE', '2026-09-13')
const contentVersion = readMetadata('CONTENT_VERSION', 'content-2026-09-13-r1')
const offlineContentVersion = readMetadata('OFFLINE_CONTENT_VERSION', 'offline-2026-09-13-r1')

export default defineConfig({
  base: './',  // v9.20.1: 相对路径——5+App file:// 协议下 /assets 绝对路径 404
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
    __APP_RELEASE_DATE__: JSON.stringify(releaseDate),
    __CONTENT_VERSION__: JSON.stringify(contentVersion),
    __OFFLINE_CONTENT_VERSION__: JSON.stringify(offlineContentVersion),
  },
  plugins: [
    vue(),
    // v9.20.1: legacy 构建——5+App/安卓老 WebView 不支持 ES Module（file:// 下 CORS 拦截白屏）
    legacy({
      targets: ['Android >= 5', 'iOS >= 10', 'Chrome >= 49'],
      modernPolyfills: false,
    }),
  ],
  build: {
    // Keep a machine-readable graph for CI bundle-budget checks.
    manifest: true,
    // Keep Vite's warning aligned with the repository's 512/1024 KiB gates.
    // Heavy speech/Whisper assets are lazy by design; manual chunks keep the
    // runtime libraries out of the VAD and page chunks where possible.
    chunkSizeWarningLimit: 1024,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalized = id.replaceAll('\\\\', '/')
          if (normalized.includes('/node_modules/@huggingface/transformers/')) {
            return 'speech-transformers'
          }
          if (normalized.includes('/node_modules/onnxruntime-web/')) {
            return 'speech-onnx-runtime'
          }
          if (normalized.includes('/node_modules/xsai-transformers/')) {
            return 'speech-whisper-runtime'
          }
          return undefined
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      // v10.5: ws:true——聊天室 WebSocket(/api/chat/ws) 经 dev 代理转发后端，此前 dev 下永远"连接中"
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true, ws: true },
    },
  },
})

