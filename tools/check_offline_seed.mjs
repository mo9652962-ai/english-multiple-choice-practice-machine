import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const valueFor = (flag, fallback) => {
  const index = process.argv.indexOf(flag)
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback
}

const dbPath = path.resolve(root, valueFor('--db', 'frontend/public/question_bank.db'))
const manifestPath = path.resolve(root, valueFor('--migrations', 'frontend/public/offline_migrations.json'))
const sqlJsPath = path.join(root, 'frontend', 'node_modules', 'sql.js', 'dist', 'sql-wasm.js')

if (!fs.existsSync(dbPath)) throw new Error(`offline database missing: ${dbPath}`)
if (!fs.existsSync(manifestPath)) throw new Error(`offline migration manifest missing: ${manifestPath}`)
if (!fs.existsSync(sqlJsPath)) throw new Error(`sql.js runtime missing: ${sqlJsPath}`)

const { default: initSqlJs } = await import(pathToFileURL(sqlJsPath))
const SQL = await initSqlJs({
  locateFile: file => path.join(path.dirname(sqlJsPath), file),
})
const db = new SQL.Database(fs.readFileSync(dbPath))
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))

if (!manifest.fingerprint || !Number.isInteger(manifest.object_count)) {
  throw new Error('offline migration manifest is missing fingerprint/object_count')
}
if (!Array.isArray(manifest.objects) || manifest.objects.length !== manifest.object_count) {
  throw new Error('offline migration manifest object_count does not match objects')
}

const spacedObject = manifest.objects.find(
  object => object.type === 'table' && object.name === 'spaced_repetition_records',
)
if (!spacedObject || !/fsrs_due/.test(spacedObject.sql) || !/fsrs_state/.test(spacedObject.sql)) {
  throw new Error('offline migration manifest missing FSRS columns in spaced_repetition_records')
}
const requiredFsrsMigrations = ['fsrs_due', 'fsrs_stability', 'fsrs_difficulty', 'fsrs_state', 'fsrs_step', 'fsrs_last_review']
const missingFsrsMigrations = requiredFsrsMigrations.filter(
  column => !manifest.objects.some(object => object.type === 'column' && object.name === `spaced_repetition_records.${column}`),
)
if (missingFsrsMigrations.length) {
  throw new Error(`offline migration manifest missing FSRS column migrations: ${missingFsrsMigrations.join(', ')}`)
}

const tableNames = new Set(
  db.exec("SELECT name FROM sqlite_master WHERE type='table'")[0]?.values.map(row => String(row[0])) || [],
)
const requiredTables = ['papers', 'units', 'questions', 'options', 'vocabulary_entries']
const missingTables = requiredTables.filter(name => !tableNames.has(name))
if (missingTables.length) throw new Error(`offline database missing tables: ${missingTables.join(', ')}`)
const spacedColumns = new Set(
  db.exec('PRAGMA table_info(spaced_repetition_records)')[0]?.values.map(row => String(row[1])) || [],
)
if (missingFsrsMigrations.some(column => !spacedColumns.has(column))) {
  throw new Error('offline database missing FSRS columns in spaced_repetition_records')
}

const count = table => Number(db.exec(`SELECT COUNT(*) FROM "${table}"`)[0].values[0][0])
const counts = Object.fromEntries(requiredTables.map(table => [table, count(table)]))
const structural = {
  papers_without_units: Number(db.exec("SELECT COUNT(*) FROM papers p WHERE p.deleted_at IS NULL AND NOT EXISTS (SELECT 1 FROM units u WHERE u.paper_id=p.id)")[0].values[0][0]),
  units_without_questions: Number(db.exec("SELECT COUNT(*) FROM units u WHERE NOT EXISTS (SELECT 1 FROM questions q WHERE q.unit_id=u.id)")[0].values[0][0]),
  questions_without_options: Number(db.exec("SELECT COUNT(*) FROM questions q WHERE NOT EXISTS (SELECT 1 FROM options o WHERE o.question_id=q.id)")[0].values[0][0]),
}
if (Object.values(structural).some(value => value !== 0)) {
  throw new Error(`offline database structural gate failed: ${JSON.stringify(structural)}`)
}

console.log(JSON.stringify({
  db: path.relative(root, dbPath),
  migrations: path.relative(root, manifestPath),
  migration_objects: manifest.object_count,
  counts,
  structural,
}, null, 2))
db.close()
