// v9.21: 离线库自动迁移（任务 E 收尾·问题 1）
// 按随包发布的 offline_migrations.json（由 scripts/migrate_frontend_db.py 从
// backend/app/database.py 的 SCHEMA 导出）检测并补建缺失的表/索引。
//
// 为什么需要：离线模式首次启动把 public/question_bank.db seed 进 IndexedDB，
// 之后一直优先使用 IndexedDB 里的副本——即使新版打包文件包含新表，存量设备的
// 旧副本也不会更新。本模块在每次启动时按清单比对 sqlite_master，缺什么建什么，
// 让旧副本自动升级（如 question_explanations 表）。
//
// 算法纯幂等：清单只含 CREATE TABLE/INDEX IF NOT EXISTS，且执行前先检测对象
// 是否存在；无变更时不写 IndexedDB（避免每次启动导出整库）。

import type { Database } from 'sql.js'

export interface MigrationObject {
  type: 'table' | 'index'
  name: string
  sql: string
}

export interface MigrationManifest {
  version: string
  fingerprint: string
  object_count: number
  objects: MigrationObject[]
}

const MIGRATIONS_URL = '/offline_migrations.json'

/** 比对清单与库内 sqlite_master，返回需要执行的对象（表先于索引，保证依赖顺序）。 */
export function planMissingObjects(
  db: Database,
  manifest: MigrationManifest,
): MigrationObject[] {
  const existing = new Set<string>()
  const result = db.exec(
    "SELECT type, name FROM sqlite_master WHERE type IN ('table', 'index')",
  )
  for (const resultSet of result) {
    const typeIndex = resultSet.columns.indexOf('type')
    const nameIndex = resultSet.columns.indexOf('name')
    for (const row of resultSet.values) {
      existing.add(`${row[typeIndex]}:${row[nameIndex]}`)
    }
  }
  const missing = (manifest.objects || []).filter(
    object => object && object.sql && !existing.has(`${object.type}:${object.name}`),
  )
  missing.sort((left, right) =>
    (left.type === 'table' ? 0 : 1) - (right.type === 'table' ? 0 : 1),
  )
  return missing
}

/**
 * 应用离线迁移。返回是否有变更（调用方据此决定是否 saveToIndexedDB）。
 * 清单缺失/拉取失败时静默返回 false——不阻塞离线功能启动。
 */
export async function applyOfflineMigrations(db: Database): Promise<boolean> {
  const resp = await fetch(MIGRATIONS_URL, { signal: AbortSignal.timeout(5000) })
  if (!resp.ok) return false
  const manifest: MigrationManifest = await resp.json()
  const missing = planMissingObjects(db, manifest)
  if (!missing.length) return false
  for (const object of missing) {
    db.run(object.sql)
  }
  console.info(
    `[offline] schema 迁移：补建 ${missing.length} 个对象`
    + `（${missing.map(object => object.name).join(', ')}）`
    + `，清单版本 ${manifest.version}`,
  )
  return true
}
