import { reactive } from 'vue'
import { del, get, patch, post } from '../api'

export const questionBankProfilesState = reactive({
  items: [] as any[],
  activeId: 0,
  loading: false,
})

export async function loadQuestionBankProfiles() {
  questionBankProfilesState.loading = true
  try {
    questionBankProfilesState.items = await get<any[]>('/question-bank-profiles')
    // 在线模式：后端返回 is_active（app_settings 记录当前激活）；离线模式无 is_active 字段 → fallback is_default
    // 修复：此前只用 is_default，在线激活后 activeId 被重置回默认配置，彩色圆点/下拉切换无效（沐春 09-10 反馈）
    const activeItem = questionBankProfilesState.items.find((item: any) => item.is_active)
      || questionBankProfilesState.items.find((item: any) => item.is_default)
    questionBankProfilesState.activeId = Number(activeItem?.id || 0)
    return questionBankProfilesState.items
  } finally {
    questionBankProfilesState.loading = false
  }
}

export async function activateQuestionBankProfile(profileId: number) {
  questionBankProfilesState.activeId = profileId
  try { await post(`/question-bank-profiles/${profileId}/activate`) } catch { /* 离线忽略 */ }
  await loadQuestionBankProfiles()
}

export async function createQuestionBankProfile(name: string) {
  await post('/question-bank-profiles', { name })
  return loadQuestionBankProfiles()
}

export async function renameQuestionBankProfile(profileId: number, name: string) {
  await patch(`/question-bank-profiles/${profileId}`, { name })
  return loadQuestionBankProfiles()
}

export async function deleteQuestionBankProfile(profileId: number) {
  await del(`/question-bank-profiles/${profileId}`)
  return loadQuestionBankProfiles()
}
