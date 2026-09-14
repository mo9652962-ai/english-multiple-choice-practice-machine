import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const versionPath = path.join(projectRoot, 'VERSION')
const gradlePath = path.join(projectRoot, 'frontend', 'android', 'app', 'build.gradle')
const version = fs.readFileSync(versionPath, 'utf8').trim()

if (!/^\d+\.\d+\.\d+$/.test(version)) {
  throw new Error(`VERSION 不是合法的三段式版本号：${version}`)
}
if (!fs.existsSync(gradlePath)) {
  throw new Error(`未找到 Capacitor Android 项目：${gradlePath}`)
}

let source = fs.readFileSync(gradlePath, 'utf8')
const marker = "    def epmVersion = file('../../../VERSION').text.trim()"
if (!source.includes(marker)) {
  const compileSdkLine = /(^\s*compileSdk\s+[^\r\n]+\r?\n)/m
  const injected = [
    marker,
    '    def epmVersionParts = epmVersion.tokenize(\'.\')',
    '    def epmVersionCode = epmVersionParts[0].toInteger() * 10000 + epmVersionParts[1].toInteger() * 100 + epmVersionParts[2].toInteger()',
  ].join('\n') + '\n'
  if (!compileSdkLine.test(source)) {
    throw new Error('无法定位 compileSdk 行，未修改 Android 版本文件')
  }
  source = source.replace(compileSdkLine, `$1${injected}`)
}

const signingMarker = '    // EPM_RELEASE_SIGNING_CONFIG'
if (!source.includes(signingMarker)) {
  const signingBlock = [
    signingMarker,
    "    def epmReleaseRequested = gradle.startParameter.taskNames.any { it.toLowerCase().contains('release') }",
    "    def epmKeystoreFile = System.getenv('EPM_ANDROID_KEYSTORE_FILE')",
    "    def epmKeystorePassword = System.getenv('EPM_ANDROID_KEYSTORE_PASSWORD')",
    "    def epmKeyAlias = System.getenv('EPM_ANDROID_KEY_ALIAS')",
    "    def epmKeyPassword = System.getenv('EPM_ANDROID_KEY_PASSWORD')",
    '    def epmHasReleaseSigning = [epmKeystoreFile, epmKeystorePassword, epmKeyAlias, epmKeyPassword].every { it }',
    '    if (epmReleaseRequested && !epmHasReleaseSigning) {',
    '        throw new GradleException("assembleRelease requires EPM_ANDROID_KEYSTORE_FILE, EPM_ANDROID_KEYSTORE_PASSWORD, EPM_ANDROID_KEY_ALIAS, and EPM_ANDROID_KEY_PASSWORD")',
    '    }',
    '    if (epmHasReleaseSigning) {',
    '        signingConfigs {',
    '            release {',
    '                storeFile file(epmKeystoreFile)',
    '                storePassword epmKeystorePassword',
    '                keyAlias epmKeyAlias',
    '                keyPassword epmKeyPassword',
    '            }',
    '        }',
    '    }',
  ].join('\n') + '\n'
  source = source.replace(/^android \{\r?\n/m, (match) => `${match}${signingBlock}`)
}

const releaseSigningLine = '            if (epmHasReleaseSigning) signingConfig signingConfigs.release'
if (!source.includes(releaseSigningLine)) {
  const releaseBlock = /(^\s*buildTypes\s*\{\r?\n\s*release\s*\{\r?\n)([\s\S]*?)(^\s*\})/m
  if (!releaseBlock.test(source)) {
    throw new Error('无法定位 Android release buildType，未写入签名配置')
  }
  source = source.replace(releaseBlock, `$1${releaseSigningLine}\n$2$3`)
}

source = source.replace(/(^\s*versionCode\s+)([^\r\n]+)/m, '$1epmVersionCode')
source = source.replace(/(^\s*versionName\s+)([^\r\n]+)/m, '$1epmVersion')
if (!source.includes('versionCode epmVersionCode') || !source.includes('versionName epmVersion')) {
  throw new Error('无法确认 Android versionCode/versionName 已绑定 VERSION')
}
fs.writeFileSync(gradlePath, source, 'utf8')
console.log(`Android version metadata synchronized: ${version}`)
