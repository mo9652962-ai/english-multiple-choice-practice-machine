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
    questionBankProfilesState.activeId = Number(
      questionBankProfilesState.items.find(item => item.is_active)?.id || 0,
    )
    return questionBankProfilesState.items
  } finally {
    questionBankProfilesState.loading = false
  }
}

export async function activateQuestionBankProfile(profileId: number) {
  await post(`/question-bank-profiles/${profileId}/activate`)
  questionBankProfilesState.activeId = profileId
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
