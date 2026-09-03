<script setup lang="ts">
import { Building2, ChevronDown } from 'lucide-vue-next'
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  loadOrganizations,
  organizationsState,
  switchOrganization,
} from '../services/organizations'

const router = useRouter()
const error = ref('')
const activeOrganization = computed(() =>
  organizationsState.items.find((item) => item.id === organizationsState.activeId)
  || organizationsState.items[0]
  || null,
)

onMounted(() => {
  if (!organizationsState.items.length) void loadOrganizations().catch(() => undefined)
})

async function changeOrganization(event: Event) {
  const id = Number((event.target as HTMLSelectElement).value)
  if (!id || id === organizationsState.activeId) return
  try {
    error.value = ''
    await switchOrganization(id)
    window.location.reload()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
}
</script>

<template>
  <div class="organization-switcher" title="切换当前组织">
    <Building2 :size="16" aria-hidden="true" />
    <select
      v-if="organizationsState.items.length"
      :value="activeOrganization?.id"
      :disabled="organizationsState.loading"
      aria-label="当前组织"
      @change="changeOrganization"
    >
      <option v-for="organization in organizationsState.items" :key="organization.id" :value="organization.id">
        {{ organization.name }}
      </option>
    </select>
    <button v-else type="button" class="organization-empty" @click="router.push('/organizations')">
      设置组织
    </button>
    <ChevronDown :size="14" aria-hidden="true" />
    <p v-if="error" class="organization-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.organization-switcher {
  position: relative;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  margin-bottom: 10px;
  color: var(--text-muted, #727a72);
  background: color-mix(in srgb, var(--surface, #fff) 74%, transparent);
  border: 1px solid var(--border, #e7e3da);
  border-radius: 10px;
}
.organization-switcher select,
.organization-empty {
  min-width: 0;
  flex: 1;
  border: 0;
  outline: 0;
  color: var(--text, #29332d);
  background: transparent;
  font: inherit;
  cursor: pointer;
}
.organization-empty {
  text-align: left;
}
.organization-error {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 2;
  width: max-content;
  max-width: 220px;
  margin: 0;
  padding: 5px 7px;
  color: #9b3c35;
  background: #fff5f2;
  border-radius: 6px;
  font-size: 11px;
}
</style>
