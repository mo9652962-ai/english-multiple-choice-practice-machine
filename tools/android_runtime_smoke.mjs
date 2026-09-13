#!/usr/bin/env node

/**
 * Install and exercise the Android debug APK on an already booted device or
 * emulator.  The script is intentionally independent of the emulator
 * launcher so it can run in CI and against a physical device.
 */
import { execFileSync } from 'node:child_process'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)))
const DEFAULT_APK = resolve(ROOT, 'frontend/android/app/build/outputs/apk/debug/app-debug.apk')
const DEFAULT_EVIDENCE = resolve(ROOT, 'android-emulator-evidence')

function parseArgs(argv) {
  const values = {
    apk: DEFAULT_APK,
    packageName: 'com.moti.englishpractice',
    versionFile: resolve(ROOT, 'VERSION'),
    evidenceDir: DEFAULT_EVIDENCE,
    adb: process.env.ADB || 'adb',
    extendedInput: false,
    offline: false,
    emulatorRotation: false,
  }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    const next = argv[index + 1]
    if (arg === '--apk' && next) values.apk = resolve(next)
    else if (arg === '--package' && next) values.packageName = next
    else if (arg === '--version-file' && next) values.versionFile = resolve(next)
    else if (arg === '--evidence-dir' && next) values.evidenceDir = resolve(next)
    else if (arg === '--adb' && next) values.adb = resolve(next)
    else if (arg === '--extended-input') values.extendedInput = true
    else if (arg === '--offline') values.offline = true
    else if (arg === '--emulator-rotation') values.emulatorRotation = true
    else if (arg === '--help') {
      console.log('Usage: node tools/android_runtime_smoke.mjs [--apk path] [--package id] [--version-file path] [--evidence-dir path] [--adb path] [--extended-input] [--offline] [--emulator-rotation]')
      process.exit(0)
    }
  }
  return values
}

const options = parseArgs(process.argv.slice(2))
mkdirSync(options.evidenceDir, { recursive: true })

function adb(args, { allowFailure = false } = {}) {
  try {
    return execFileSync(options.adb, args, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
      timeout: 120_000,
    }).replaceAll('\r\n', '\n')
  } catch (error) {
    const stdout = String(error.stdout || '')
    const stderr = String(error.stderr || '')
    if (allowFailure) return `${stdout}${stderr}`
    throw new Error(`adb ${args.join(' ')} failed:\n${stdout}${stderr}`)
  }
}

function writeEvidence(name, content) {
  writeFileSync(resolve(options.evidenceDir, name), String(content), 'utf8')
}

function wait(milliseconds) {
  return new Promise(resolveWait => setTimeout(resolveWait, milliseconds))
}

function assertRunning(stage) {
  if (!adb(['shell', 'pidof', options.packageName]).trim()) {
    throw new Error(`Android application did not expose a running pid after ${stage}`)
  }
}

function orientationOf(displayDump) {
  const match = displayDump.match(/mCurrentOrientation=(\d+)|SurfaceOrientation:\s*(\d+)|\borientation=(\d+)/i)
  return match ? Number(match[1] || match[2] || match[3]) : null
}

async function exerciseInputAndRotation() {
  // These are intentionally opt-in because input injection and rotation alter
  // the foreground state of a physical device. CI enables the flag on its
  // disposable emulator; the default smoke remains safe for local devices.
  const beforeRotation = adb(['shell', 'dumpsys', 'display'], { allowFailure: true })
  const beforeOrientation = orientationOf(beforeRotation)
  let rotated = false
  let rotatedDump = ''
  const rotationCommand = options.emulatorRotation ? 'adb emu rotate' : 'adb shell wm set-user-rotation lock 1'
  try {
    adb(['shell', 'input', 'tap', '120', '240'])
    adb(['shell', 'input', 'text', 'epm_smoke'])
    adb(['shell', 'input', 'keyevent', '66'])
    if (options.emulatorRotation) adb(['emu', 'rotate'])
    else adb(['shell', 'wm', 'set-user-rotation', 'lock', '1'])
    rotated = true
    await wait(1_000)
    rotatedDump = adb(['shell', 'dumpsys', 'display'], { allowFailure: true })
    const afterOrientation = orientationOf(rotatedDump)
    if (afterOrientation === null || (beforeOrientation !== null && afterOrientation === beforeOrientation)) {
      throw new Error('Android orientation did not change during smoke test')
    }
    assertRunning('touch, keyboard, and rotation input')
  } finally {
    if (rotated) {
      if (options.emulatorRotation) adb(['emu', 'rotate'], { allowFailure: true })
      else adb(['shell', 'wm', 'set-user-rotation', 'free'], { allowFailure: true })
    }
  }
  await wait(500)
  const restored = adb(['shell', 'dumpsys', 'display'], { allowFailure: true })
  const restoredOrientation = orientationOf(restored)
  if (beforeOrientation !== null && restoredOrientation !== null && restoredOrientation !== beforeOrientation) {
    throw new Error('Android orientation was not restored after smoke test')
  }
  writeEvidence('input-rotation.txt', [
    'touch=sent',
    'keyboard=sent',
    `rotation_command=${rotationCommand}`,
    'before_rotation=',
    beforeRotation,
    'rotated=',
    rotatedDump,
    'restored=',
    restored,
  ].join('\n'))
}

async function exerciseOfflineLaunch() {
  try {
    adb(['shell', 'cmd', 'connectivity', 'airplane-mode', 'enable'])
    await wait(1_000)
    adb(['shell', 'am', 'force-stop', options.packageName])
    adb(['shell', 'monkey', '-p', options.packageName, '1'])
    await wait(3_000)
    assertRunning('offline launch')
    writeEvidence('offline.txt', 'airplane_mode=enabled\noffline_launch=ok\n')
  } finally {
    adb(['shell', 'cmd', 'connectivity', 'airplane-mode', 'disable'], { allowFailure: true })
  }
}

let failure = null
try {
  const expectedVersion = readFileSync(options.versionFile, 'utf8').trim()
  adb(['wait-for-device'])
  adb(['install', '-r', options.apk])
  const packageInfo = adb(['shell', 'dumpsys', 'package', options.packageName])
  if (!packageInfo.includes(`versionName=${expectedVersion}`)) {
    throw new Error(`Android package version mismatch: expected ${expectedVersion}`)
  }

  adb(['logcat', '-c'])
  adb(['shell', 'monkey', '-p', options.packageName, '1'])
  await wait(5_000)
  assertRunning('launch')
  const activities = adb(['shell', 'dumpsys', 'activity', 'activities'])
  if (!activities.includes(options.packageName)) {
    throw new Error('Android activity dump does not contain the application package')
  }
  const smokeLog = adb(['logcat', '-d', '-s', 'EPM_ANDROID_SMOKE:I', '*:S'])
  if (!smokeLog.includes('keystore_round_trip=ok provider=AndroidKeyStore')) {
    throw new Error('Android Keystore round-trip evidence was not found in logcat')
  }

  if (options.extendedInput) await exerciseInputAndRotation()
  if (options.offline) await exerciseOfflineLaunch()

  adb(['shell', 'am', 'force-stop', options.packageName])
  adb(['shell', 'monkey', '-p', options.packageName, '1'])
  await wait(3_000)
  assertRunning('force-stop restart')

  writeEvidence('package.txt', packageInfo)
  writeEvidence('activities.txt', activities)
  writeEvidence('logcat.txt', adb(['logcat', '-d'], { allowFailure: true }))
  console.log(`Android runtime smoke passed: package=${options.packageName}, version=${expectedVersion}, keystore=ok`)
} catch (error) {
  failure = error
} finally {
  writeEvidence('package.txt', adb(['shell', 'dumpsys', 'package', options.packageName], { allowFailure: true }))
  writeEvidence('activities.txt', adb(['shell', 'dumpsys', 'activity', 'activities'], { allowFailure: true }))
  writeEvidence('logcat.txt', adb(['logcat', '-d'], { allowFailure: true }))
}

if (failure) {
  console.error(`Android runtime smoke failed: ${failure.message}`)
  process.exit(1)
}
