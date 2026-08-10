<script setup lang="ts">
import { ref } from 'vue'
import { get } from '../api'
import { CheckCircle2, ExternalLink, LoaderCircle, RotateCw, Sparkles } from 'lucide-vue-next'

// v3.3: 我的墨题——版本号 + 开发时间 + 检查更新
const APP_VERSION = '2.0.0-beta.15'
const RELEASE_DATE = '2026-08-10'
const UPDATE_REPO = 'mo9652962-ai/epm-releases'
const UPDATE_URL = `https://github.com/${UPDATE_REPO}/releases/latest`

const checking = ref(false)
const result = ref('')
const latest = ref('')
const hasNew = ref(false)
const downloadUrlRef = ref(UPDATE_URL)
const mirrors = ref<string[]>([])

// beta 版本比较：2.0.0-beta.16 > 2.0.0-beta.15；正式版 > beta
function isNewer(latestTag: string, current: string): boolean {
  if (!latestTag) return false
  const norm = (v: string) => {
    const m = v.replace(/^v/, '').match(/(\d+)\.(\d+)\.(\d+)(?:-beta\.(\d+))?/)
    if (!m) return [0, 0, 0, 999]
    return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] ? Number(m[4]) : 999]
  }
  const a = norm(latestTag)
  const b = norm(current)
  for (let i = 0; i < 4; i++) {
    if (a[i] !== b[i]) return a[i] > b[i]
  }
  return false
}

async function checkUpdate() {
  checking.value = true
  result.value = ''
  latest.value = ''
  hasNew.value = false
  try {
    let tag = ''
    let downloadUrl = UPDATE_URL
    let mirrorUrls: string[] = []
    const isNative = !!(window as any)?.Capacitor?.isNativePlatform?.()
    if (isNative) {
      // 移动端：直接查 GitHub releases
      const resp = await fetch(`https://api.github.com/repos/${UPDATE_REPO}/releases/latest`, {
        headers: { Accept: 'application/vnd.github+json' },
        signal: AbortSignal.timeout(10000),
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const data = await resp.json()
      tag = data.tag_name || ''
      const apk = (data.assets || []).find((a: any) => a.name?.endsWith('.apk'))
      if (apk?.browser_download_url) downloadUrl = apk.browser_download_url
    } else {
      // 桌面：后端代理（含镜像回退 + 资产列表）
      const r: any = await get('/version')
      tag = r?.latest_version || ''
      mirrorUrls = r?.mirrors || []
      if (r?.assets?.length) {
        const exe = r.assets.find((a: any) => a.name?.endsWith('.exe'))
        if (exe?.url) downloadUrl = exe.url
      }
    }
    latest.value = tag
    downloadUrlRef.value = downloadUrl
    mirrors.value = mirrorUrls
    if (isNewer(tag, APP_VERSION)) {
      hasNew.value = true
      result.value = `发现新版本 ${tag}`
    } else {
      result.value = '已为最新版'
    }
  } catch (e) {
    result.value = '无法连接更新服务器'
  } finally {
    checking.value = false
  }
}
</script>

<template>
  <div class="page-about">
    <div class="page-head">
      <h2><Sparkles :size="20" /> 我的墨题</h2>
      <p class="muted">版本信息与更新检查</p>
    </div>

    <div class="about-card card">
      <div class="about-logo">墨</div>
      <h3>墨题 · 英语刷题机</h3>
      <p class="muted about-slogan">水墨之间 · 学海无涯</p>

      <div class="about-info">
        <div class="about-row">
          <span>当前版本</span>
          <strong>{{ APP_VERSION }}</strong>
        </div>
        <div class="about-row">
          <span>开发时间</span>
          <strong>{{ RELEASE_DATE }}</strong>
        </div>
        <div class="about-row">
          <span>更新通道</span>
          <strong>GitHub Releases</strong>
        </div>
      </div>

      <button class="button about-check" type="button" :disabled="checking" @click="checkUpdate">
        <LoaderCircle v-if="checking" :size="16" class="spin" />
        <RotateCw v-else :size="16" />
        {{ checking ? '检查中…' : '检查更新' }}
      </button>

      <div v-if="result" class="about-result" :class="{ new: hasNew, ok: !hasNew }">
        <template v-if="!hasNew">
          <CheckCircle2 :size="16" />{{ result }}
        </template>
        <template v-else>
          <Sparkles :size="16" />{{ result }}
          <a class="about-download" :href="downloadUrlRef" target="_blank" rel="noopener">
            获取最新版 <ExternalLink :size="13" />
          </a>
          <!-- v3.3: 镜像回退（国内可访问） -->
          <div v-if="mirrors.length" class="about-mirrors">
            <span>镜像下载：</span>
            <a v-for="(m, i) in mirrors" :key="i" :href="m" target="_blank" rel="noopener">镜像{{ i + 1 }}</a>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-about { max-width: 720px; margin: 0 auto; padding: 28px 20px 96px; }
.page-head h2 { display: flex; align-items: center; gap: 8px; margin: 0 0 6px; }
.about-card { padding: 32px 24px; text-align: center; }
.about-logo {
  width: 64px; height: 64px; margin: 0 auto 14px; border-radius: 18px;
  background: linear-gradient(135deg, #486d5c, #2d4a3c); color: #f3ede0;
  display: grid; place-items: center; font-size: 30px; font-weight: 800;
  box-shadow: 0 10px 28px -12px rgba(45, 74, 60, .45);
}
.about-card h3 { margin: 0 0 4px; font-size: 18px; }
.about-slogan { margin: 0 0 22px; font-size: 13px; }
.about-info { display: grid; gap: 10px; max-width: 420px; margin: 0 auto 22px; }
.about-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 14px; border: 1px solid var(--line); border-radius: 10px;
  font-size: 13.5px;
}
.about-row span { color: var(--muted); }
.about-check { width: 100%; max-width: 420px; margin: 0 auto; display: flex; align-items: center; justify-content: center; gap: 7px; }
.about-result {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  margin-top: 14px; padding: 10px 14px; border-radius: 10px; font-size: 13.5px;
}
.about-result.ok { background: color-mix(in srgb, #486d5c 10%, transparent); color: #3c5c4d; }
.about-result.new { background: color-mix(in srgb, #c97b4a 12%, transparent); color: #a85f33; }
.about-download { display: inline-flex; align-items: center; gap: 4px; margin-left: 8px; font-weight: 700; color: #a85f33; text-decoration: underline; }
.about-mirrors { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; color: var(--muted); flex-wrap: wrap; justify-content: center; }
.about-mirrors a { color: var(--primary); text-decoration: underline; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
