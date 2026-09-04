/**
 * 展示层选项清洗工具。
 *
 * 题库导入历史上可能把多个选项写进同一个 content 字段。本模块只生成
 * 展示层副本，不修改 session、question 或 option 原对象，也不负责保存修复结果。
 */

export interface PracticeOption {
  key?: string
  stable_key?: string
  label?: string
  content?: string
  [key: string]: unknown
}

export interface OptionSanitizeResult {
  dirty: boolean
  reason?: 'tab' | 'merged-labels'
  options: PracticeOption[]
  rawContent?: string
}

const OPTION_LABEL = /(?:^|[\s])([A-Da-d])[.．、)]\s*/g

function optionLabelMatches(content: string): RegExpMatchArray[] {
  OPTION_LABEL.lastIndex = 0
  return [...content.matchAll(OPTION_LABEL)]
}

function cloneWithOptionLabel(option: PracticeOption, label: string, content: string): PracticeOption {
  return {
    ...option,
    key: label,
    stable_key: label,
    label,
    content,
  }
}

function splitEmbeddedOptions(option: PracticeOption, content: string, matches: RegExpMatchArray[]): PracticeOption[] {
  const result: PracticeOption[] = []
  const firstIndex = matches[0]?.index ?? 0
  const prefix = content.slice(0, firstIndex).trim()
  if (prefix) result.push({ ...option, content: prefix })
  for (let index = 0; index < matches.length; index += 1) {
    const match = matches[index]
    const start = (match.index ?? 0) + match[0].length
    const end = matches[index + 1]?.index ?? content.length
    const piece = content.slice(start, end).trim()
    if (piece) result.push(cloneWithOptionLabel(option, match[1].toUpperCase(), piece))
  }
  return result
}

/**
 * 清洗一个题目的 options 展示数据。
 *
 * 只有同一 content 中命中至少两个不同的 A-D 标签时，才会按拼接选项拆分，
 * 避免把正常英文句子中的单个 “A.” 误判为脏数据。含 TAB 但无法可靠拆分时，
 * 会转成换行，以免把历史拼接文本直接连成一行展示。
 */
export function sanitizeQuestionOptions(options: PracticeOption[] | unknown): OptionSanitizeResult {
  if (!Array.isArray(options)) return { dirty: false, options: [] }

  let dirty = false
  let reason: OptionSanitizeResult['reason']
  let rawContent: string | undefined
  const safeOptions: PracticeOption[] = []

  for (const rawOption of options) {
    const option = (rawOption && typeof rawOption === 'object'
      ? rawOption
      : { content: String(rawOption ?? '') }) as PracticeOption
    const content = String(option.content ?? '')
    const matches = optionLabelMatches(content)
    const labels = new Set(matches.map(match => match[1].toUpperCase()))
    const hasMergedLabels = labels.size >= 2
    const hasTab = content.includes('\t')

    if (hasMergedLabels) {
      dirty = true
      reason ||= hasTab ? 'tab' : 'merged-labels'
      rawContent ||= content
      const split = splitEmbeddedOptions(option, content, matches)
      if (split.length > 1) {
        safeOptions.push(...split)
        continue
      }
    }

    if (hasTab) {
      dirty = true
      reason ||= 'tab'
      rawContent ||= content
      safeOptions.push({ ...option, content: content.replace(/\t+/g, '\n') })
      continue
    }

    safeOptions.push({ ...option })
  }

  return { dirty, reason, options: safeOptions, rawContent }
}
