<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { get } from '../api'
import { CheckCircle2, ExternalLink, LoaderCircle, RotateCw, Sparkles } from 'lucide-vue-next'
import { trackMetric } from '../services/metrics'

// v3.3: 我的墨题——版本号 + 开发时间 + 检查更新
const APP_VERSION = __APP_VERSION__
const RELEASE_DATE = __APP_RELEASE_DATE__
const CONTENT_VERSION = __CONTENT_VERSION__
const OFFLINE_CONTENT_VERSION = __OFFLINE_CONTENT_VERSION__
const UPDATE_REPO = 'mo9652962-ai/english-multiple-choice-practice-machine'
const UPDATE_URL = `https://github.com/${UPDATE_REPO}/releases/latest`

const checking = ref(false)
const result = ref('')
const latest = ref('')
const hasNew = ref(false)
const downloadUrlRef = ref(UPDATE_URL)
const mirrors = ref<string[]>([])
const installing = ref(false)
const apkUrlRef = ref('')
const apkShaRef = ref('')
const releaseInfo = ref<any>(null)

async function loadReleaseInfo() {
  try {
    releaseInfo.value = await get('/content/version')
  } catch {
    // Offline mode still shows compile-time metadata below and can read the
    // same policy file shipped to Web/Android.
  }
  if (!releaseInfo.value?.content_policy?.offline_seed) {
    try {
      const response = await fetch('./release-metadata.json', { cache: 'no-store' })
      if (response.ok) {
        const payload = await response.json()
        releaseInfo.value = {
          ...(releaseInfo.value || {}),
          ...(payload.metadata || {}),
          content_policy: payload.content || {},
        }
      }
    } catch {
      // A broken metadata sidecar must not block the About page.
    }
  }
}

onMounted(() => { void loadReleaseInfo() })

// v3.3: 移动端下载 + SHA-256 校验 + 系统安装器（原生 OpenApkPlugin）
async function downloadAndInstall() {
  if (!apkUrlRef.value) return
  installing.value = true
  try {
    const isNative = !!(window as any)?.Capacitor?.isNativePlatform?.()
    if (!isNative) {
      window.open(apkUrlRef.value, '_blank')
      return
    }
    const { Filesystem, Directory } = await import('@capacitor/filesystem')
    const { Capacitor } = await import('@capacitor/core')
    result.value = '正在下载…'
    const resp = await fetch(apkUrlRef.value, { signal: AbortSignal.timeout(180000) })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const buf = await resp.arrayBuffer()
    // SHA-256 校验（GitHub asset digest）
    const digest = await crypto.subtle.digest('SHA-256', buf)
    const shaHex = [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
    if (apkShaRef.value && shaHex.toLowerCase() !== apkShaRef.value.toLowerCase()) {
      result.value = 'SHA-256 校验失败（文件可能损坏）'
      return
    }
    result.value = '校验通过，正在写入…'
    // base64 写入缓存
    const bytes = new Uint8Array(buf)
    let binary = ''
    const chunk = 0x8000
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk))
    }
    const base64 = btoa(binary)
    const file = await Filesystem.writeFile({
      path: 'update.apk',
      data: base64,
      directory: Directory.Cache,
      recursive: true,
    })
    result.value = '校验通过，正在打开安装器…'
    // 原生插件打开（FileProvider + ACTION_VIEW——系统安装确认）
    const path = file.uri.replace(/^file:\/\//, '')
    const OpenApk = (Capacitor as any).Plugins?.OpenApk
    if (!OpenApk) throw new Error('安装插件不可用')
    await OpenApk.openApk({ filePath: path })
    void trackMetric('install_succeeded', { source: 'about' })
    result.value = '已下载校验，请按系统提示安装'
  } catch (e) {
    void trackMetric('install_failed', { source: 'about' })
    result.value = '下载/安装失败：' + String(e).slice(0, 80)
  } finally {
    installing.value = false
  }
}

// 版本比较：正式版优先于同版本 beta，较新的 beta 优先于旧 beta。
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
      if (apk?.browser_download_url) {
        downloadUrl = apk.browser_download_url
        apkUrlRef.value = apk.browser_download_url
        apkShaRef.value = apk.digest || ''
      }
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
      <h3>墨题</h3>
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
          <span>内容版本</span>
          <strong>{{ CONTENT_VERSION }}</strong>
        </div>
        <div class="about-row">
          <span>离线种子</span>
          <strong>{{ OFFLINE_CONTENT_VERSION }}</strong>
        </div>
        <div v-if="releaseInfo?.schema_version" class="about-row">
          <span>数据库 Schema</span>
          <strong>v{{ releaseInfo.schema_version }}</strong>
        </div>
        <div v-if="releaseInfo?.counts?.questions" class="about-row">
          <span>当前库题目</span>
          <strong>{{ releaseInfo.counts.questions }}</strong>
        </div>
        <div v-if="releaseInfo?.database_sha256" class="about-row">
          <span>数据库指纹</span>
          <strong :title="releaseInfo.database_sha256">{{ releaseInfo.database_sha256.slice(0, 12) }}…</strong>
        </div>
        <div v-if="releaseInfo?.content_policy?.offline_seed" class="about-policy">
          <div>
            <span>离线内容范围</span>
            <strong>{{ releaseInfo.content_policy.offline_seed.is_complete ? '完整库' : '入门种子库' }}</strong>
          </div>
          <div>
            <span>导出 / 分享</span>
            <strong>{{ releaseInfo.content_policy.offline_seed.allow_export ? '允许' : '不允许' }} / {{ releaseInfo.content_policy.offline_seed.allow_share ? '允许' : '不允许' }}</strong>
          </div>
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
          <!-- v3.3: 移动端一键下载校验安装 -->
          <button v-if="apkUrlRef" class="about-install" type="button" :disabled="installing" @click="downloadAndInstall">
            <LoaderCircle v-if="installing" :size="14" class="spin" />{{ installing ? '下载安装中…' : '下载并安装' }}
          </button>
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
.page-about { max-width: min(100%, 1360px); margin: 0 auto; padding: 28px 24px 96px; width: 100%; box-sizing: border-box; }
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
.about-info { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; max-width: 900px; margin: 0 auto 24px; }
.about-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 11px 14px; border: 1px solid var(--line); border-radius: 10px;
  font-size: 13.5px;
}
.about-row span { color: var(--muted); }
.about-policy { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; max-width: 900px; margin: -4px auto 24px; }
.about-policy > div { display: flex; justify-content: space-between; gap: 12px; padding: 10px 14px; border-radius: 10px; background: color-mix(in srgb, var(--primary) 6%, transparent); font-size: 12.5px; text-align: left; }
.about-policy span { color: var(--muted); }
.about-check { width: 100%; max-width: 480px; margin: 0 auto; display: flex; align-items: center; justify-content: center; gap: 7px; }
.about-result {
  display: flex; align-items: center; justify-content: center; gap: 7px;
  margin-top: 14px; padding: 10px 14px; border-radius: 10px; font-size: 13.5px;
}
.about-result.ok { background: color-mix(in srgb, #486d5c 10%, transparent); color: #3c5c4d; }
.about-result.new { background: color-mix(in srgb, #c97b4a 12%, transparent); color: #a85f33; }
.about-download { display: inline-flex; align-items: center; gap: 4px; margin-left: 8px; font-weight: 700; color: #a85f33; text-decoration: underline; }
.about-install { display: inline-flex; align-items: center; gap: 6px; margin-left: 10px; padding: 6px 14px; border: 1px solid var(--primary); border-radius: 999px; background: var(--primary); color: #fff; font-size: 13px; font-weight: 600; cursor: pointer; }
.about-install:disabled { opacity: .6; cursor: wait; }
.about-mirrors { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; color: var(--muted); flex-wrap: wrap; justify-content: center; }
.about-mirrors a { color: var(--primary); text-decoration: underline; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
