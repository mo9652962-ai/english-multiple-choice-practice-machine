import { copyFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = resolve(fileURLToPath(new URL('..', import.meta.url)))
const androidRoot = resolve(root, 'frontend', 'android')
const sourceRoot = resolve(root, 'frontend', 'native', 'android')

if (!existsSync(androidRoot)) {
  throw new Error('frontend/android 不存在，请先执行 npx cap add android')
}

const javaPackage = resolve(androidRoot, 'app', 'src', 'main', 'java', 'com', 'moti', 'englishpractice')
const resourceXml = resolve(androidRoot, 'app', 'src', 'main', 'res', 'xml')
mkdirSync(javaPackage, { recursive: true })
mkdirSync(resourceXml, { recursive: true })

for (const file of ['MainActivity.java', 'SecureStoragePlugin.java', 'OpenApkPlugin.java']) {
  copyFileSync(resolve(sourceRoot, 'com', 'moti', 'englishpractice', file), resolve(javaPackage, file))
}
copyFileSync(resolve(sourceRoot, 'file_paths.xml'), resolve(resourceXml, 'file_paths.xml'))

const manifestPath = resolve(androidRoot, 'app', 'src', 'main', 'AndroidManifest.xml')
let manifest = readFileSync(manifestPath, 'utf8')
const provider = `
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="\${applicationId}.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>`
if (!manifest.includes('androidx.core.content.FileProvider')) {
  manifest = manifest.replace(/\s*<\/application>/, `${provider}\n    </application>`)
}
if (!manifest.includes('android.permission.INTERNET')) {
  manifest = manifest.replace(/\s*<\/manifest>/, '    <uses-permission android:name="android.permission.INTERNET" />\n</manifest>')
}
writeFileSync(manifestPath, manifest)

console.log('Android native sources synced: SecureStorage/Keystore, OpenApk/FileProvider, MainActivity')
