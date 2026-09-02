import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.moti.englishpractice',
  appName: '墨题英语刷题',
  webDir: 'dist',
  // v10.4: 允许 https(localhost) 页面访问 http 局域网后端（聊天室 WS + API 探测）
  android: {
    allowMixedContent: true,
  },
  // v9.27: Gemini UI4——移动端键盘 resizeMode（输入时 WebView 视口自动缩小防遮挡）
  plugins: {
    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
  },
};

export default config;
