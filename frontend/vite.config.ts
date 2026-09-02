import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import legacy from '@vitejs/plugin-legacy'

export default defineConfig({
  base: './',  // v9.20.1: 相对路径——5+App file:// 协议下 /assets 绝对路径 404
  plugins: [
    vue(),
    // v9.20.1: legacy 构建——5+App/安卓老 WebView 不支持 ES Module（file:// 下 CORS 拦截白屏）
    legacy({
      targets: ['Android >= 5', 'iOS >= 10', 'Chrome >= 49'],
      modernPolyfills: false,
    }),
  ],
  server: {
    port: 5173,
    proxy: {
      // v10.5: ws:true——聊天室 WebSocket(/api/chat/ws) 经 dev 代理转发后端，此前 dev 下永远"连接中"
      '/api': { target: 'http://127.0.0.1:8765', changeOrigin: true, ws: true },
    },
  },
})

