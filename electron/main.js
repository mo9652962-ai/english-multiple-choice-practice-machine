// AI 英语刷题机 - Electron 桌面应用主进程
// 职责: 启动 Python 后端 → 等待健康检查 → 创建窗口加载前端
// v9.20: 自动更新（electron-updater, 启动+每10分钟检查）
const { app, BrowserWindow, dialog } = require('electron')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const http = require('http')

const PORT = 8765
const URL = `http://127.0.0.1:${PORT}`

let backendProc = null
let mainWindow = null

// ---------- 自动更新（仅打包版启用） ----------
let autoUpdater = null
function setupAutoUpdater() {
  if (!app.isPackaged) return
  try {
    autoUpdater = require('electron-updater').autoUpdater
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
    })
    // 启动时检查 + 每 10 分钟轮询
    autoUpdater.checkForUpdatesAndNotify()
    setInterval(() => {
      autoUpdater.checkForUpdatesAndNotify()
    }, 10 * 60 * 1000)
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
  const py = findPython()
  if (!py) {
    dialog.showErrorBox('启动失败', '未找到 Python，请安装 Python 3.10+ 并加入 PATH')
    return false
  }
  const projectDir = app.isPackaged
    ? path.join(process.resourcesPath, 'app')
    : __dirname
  const runScript = path.join(projectDir, 'run_app.py')
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
