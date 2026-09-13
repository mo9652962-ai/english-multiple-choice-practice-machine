import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const manifestPath = path.resolve(root, process.argv[2] || 'frontend/public/offline_migrations.json')
const sqlJsPath = path.join(root, 'frontend', 'node_modules', 'sql.js', 'dist', 'sql-wasm.js')

if (!fs.existsSync(manifestPath)) throw new Error(`offline migration manifest missing: ${manifestPath}`)
if (!fs.existsSync(sqlJsPath)) throw new Error(`sql.js runtime missing: ${sqlJsPath}`)

const { default: initSqlJs } = await import(pathToFileURL(sqlJsPath))
const SQL = await initSqlJs({ locateFile: file => path.join(path.dirname(sqlJsPath), file) })
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))

function quoteIdentifier(value) {
  return `"${String(value).replaceAll('"', '""')}"`
}

function existingObjects(db, objects) {
  const existing = new Set()
  const rows = db.exec("SELECT type, name FROM sqlite_master WHERE type IN ('table', 'index')")[0]
  for (const row of rows?.values || []) existing.add(`${row[0]}:${row[1]}`)

  for (const object of objects) {
    if (object.type !== 'column' || !object.name) continue
    const separator = object.name.indexOf('.')
    if (separator <= 0) continue
    const table = object.name.slice(0, separator)
    const result = db.exec(`PRAGMA table_info(${quoteIdentifier(table)})`)[0]
    for (const row of result?.values || []) existing.add(`column:${table}.${row[1]}`)
  }
  return existing
}

function missingObjects(db, objects = manifest.objects) {
  const existing = existingObjects(db, objects)
  return objects
    .filter(object => object?.sql && !existing.has(`${object.type}:${object.name}`))
    .sort((left, right) => ({ table: 0, column: 1, index: 2 }[left.type] ?? 3)
      - ({ table: 0, column: 1, index: 2 }[right.type] ?? 3))
}

function applyAll(db, objects = manifest.objects) {
  let applied = 0
  while (true) {
    const missing = missingObjects(db, objects)
    if (!missing.length) break
    db.run(missing[0].sql)
    applied += 1
    if (applied > objects.length) {
      throw new Error('offline runtime migration exceeded manifest object count')
    }
  }
  return applied
}

function tableColumns(db, table) {
  const result = db.exec(`PRAGMA table_info(${quoteIdentifier(table)})`)[0]
  return new Set((result?.values || []).map(row => String(row[1])))
}

// Exercise a legacy database: the old question SRS table exists, but does not
// have the new FSRS columns.  This is the path taken by existing IndexedDB
// copies after an application upgrade.
const legacy = new SQL.Database()
legacy.run(`
  CREATE TABLE questions (id INTEGER PRIMARY KEY);
  CREATE TABLE spaced_repetition_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER DEFAULT NULL,
    question_id INTEGER NOT NULL,
    interval_days INTEGER NOT NULL DEFAULT 1,
    ease_factor REAL NOT NULL DEFAULT 2.5,
    review_date TEXT,
    due_date TEXT NOT NULL,
    UNIQUE (user_id, question_id)
  );
`)
const legacyObjects = manifest.objects.filter(object =>
  object.name === 'spaced_repetition_records'
  || object.name.startsWith('spaced_repetition_records.')
  || object.name === 'idx_spaced_repetition_due'
)
const legacyApplied = applyAll(legacy, legacyObjects)
const requiredFsrsColumns = ['fsrs_due', 'fsrs_stability', 'fsrs_difficulty', 'fsrs_state', 'fsrs_step', 'fsrs_last_review']
const legacyColumns = tableColumns(legacy, 'spaced_repetition_records')
const missingFsrs = requiredFsrsColumns.filter(column => !legacyColumns.has(column))
if (missingFsrs.length) throw new Error(`legacy runtime migration missing FSRS columns: ${missingFsrs.join(', ')}`)
if (missingObjects(legacy, legacyObjects).length) throw new Error('legacy runtime migration is not idempotent')

// Also verify that the same manifest can initialize a fresh offline database.
const fresh = new SQL.Database()
const freshApplied = applyAll(fresh)
const freshColumns = tableColumns(fresh, 'spaced_repetition_records')
if (requiredFsrsColumns.some(column => !freshColumns.has(column))) {
  throw new Error('fresh offline runtime schema is missing FSRS columns')
}

console.log(JSON.stringify({
  manifest: path.relative(root, manifestPath),
  objects: manifest.object_count,
  legacy_applied: legacyApplied,
  fresh_applied: freshApplied,
  fsrs_columns: requiredFsrsColumns,
  status: 'ok',
}, null, 2))

legacy.close()
fresh.close()
