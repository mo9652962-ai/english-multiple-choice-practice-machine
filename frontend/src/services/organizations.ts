import { reactive } from 'vue'
import { get, getOrganizationId, isOffline, post, setOrganizationId } from '../api'

export interface Organization {
  id: number
  name: string
  slug: string
  status: string
  owner_user_id: number | null
  settings: string
  created_at: string
  role?: string
  is_active?: boolean
  members?: Array<{
    user_id: number
    username: string
    role: string
    status: string
    joined_at: string
  }>
}

export const organizationsState = reactive({
  items: [] as Organization[],
  activeId: getOrganizationId(),
  loading: false,
  error: '',
})

const offlineOrganization: Organization = {
  id: 0,
  name: '本地学习空间',
  slug: 'local',
  status: 'active',
  owner_user_id: null,
  settings: '{}',
  created_at: '',
  role: 'owner',
  is_active: true,
}

export async function loadOrganizations(): Promise<Organization[]> {
  organizationsState.loading = true
  organizationsState.error = ''
  try {
    if (isOffline()) {
      organizationsState.items = [offlineOrganization]
      organizationsState.activeId = 0
      return organizationsState.items
    }
    organizationsState.items = await get<Organization[]>('/organizations')
    const active = organizationsState.items.find((item) => item.is_active)
      || organizationsState.items.find((item) => item.id === organizationsState.activeId)
      || organizationsState.items[0]
    organizationsState.activeId = active?.id ?? null
    setOrganizationId(organizationsState.activeId)
    return organizationsState.items
  } catch (error) {
    organizationsState.error = error instanceof Error ? error.message : String(error)
    throw error
  } finally {
    organizationsState.loading = false
  }
}

export async function switchOrganization(organizationId: number): Promise<void> {
  if (organizationId === organizationsState.activeId) return
  if (!isOffline()) await post(`/organizations/${organizationId}/switch`)
  organizationsState.activeId = organizationId
  setOrganizationId(organizationId)
  await loadOrganizations()
}

export async function createOrganization(name: string): Promise<Organization> {
  const organization = isOffline()
    ? offlineOrganization
    : await post<Organization>('/organizations', { name })
  if (isOffline()) {
    organizationsState.items = [organization]
    organizationsState.activeId = organization.id
  } else {
    await loadOrganizations()
  }
  return organization
}

