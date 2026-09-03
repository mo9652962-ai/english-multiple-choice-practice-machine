<script setup lang="ts">
import { Building2, Check, LoaderCircle, Plus, Users } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { get } from '../api'
import {
  createOrganization,
  loadOrganizations,
  organizationsState,
  switchOrganization,
  type Organization,
} from '../services/organizations'

const name = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const selected = ref<Organization | null>(null)
const activeOrganization = computed(() =>
  organizationsState.items.find((item) => item.id === organizationsState.activeId) || null,
)

onMounted(() => {
  void refresh()
})

async function refresh() {
  loading.value = true
  error.value = ''
  try {
    await loadOrganizations()
    if (activeOrganization.value) await showDetails(activeOrganization.value)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    loading.value = false
  }
}

async function showDetails(organization: Organization) {
  selected.value = organization
  if (organization.id === 0) return
  try {
    selected.value = await get<Organization>(`/organizations/${organization.id}`)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
}

async function create() {
  const value = name.value.trim()
  if (!value) return
  saving.value = true
  error.value = ''
  try {
    const organization = await createOrganization(value)
    name.value = ''
    await refresh()
    await showDetails(organization)
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  } finally {
    saving.value = false
  }
}

async function activate(organization: Organization) {
  if (organization.id === organizationsState.activeId) {
    await showDetails(organization)
    return
  }
  error.value = ''
  try {
    await switchOrganization(organization.id)
    await refresh()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
}

function formatDate(value: string) {
  if (!value) return '本地模式'
  return new Date(`${value.replace(' ', 'T')}Z`).toLocaleDateString()
}
</script>

<template>
  <section class="page organizations-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">ENTERPRISE WORKSPACE</span>
        <h1>组织管理</h1>
        <p class="subtitle">为团队划分独立的学习空间，当前阶段先完成组织边界与切换能力。</p>
      </div>
      <Building2 :size="38" stroke-width="1.4" class="header-icon" aria-hidden="true" />
    </header>

    <div class="create-card card">
      <div>
        <strong>创建一个组织</strong>
        <p>创建后你会自动成为该组织的 owner。</p>
      </div>
      <form class="create-form" @submit.prevent="create">
        <input v-model="name" maxlength="120" placeholder="例如：华东校区英语教研组" aria-label="组织名称" />
        <button class="button" type="submit" :disabled="saving || !name.trim()">
          <LoaderCircle v-if="saving" :size="16" class="spinning" />
          <Plus v-else :size="16" />
          创建组织
        </button>
      </form>
    </div>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <div v-if="loading && !organizationsState.items.length" class="empty-state">正在读取组织…</div>
    <div v-else-if="!organizationsState.items.length" class="empty-state">
      还没有组织，请先创建一个。
    </div>
    <div v-else class="organization-layout">
      <div class="organization-list">
        <button
          v-for="organization in organizationsState.items"
          :key="organization.id"
          type="button"
          class="organization-card card"
          :class="{ active: organization.id === organizationsState.activeId }"
          @click="activate(organization)"
        >
          <span class="organization-mark"><Building2 :size="20" /></span>
          <span class="organization-copy">
            <strong>{{ organization.name }}</strong>
            <small>{{ organization.slug }} · {{ organization.role || 'owner' }}</small>
            <small>创建于 {{ formatDate(organization.created_at) }}</small>
          </span>
          <Check v-if="organization.id === organizationsState.activeId" :size="18" class="active-check" />
        </button>
      </div>

      <aside v-if="selected" class="detail-card card">
        <div class="detail-heading">
          <div>
            <span class="eyebrow">CURRENT ORGANIZATION</span>
            <h2>{{ selected.name }}</h2>
          </div>
          <Users :size="22" aria-hidden="true" />
        </div>
        <p class="detail-meta">{{ selected.slug }} · {{ selected.role || 'owner' }}</p>
        <div v-if="selected.members?.length" class="member-list">
          <strong>成员（{{ selected.members.length }}）</strong>
          <div v-for="member in selected.members" :key="member.user_id" class="member-row">
            <span>{{ member.username }}</span>
            <small>{{ member.role }}</small>
          </div>
        </div>
        <p v-else class="muted">成员列表将在邀请成员后显示。</p>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.organizations-page { max-width: 1120px; margin: 0 auto; padding: 36px clamp(18px, 4vw, 54px) 72px; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; margin-bottom: 28px; }
.page-header h1 { margin: 7px 0 8px; }
.subtitle { max-width: 620px; margin: 0; color: var(--text-muted, #778078); line-height: 1.6; }
.header-icon { color: #486d5c; opacity: .65; }
.eyebrow { color: #9b765d; font-size: 11px; letter-spacing: .14em; }
.card { background: var(--surface, #fff); border: 1px solid var(--border, #e8e3d9); border-radius: 16px; box-shadow: 0 8px 24px rgba(55, 62, 52, .05); }
.create-card { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 18px 20px; margin-bottom: 22px; }
.create-card p { margin: 4px 0 0; color: var(--text-muted, #778078); font-size: 13px; }
.create-form { display: flex; gap: 10px; min-width: min(100%, 470px); }
.create-form input { flex: 1; min-width: 0; padding: 10px 12px; border: 1px solid var(--border, #ded9ce); border-radius: 9px; background: var(--surface-2, #faf9f5); color: inherit; }
.button { display: inline-flex; align-items: center; justify-content: center; gap: 6px; padding: 9px 13px; border: 0; border-radius: 9px; color: #fff; background: #486d5c; cursor: pointer; white-space: nowrap; }
.button:disabled { opacity: .55; cursor: not-allowed; }
.organization-layout { display: grid; grid-template-columns: minmax(280px, 1fr) minmax(300px, 1fr); gap: 18px; align-items: start; }
.organization-list { display: grid; gap: 12px; }
.organization-card { width: 100%; display: flex; align-items: center; gap: 12px; padding: 16px; text-align: left; color: inherit; cursor: pointer; transition: border-color .18s, transform .18s; }
.organization-card:hover, .organization-card.active { border-color: #7da28c; transform: translateY(-1px); }
.organization-mark { display: grid; place-items: center; width: 40px; height: 40px; color: #486d5c; background: #eaf2eb; border-radius: 11px; }
.organization-copy { display: grid; gap: 3px; min-width: 0; flex: 1; }
.organization-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.organization-copy small, .detail-meta, .muted { color: var(--text-muted, #778078); font-size: 12px; }
.active-check { color: #486d5c; }
.detail-card { padding: 22px; min-height: 190px; }
.detail-heading { display: flex; align-items: flex-start; justify-content: space-between; color: #486d5c; }
.detail-heading h2 { margin: 7px 0 0; color: var(--text, #29332d); }
.detail-meta { margin: 8px 0 22px; }
.member-list { display: grid; gap: 9px; }
.member-row { display: flex; justify-content: space-between; padding: 9px 0; border-top: 1px solid var(--border, #eeeae3); }
.member-row small { color: var(--text-muted, #778078); }
.error { margin: 12px 0; color: #a13d35; }
.empty-state { padding: 40px 20px; color: var(--text-muted, #778078); text-align: center; }
.spinning { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (max-width: 760px) { .create-card, .create-form { flex-direction: column; align-items: stretch; min-width: 0; } .organization-layout { grid-template-columns: 1fr; } }
</style>
