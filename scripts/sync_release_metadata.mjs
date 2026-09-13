import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readText(name, fallback = '') {
  try {
    const value = fs.readFileSync(path.join(projectRoot, name), 'utf8').trim()
    return value || fallback
  } catch {
    return fallback
  }
}

const manifest = JSON.parse(
  fs.readFileSync(path.join(projectRoot, 'content-manifest.json'), 'utf8'),
)
const metadata = {
  version: readText('VERSION'),
  release_date: readText('RELEASE_DATE'),
  content_version: readText('CONTENT_VERSION'),
  offline_seed_version: readText('OFFLINE_CONTENT_VERSION'),
  schema_version: Number(manifest.schema_version || 0),
}

for (const [key, value] of Object.entries(metadata)) {
  if (!value || (key === 'schema_version' && value < 1)) {
    throw new Error(`发布元数据缺少 ${key}`)
  }
}

const payload = {
  manifest_version: 1,
  metadata,
  content: {
    release: manifest.release || {},
    offline_seed: manifest.offline_seed || {},
    share_policy: manifest.share_policy || {},
    quality_policy: manifest.quality_policy || {},
  },
  platforms: {
    web: { metadata_source: 'release-metadata.json' },
    android: { metadata_source: 'release-metadata.json', version_source: 'VERSION' },
    windows: { metadata_source: 'release-metadata.json', version_source: 'VERSION' },
  },
}

const outputPath = path.join(projectRoot, 'frontend', 'public', 'release-metadata.json')
fs.writeFileSync(outputPath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
console.log(`Release metadata synchronized: ${path.relative(projectRoot, outputPath)}`)
