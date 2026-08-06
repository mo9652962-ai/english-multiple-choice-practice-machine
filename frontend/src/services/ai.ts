// AI 英语刷题机 — 前端 AI 客户端 (直接调 DeepSeek API，不依赖后端)
// 手机端 PWA 模式下，AI 功能通过此客户端直接调用

import { queryOne } from './db'

let cachedKey: string | null = null

async function getApiKey(): Promise<string> {
  if (cachedKey) return cachedKey
  try {
    // 从 sql.js 数据库读取 AI 配置
    const profile = queryOne(
      "SELECT api_key_encrypted, base_url FROM ai_profiles WHERE enabled = 1 AND is_default = 1"
    )
    if (profile?.api_key_encrypted) {
      // 简化：直接存明文（开发用途；生产环境用 DPAPI 但浏览器不可用）
      cachedKey = profile.api_key_encrypted
    }
  } catch {
    // 数据库未初始化时 fallback
  }
  return cachedKey || ''
}

export async function setApiKey(key: string) {
  cachedKey = key
}

export async function chatCompletion(
  messages: { role: string; content: string }[],
  options: { temperature?: number; max_tokens?: number } = {}
): Promise<string> {
  const key = await getApiKey()
  if (!key) throw new Error('请先在设置中配置 DeepSeek API Key')

  const resp = await fetch('https://api.deepseek.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model: 'deepseek-v4-flash',
      messages,
      temperature: options.temperature ?? 0.2,
      max_tokens: options.max_tokens ?? 1200,
    }),
  })

  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`AI 调用失败: ${resp.status} ${err}`)
  }

  const data = await resp.json()
  return data.choices?.[0]?.message?.content || ''
}

/** 从 JSON 响应中提取数组 */
export function parseJsonResponse(text: string): any {
  try {
    return JSON.parse(text)
  } catch {
    // 尝试提取 JSON 块
    const match = text.match(/```json\s*([\s\S]*?)```/)
    if (match) return JSON.parse(match[1])
    const match2 = text.match(/\[[\s\S]*\]/)
    if (match2) return JSON.parse(match2[0])
    return []
  }
}