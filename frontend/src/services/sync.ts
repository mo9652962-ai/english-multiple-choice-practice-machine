/**
 * 墨题 Local-First 跨端增量同步服务
 * 负责在 Web / Desktop / Android 设备间进行做题记录、FSRS 队列与错题本的双向增量对账。
 */

import { post, get } from '../api'
import { showToast } from './toast'

export interface SyncStatus {
  user_id: number | null
  is_authenticated: boolean
  server_counts: {
    learning_days: number
    wrong_stats: number
    fsrs_records: number
  }
}

export interface SyncExchangeResult {
  status: string
  server_time: string
  pushed_summary: {
    learning_days: number
    wrong_stats: number
    fsrs_records: number
    collections: number
  }
  pull: {
    learning_days: any[]
    wrong_stats: any[]
    fsrs_records: any[]
    collections: any[]
  }
}

const SYNC_STORAGE_KEY = 'motei_last_synced_at'

export function getLastSyncTime(): string | null {
  try {
    return localStorage.getItem(SYNC_STORAGE_KEY)
  } catch {
    return null
  }
}

export function setLastSyncTime(isoTime: string): void {
  try {
    localStorage.setItem(SYNC_STORAGE_KEY, isoTime)
  } catch {
    // ignore
  }
}

/**
 * 执行跨端增量对账同步
 * @param pushOverrides 可选的客户端增量推送数据
 * @param silent 是否静默同步（不弹 toast）
 */
export async function triggerIncrementalSync(
  pushOverrides?: Record<string, any>,
  silent: boolean = false,
): Promise<SyncExchangeResult> {
  const lastSynced = getLastSyncTime()
  const payload = {
    client_time: new Date().toISOString(),
    last_synced_at: lastSynced,
    push: pushOverrides || {},
  }

  const result: any = await post('/sync/exchange', payload)
  if (result.server_time) {
    setLastSyncTime(result.server_time)
  }

  if (!silent) {
    const p = result.pushed_summary || {}
    const totalPushed = (p.learning_days || 0) + (p.wrong_stats || 0) + (p.fsrs_records || 0)
    const pull = result.pull || {}
    const totalPulled = (pull.learning_days?.length || 0) + (pull.wrong_stats?.length || 0) + (pull.fsrs_records?.length || 0)
    showToast(`云端同步完成：上传 ${totalPushed} 条 · 拉取 ${totalPulled} 条记录`, 'success')
  }

  return result as SyncExchangeResult
}

export async function fetchSyncStatus(): Promise<SyncStatus> {
  return (await get('/sync/status')) as SyncStatus
}
