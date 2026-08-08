// AI 英语刷题机 - Electron 桌面应用主进程
// 职责: 启动 Python 后端 → 等待健康检查 → 创建窗口加载前端
// v9.21 (beta.2): 单实例锁 + crashReporter + 更新错误日志 + 数据备份提示
const { app, BrowserWindow, dialog } = require('electron')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const http = require('http')
const fs = require('fs')

// ---------- 单实例锁（防多开导致后端端口冲突） ----------
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.focus()
    }
  })
}

// ---------- 崩溃日志（内测反馈用，本地文件） ----------
try {
  const { crashReporter } = require('electron')
  crashReporter.start({
    productName: 'AI英语刷题机',
    companyName: 'MoSoftware',
    submitURL: '', // 不上报服务器，仅本地记录
    uploadToServer: false,
  })
} catch (e) { /* crashReporter 可选 */ }

// ---------- 未捕获异常处理（不弹窗，写日志） ----------
// v9.23 (beta.5): 修复 EPIPE 弹窗——console 写入失败等异常不再打断用户
process.on('uncaughtException', (err) => {
  try {
    const logDir = path.join(app.getPath('userData'), 'logs')
    fs.mkdirSync(logDir, { recursive: true })
    fs.appendFileSync(path.join(logDir, 'crash.log'),
      `${new Date().toISOString()} UNCAUGHT ${err && err.stack || err}\n`)
  } catch (e) { /* 日志失败忽略 */ }
  // 不弹窗、不退出——更新等后台任务失败可静默重试
})

const PORT = 8765
const URL = `http://127.0.0.1:${PORT}`

let backendProc = null
let mainWindow = null

// ---------- 自动更新（仅打包版启用） ----------
// v9.22 (beta.4): 双网络适配——GitHub 主源失败（中国无代理）→ 自动切 ghproxy 国内镜像
let autoUpdater = null
const GH_MIRROR = 'https://ghproxy.net/https://github.com/mo9652962-ai/epm-releases/releases/latest/download'
let mirrorMode = false

async function checkForUpdatesSmart() {
  if (!autoUpdater) return
  try {
    if (mirrorMode) {
      // 已切镜像：直接走镜像检查
      await autoUpdater.checkForUpdates()
      return
    }
    // 先试 GitHub 主源（短超时）
    await Promise.race([
      autoUpdater.checkForUpdates(),
      new Promise((_, rej) => setTimeout(() => rej(new Error('主源超时')), 20000)),
    ])
  } catch (err) {
    // 主源失败（超时/网络错误）→ 切国内镜像重试一次
    if (!mirrorMode) {
      mirrorMode = true
      console.error('[updater] 主源不可达，切换 ghproxy 国内镜像:', err.message)
      try {
        const logDir = path.join(app.getPath('userData'), 'logs')
        fs.mkdirSync(logDir, { recursive: true })
        fs.appendFileSync(path.join(logDir, 'updater.log'),
          `${new Date().toISOString()} SWITCH mirror (${err.message})\n`)
      } catch (e) { /* 日志失败忽略 */ }
      try {
        autoUpdater.setFeedURL({ provider: 'generic', url: GH_MIRROR })
        await autoUpdater.checkForUpdates()
      } catch (e2) {
        console.error('[updater] 镜像源也失败:', e2.message)
        mirrorMode = false // 下轮恢复主源
      }
    }
  }
}

function setupAutoUpdater() {
  if (!app.isPackaged) return
  try {
    autoUpdater = require('electron-updater').autoUpdater
    // v9.23 (beta.5): 禁用差分下载——150MB 安装包差分易出错，全量下载更稳
    autoUpdater.disableDifferentialDownload = true
    // 下载完提示重启（静默下载，不打扰使用）
    autoUpdater.on('update-downloaded', () => {
      if (mainWindow) {
        dialog.showMessageBox(mainWindow, {
          type: 'info',
          title: '更新已就绪',
          message: '新版本已下载完成，重启即可使用。',
          buttons: ['立即重启', '稍后'],
        }).then(({ response }) => {
          if (response === 0) autoUpdater.quitAndInstall()
        })
      }
    })
    autoUpdater.on('error', (err) => {
      console.error('[updater]', err && err.message)
      // 写入本地日志（内测反馈用）
      try {
        const logDir = path.join(app.getPath('userData'), 'logs')
        fs.mkdirSync(logDir, { recursive: true })
        fs.appendFileSync(path.join(logDir, 'updater.log'),
          `${new Date().toISOString()} ERROR ${err && err.message}\n`)
      } catch (e) { /* 日志失败忽略 */ }
    })
    // 启动时检查 + 每 10 分钟轮询（双网络适配）
    checkForUpdatesSmart()
    setInterval(checkForUpdatesSmart, 10 * 60 * 1000)
  } catch (e) {
    console.error('[updater] init failed:', e.message)
  }
}

// ---------- 后端管理 ----------
function findPython() {
  // 优先 pythonw（无控制台），回退 python。cmd 来自固定候选列表（无用户输入）
  const candidates = ['pythonw', 'python']
  for (const cmd of candidates) {
    try {
      const r = spawnSync(cmd, ['--version'], { stdio: 'ignore' })
      if (r.error === undefined) return cmd
    } catch (e) { /* try next */ }
  }
  return null
}

function startBackend() {
  // v9.21 (beta.2): 首次启动复制种子题库到用户数据目录（内置正式真题）
  try {
    const userDataDir = path.join(app.getPath('userData'), 'data')
    const userDb = path.join(userDataDir, 'question_bank.db')
    if (!fs.existsSync(userDb)) {
      const seedDb = path.join(process.resourcesPath, 'seed', 'question_bank.db')
      if (fs.existsSync(seedDb)) {
        fs.mkdirSync(userDataDir, { recursive: true })
        fs.copyFileSync(seedDb, userDb)
        console.log('[seed] 首次启动：内置真题库已就位')
      }
    }
  } catch (e) { console.error('[seed]', e.message) }
  // v9.20.1: 优先独立后端 exe（别人电脑无需 Python）；回退 python run_app.py（开发模式）
  const resources = process.resourcesPath
  const backendExe = path.join(resources, 'backend_app', 'backend_app.exe')
  const hasBackendExe = app.isPackaged && require('fs').existsSync(backendExe)
  if (hasBackendExe) {
    backendProc = spawn(backendExe, [], {
      windowsHide: true,
      stdio: 'ignore',
      env: {
        ...process.env,
        // v2.0-beta: 数据放用户目录（%APPDATA%），避免 Program Files 写入权限 + 杀软关注
        EPM_DATA_DIR: path.join(app.getPath('userData'), 'data'),
        EPM_FRONTEND_DIST: path.join(resources, 'frontend', 'dist'),
        EPM_HOST: '127.0.0.1',
        EPM_PORT: String(PORT),
      },
    })
    return true
  }
  const py = findPython()
  if (!py) {
    dialog.showErrorBox('启动失败', '未找到 Python，请安装 Python 3.10+ 并加入 PATH')
    return false
  }
  const projectDir = app.isPackaged
    ? path.join(resources, 'app')
    : __dirname
  const args = ['run_app.py', '--lan'] // 局域网模式：手机同 WiFi 可访问
  backendProc = spawn(py, args, {
    cwd: projectDir,
    windowsHide: true,
    stdio: 'ignore', // 隐藏后端控制台输出（日志写在文件）
  })
  return true
}

function waitForBackend(timeoutMs = 20000) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + timeoutMs
    const tick = () => {
      const req = http.get(`${URL}/api/health`, { timeout: 2000 }, (res) => {
        res.resume()
        if (res.statusCode === 200) resolve(true)
        else retry()
      })
      req.on('error', retry)
      req.on('timeout', () => { req.destroy(); retry() })
    }
    const retry = () => {
      if (Date.now() > deadline) reject(new Error('后端启动超时'))
      else setTimeout(tick, 300)
    }
    tick()
  })
}

function stopBackend() {
  if (backendProc && !backendProc.killed) {
    try { backendProc.kill() } catch (e) { /* ignore */ }
    backendProc = null
  }
}

// ---------- 窗口 ----------
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    title: 'AI 英语刷题机',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  })
  mainWindow.loadURL(URL)
  mainWindow.on('closed', () => { mainWindow = null })
}

// ---------- 生命周期 ----------
app.whenReady().then(async () => {
  setupAutoUpdater()  // v9.20: 自动更新（打包版）
  // 检查后端是否已在运行（用户之前手动启动过）
  const alreadyRunning = await new Promise((resolve) => {
    const req = http.get(`${URL}/api/health`, { timeout: 2000 }, (res) => {
      res.resume(); resolve(res.statusCode === 200)
    })
    req.on('error', () => resolve(false))
  })

  if (!alreadyRunning) {
    if (!startBackend()) return
    try {
      await waitForBackend()
    } catch (e) {
      dialog.showErrorBox('启动失败', `后端启动超时：\n${e.message}\n\n请检查 Python 环境和依赖 (pip install -r requirements.txt)`)
      return
    }
  }
  createWindow()
})

app.on('window-all-closed', () => {
  stopBackend() // 关闭窗口时停掉后端（桌面版专用）
  app.quit()
})

app.on('before-quit', stopBackend)
app.on('will-quit', stopBackend)
