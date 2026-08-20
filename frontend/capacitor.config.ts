import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.moti.englishpractice',
  appName: '墨题英语刷题',
  webDir: 'dist',
  // v9.27: Gemini UI4——移动端键盘 resizeMode（输入时 WebView 视口自动缩小防遮挡）
  plugins: {
    Keyboard: {
      resize: 'body',
      resizeOnFullScreen: true,
    },
  },
};

export default config;
