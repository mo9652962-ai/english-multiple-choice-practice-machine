import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const args = process.argv.slice(2)
const valueFor = (name, fallback) => {
  const index = args.indexOf(name)
  return index >= 0 && args[index + 1] ? args[index + 1] : fallback
}

const dist = path.resolve(valueFor('--dist', 'frontend/dist'))
const maxEntryBytes = Number(valueFor('--max-entry-kb', '512')) * 1024
const maxLazyValue = valueFor('--max-lazy-kb', '')
const maxLazyBytes = maxLazyValue === '' ? null : Number(maxLazyValue) * 1024
const manifestCandidates = [
  path.join(dist, '.vite', 'manifest.json'),
  path.join(dist, 'manifest.json'),
]
const manifestPath = manifestCandidates.find((candidate) => fs.existsSync(candidate))
if (!manifestPath) {
  throw new Error(`未找到 Vite manifest：${manifestCandidates.join(', ')}`)
}

const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
const normalizedFile = (file) => file.replaceAll('\\', '/').replace(/^\.\//, '')
const entries = Object.entries(manifest)
  .filter(([, item]) => item?.isEntry && typeof item.file === 'string' && item.file.endsWith('.js'))
  .map(([name, item]) => {
    const file = normalizedFile(item.file)
    return { name, file, bytes: fs.statSync(path.join(dist, file)).size }
  })

if (!entries.length) {
  throw new Error('Vite manifest 中没有 JavaScript entry')
}

const failures = entries.filter((entry) => entry.bytes > maxEntryBytes)
const assets = []
const collect = (directory) => {
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name)
    if (item.isDirectory()) collect(full)
    else if (item.name.endsWith('.js')) assets.push({
      file: normalizedFile(path.relative(dist, full)),
      bytes: fs.statSync(full).size,
    })
  }
}
collect(dist)
const largestLazyChunks = assets
  .filter((asset) => !entries.some((entry) => entry.file === asset.file))
  .sort((left, right) => right.bytes - left.bytes)
  .slice(0, 8)
const lazyFailures = maxLazyBytes === null
  ? []
  : assets.filter((asset) => !entries.some((entry) => entry.file === asset.file) && asset.bytes > maxLazyBytes)

const report = {
  dist: path.relative(process.cwd(), dist),
  max_entry_bytes: maxEntryBytes,
  max_lazy_bytes: maxLazyBytes,
  entries: entries.map((entry) => ({ ...entry, size_kb: Math.round(entry.bytes / 1024) })),
  largest_lazy_chunks: largestLazyChunks.map((chunk) => ({
    ...chunk,
    size_kb: Math.round(chunk.bytes / 1024),
  })),
}
console.log(JSON.stringify(report, null, 2))
if (failures.length) {
  throw new Error(
    `入口 chunk 超过 ${Math.round(maxEntryBytes / 1024)} KiB：${failures.map((entry) => `${entry.file}=${entry.bytes}`).join(', ')}`,
  )
}
if (lazyFailures.length) {
  throw new Error(
    `按需 chunk 超过 ${Math.round(maxLazyBytes / 1024)} KiB：${lazyFailures.map((chunk) => `${chunk.file}=${chunk.bytes}`).join(', ')}`,
  )
}
