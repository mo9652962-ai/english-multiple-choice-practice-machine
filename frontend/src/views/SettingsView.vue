<script setup lang="ts">
import {
  Check,
  ChevronDown,
  ChevronUp,
  CirclePlus,
  Eye,
  EyeOff,
  KeyRound,
  LoaderCircle,
  PlugZap,
  RefreshCw,
  Save,
  Server,
  Sparkles,
  Trash2,
} from 'lucide-vue-next'
import { onMounted, reactive, ref } from 'vue'
import { del, get, post, put } from '../api'

type AiModel = {
  model_id: string
  display_name: string
  owned_by: string
  provider: string
  is_visible: boolean
  is_available: boolean
}

type AiProfile = {
  id: number
  name: string
  base_url: string
  api_key?: string
  has_api_key: boolean
  enabled: boolean
  is_default: boolean
  default_model: string
  temperature: number
  max_tokens: number
  system_prompt: string
  models: AiModel[]
}

const profiles = ref<AiProfile[]>([])
const expanded = ref<number[]>([])
const shuffleEnabled = ref(localStorage.getItem('epm_shuffle_options') !== 'false')
const busy = reactive<Record<string, boolean>>({})
const notices = reactive<Record<number, string>>({})
const message = ref('')
const error = ref('')
const creating = ref(false)

function blankProfile(): AiProfile {
  return {
    id: 0,
    name: '新 API 配置',
    base_url: 'http://127.0.0.1:11434/v1',
    api_key: '',
    has_api_key: false,
    enabled: true,
    is_default: false,
    default_model: '',
    temperature: 0.2,
    max_tokens: 0,
    system_prompt: '',
    models: [],
  }
}

const newProfile = reactive<AiProfile>(blankProfile())

function signalChanged() {
  window.dispatchEvent(new CustomEvent('linjian-ai-config-changed'))
}

function payload(profile: AiProfile) {
  return {
    name: profile.name,
    base_url: profile.base_url,
    api_key: profile.api_key || null,
    enabled: profile.enabled,
    is_default: profile.is_default,
    default_model: profile.default_model,
    temperature: profile.temperature,
    max_tokens: profile.max_tokens,
    system_prompt: profile.system_prompt,
  }
}

function busyKey(action: string, id: number) {
  return `${action}:${id}`
}

function toggleExpanded(id: number) {
  expanded.value = expanded.value.includes(id)
    ? expanded.value.filter(item => item !== id)
    : [...expanded.value, id]
}

function toggleShuffle() {
  shuffleEnabled.value = !shuffleEnabled.value
  localStorage.setItem('epm_shuffle_options', shuffleEnabled.value ? 'true' : 'false')
}

async function load() {
  try {
    const result = await get<AiProfile[]>('/ai/profiles')
    profiles.value = result.map(profile => ({ ...profile, api_key: '' }))
    if (!expanded.value.length && profiles.value.length) {
      expanded.value = [profiles.value[0].id]
    }
    error.value = ''
  } catch (cause) {
    error.value = String(cause)
  }
}

async function createProfile() {
  const key = busyKey('create', 0)
  if (busy[key]) return
  busy[key] = true
  try {
    const created = await post<AiProfile>('/ai/profiles', payload(newProfile))
    Object.assign(newProfile, blankProfile())
    creating.value = false
    message.value = `已添加“${created.name}”`
    error.value = ''
    await load()
    expanded.value = [created.id, ...expanded.value.filter(id => id !== created.id)]
    signalChanged()
  } catch (cause) {
    error.value = String(cause)
  } finally {
    busy[key] = false
  }
}

async function saveProfile(profile: AiProfile) {
  const key = busyKey('save', profile.id)
  if (busy[key]) return
  busy[key] = true
  try {
    await put(`/ai/profiles/${profile.id}`, payload(profile))
    notices[profile.id] = '配置已保存'
    message.value = ''
    error.value = ''
    await load()
    signalChanged()
  } catch (cause) {
    error.value = String(cause)
  } finally {
    busy[key] = false
  }
}

async function toggleProfile(profile: AiProfile) {
  profile.enabled = !profile.enabled
  await saveProfile(profile)
}

async function syncModels(profile: AiProfile) {
  const key = busyKey('sync', profile.id)
  if (busy[key]) return
  busy[key] = true
  notices[profile.id] = ''
  try {
    const result = await post<{ models: unknown[] }>(`/ai/profiles/${profile.id}/models/sync`)
    notices[profile.id] = `已同步 ${result.models.length} 个模型`
    error.value = ''
    await load()
    signalChanged()
  } catch (cause) {
    notices[profile.id] = `同步失败：${String(cause)}`
  } finally {
    busy[key] = false
  }
}

async function testProfile(profile: AiProfile) {
  const key = busyKey('test', profile.id)
  if (busy[key]) return
  busy[key] = true
  notices[profile.id] = ''
  try {
    const result = await post<{ message: string }>(`/ai/profiles/${profile.id}/test`, {
      model: profile.default_model || null,
    })
    notices[profile.id] = result.message || '连接成功'
    error.value = ''
  } catch (cause) {
    notices[profile.id] = String(cause)
  } finally {
    busy[key] = false
  }
}

async function setModelVisible(profile: AiProfile, model: AiModel) {
  model.is_visible = !model.is_visible
  try {
    await put(`/ai/profiles/${profile.id}/models`, {
      model_id: model.model_id,
      is_visible: model.is_visible,
    })
    signalChanged()
  } catch (cause) {
    model.is_visible = !model.is_visible
    error.value = String(cause)
  }
}

async function setAllVisible(profile: AiProfile, visible: boolean) {
  try {
    await put(`/ai/profiles/${profile.id}/models/visibility`, { is_visible: visible })
    profile.models.forEach(model => { model.is_visible = visible })
    signalChanged()
  } catch (cause) {
    error.value = String(cause)
  }
}

async function removeProfile(profile: AiProfile) {
  if (!window.confirm(`删除 API 配置“${profile.name}”？已保存的对话不会被删除。`)) return
  try {
    await del(`/ai/profiles/${profile.id}`)
    message.value = `已删除“${profile.name}”`
    error.value = ''
    await load()
    signalChanged()
  } catch (cause) {
    error.value = String(cause)
  }
}

onMounted(() => {
  load()
  loadUsage()
})

// ── v9.27: Gemini UI4——文枢阁用量（AI Usage） ──
const usageLoading = ref(false)
const usageError = ref('')
const usage = ref<any>(null)
const usageBarWidth = 300
const usageColors = ['#B84A39', '#4A5F4E', '#A67A38', '#6B7B8C', '#8A7D6D']
const USAGE_TASK_LABELS: Record<string, string> = {
  'deep-explain': '精讲', 'deep_explain': '精讲',
  'essay': '批改', 'essay_evaluate': '批改',
  'speaking': '陪练', 'speaking_session': '陪练',
  'translate': '翻译', 'vocabulary': '翻译',
  'similar_questions': '变式', 'generate_similar': '变式',
}
function usageTaskLabel(task: string) { return USAGE_TASK_LABELS[task] || task }
function usageBarOffset(i: number) {
  return usage.value ? usage.value.distribution.slice(0, i).reduce((a: number, d: any) => a + usageBarWidth * d.percent / 100, 0) : 0
}
async function loadUsage() {
  usageLoading.value = true
  usageError.value = ''
  try {
    usage.value = await get('/ai/usage')
  } catch (e) {
    usageError.value = String(e)
  } finally {
    usageLoading.value = false
  }
}

// ── v2.95: 内置反馈入口 ──
const fbOpen = ref(false)
const fbCat = ref('other')
const fbContent = ref('')
const fbContact = ref('')
const fbSending = ref(false)
const fbMsg = ref('')
const fbCats = [
  { value: 'bug', label: '🐞 报错' },
  { value: 'bad', label: '😕 不好用' },
  { value: 'idea', label: '💡 想要新功能' },
  { value: 'other', label: '📝 其他' },
]

async function submitFeedback() {
  if (fbContent.value.trim().length < 2 || fbSending.value) return
  fbSending.value = true
  fbMsg.value = ''
  try {
    await post('/feedback', {
      category: fbCat.value,
      content: fbContent.value.trim(),
      contact: fbContact.value.trim(),
      page: window.location.pathname,
    })
    fbMsg.value = '✅ 反馈已收到，谢谢！'
    fbContent.value = ''
    fbContact.value = ''
    setTimeout(() => { fbOpen.value = false; fbMsg.value = '' }, 1200)
  } catch (cause) {
    fbMsg.value = '❌ 提交失败：' + String(cause)
  } finally {
    fbSending.value = false
  }
}
</script>

<template>
  <div class="page page-settings ai-settings-page">
    <div class="page-head">
      <div>
        <span class="eyebrow">文枢阁 · 模型配置</span>
        <h1>模型与 API</h1>
        <p class="lead">像工作区一样管理多个接口；只有启用的 API 和可见模型会出现在左侧助手中。</p>
      </div>
      <button class="button" type="button" @click="creating=!creating">
        <CirclePlus :size="17" />添加 API 配置
      </button>
    </div>

    <div v-if="error" class="warning" role="alert">{{ error }}</div>
    <div v-if="message" class="settings-success"><Check :size="17" />{{ message }}</div>

    <section class="api-profile-card new-profile">
      <div class="api-profile-heading">
        <span class="api-profile-icon"><PlugZap :size="20" /></span>
        <div><span class="eyebrow">练习偏好</span><h2>练习偏好</h2></div>
      </div>
      <div class="api-profile-body">
        <div class="practice-pref-row">
          <div>
            <strong>选项打乱</strong>
            <p>每次打开练习时随机排序选择题选项（防记答案）。判分使用稳定键，不影响正确性。排序题不受影响。</p>
          </div>
          <button class="pref-switch" type="button" role="switch" :aria-checked="shuffleEnabled" @click="toggleShuffle">
            <span :class="{ on: shuffleEnabled }"></span>
          </button>
        </div>
      </div>
    </section>

    <!-- v9.27: Gemini UI4——文枢阁用量（AI Usage） -->
    <section class="api-profile-card new-profile">
      <div class="api-profile-heading">
        <span class="api-profile-icon"><Sparkles :size="20" /></span>
        <div><span class="eyebrow">文枢阁用量</span><h2>AI 笔墨消耗</h2></div>
      </div>
      <div class="api-profile-body">
        <div v-if="usageLoading" class="lead" style="font-size:12px">正在研墨…</div>
        <div v-else-if="usageError" class="lead" style="font-size:12px;color:var(--zhusha,#B84A39)">{{ usageError }}</div>
        <template v-else-if="usage">
          <div style="display:flex;gap:14px;flex-wrap:wrap;margin-bottom:14px">
            <div>
              <div style="font-size:12px;color:var(--muted)">本月调用</div>
              <div class="font-serif" style="font-size:22px;font-weight:700;color:#B84A39">{{ usage.total_calls }} 次</div>
            </div>
            <div>
              <div style="font-size:12px;color:var(--muted)">消耗 Tokens</div>
              <div class="font-serif" style="font-size:22px;font-weight:700">{{ (usage.total_tokens / 1000).toFixed(1) }}k</div>
            </div>
            <div>
              <div style="font-size:12px;color:var(--muted)" title="status 非 ok 的调用占比">失败率</div>
              <div class="font-serif" style="font-size:22px;font-weight:700">{{ usage.fail_rate }}%</div>
            </div>
          </div>
          <!-- 任务类型分布（水墨 SVG 横向条） -->
          <div style="font-size:12px;color:var(--muted);margin-bottom:4px">任务类型分布</div>
          <svg :viewBox="'0 0 ' + usageBarWidth + ' 24'" width="100%" height="24" style="border-radius:6px;overflow:hidden;border:1px solid #E8E0D2">
            <rect v-for="(d, i) in usage.distribution" :key="i"
                  :x="usageBarOffset(i)" y="0" :width="usageBarWidth * d.percent / 100" height="24"
                  :fill="usageColors[i % usageColors.length]" />
          </svg>
          <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:6px;font-size:11px;color:var(--muted)">
            <span v-for="(d, i) in usage.distribution" :key="i">
              <span :style="{ display:'inline-block', width:8, height:8, borderRadius:2, background: usageColors[i % usageColors.length], marginRight: 3 }"></span>
              {{ usageTaskLabel(d.task) }} {{ d.percent }}%
            </span>
            <span v-if="!usage.distribution.length">本月暂无 AI 调用记录</span>
          </div>
        </template>
      </div>
    </section>

    <section v-if="creating" class="api-profile-card new-profile">
      <div class="api-profile-heading">
        <span class="api-profile-icon"><CirclePlus :size="20" /></span>
        <div><span class="eyebrow">新增 API 连接</span><h2>添加新的 API</h2></div>
      </div>
      <div class="api-profile-body">
        <div class="grid grid-2">
          <div class="field"><label>配置名称</label><input v-model.trim="newProfile.name" placeholder="例如：本地 Ollama"></div>
          <div class="field"><label>默认模型（可稍后同步选择）</label><input v-model.trim="newProfile.default_model" placeholder="例如：qwen3:8b"></div>
        </div>
        <div class="field"><label>API 基础地址 (Base URL)</label><input v-model.trim="newProfile.base_url" placeholder="http://127.0.0.1:11434/v1"></div>
        <div class="field"><label>API 密钥 (Key)</label><input v-model="newProfile.api_key" type="password" placeholder="本地接口通常可留空"></div>
        <div class="api-create-actions">
          <button class="button secondary" type="button" @click="creating=false">取消</button>
          <button class="button" type="button" :disabled="busy[busyKey('create',0)]" @click="createProfile">
            <LoaderCircle v-if="busy[busyKey('create',0)]" :size="16" class="spinning" />
            <Save v-else :size="16" />保存 API
          </button>
        </div>
      </div>
    </section>

    <div class="api-profile-list">
      <article v-for="profile in profiles" :key="profile.id" class="api-profile-card">
        <header class="api-profile-summary">
          <button class="api-profile-expand" type="button" :aria-expanded="expanded.includes(profile.id)" @click="toggleExpanded(profile.id)">
            <span class="api-profile-icon"><Server :size="20" /></span>
            <span class="api-profile-copy">
              <span><strong>{{ profile.name }}</strong><small v-if="profile.is_default">默认</small></span>
              <small>{{ profile.base_url }}</small>
            </span>
            <span class="api-profile-stats">
              <small>{{ profile.models.filter(model => model.is_visible && model.is_available).length }} 个模型可见</small>
              <span :class="{ online: profile.enabled }">{{ profile.enabled ? '已启用' : '已停用' }}</span>
            </span>
            <ChevronUp v-if="expanded.includes(profile.id)" :size="19" />
            <ChevronDown v-else :size="19" />
          </button>
          <button
            class="api-enable"
            type="button"
            role="switch"
            :aria-checked="profile.enabled"
            :aria-label="profile.enabled ? `停用 ${profile.name}` : `启用 ${profile.name}`"
            :class="{ active: profile.enabled }"
            @click="toggleProfile(profile)"
          ><span /></button>
        </header>

        <div v-if="expanded.includes(profile.id)" class="api-profile-body">
          <div class="grid grid-2">
            <div class="field"><label>配置名称</label><input v-model.trim="profile.name"></div>
            <div class="field">
              <label>默认模型</label>
              <select v-model="profile.default_model">
                <option value="">请选择默认模型</option>
                <option v-for="model in profile.models.filter(item => item.is_available)" :key="model.model_id" :value="model.model_id">
                  {{ model.display_name || model.model_id }}
                </option>
              </select>
            </div>
          </div>
          <div class="field"><label>API 基础地址 (Base URL)</label><input v-model.trim="profile.base_url"></div>
          <div class="field">
            <label>API Key（留空不会清除）</label>
            <div class="api-key-input">
              <KeyRound :size="17" />
              <input v-model="profile.api_key" type="password" :placeholder="profile.has_api_key ? '密钥已加密保存在本机' : '本地接口通常可留空'">
            </div>
          </div>
          <div class="grid grid-2">
            <div class="field"><label>生成随机性 (Temperature)</label><input v-model.number="profile.temperature" type="number" min="0" max="2" step=".1"></div>
            <div class="field"><label>输出 Token 上限（已停用）</label><input v-model.number="profile.max_tokens" type="number" disabled><small>保留旧配置兼容；当前不会向模型发送输出 Token 上限。</small></div>
          </div>
          <p class="field-hint">Temperature 控制回答的随机性与创造性：值越低越稳定、越适合判分和事实类任务（错题分析、题库导入、单词翻译建议 0.2–0.5）；越高越发散，适合头脑风暴。</p>
          <p class="field-hint">所有模型场景均由供应商决定最大输出长度；若长任务没有返回正文，程序会提示重试或切换模型/API 配置。</p>
          <div class="field"><label>附加系统提示词</label><textarea v-model="profile.system_prompt" rows="3" placeholder="对该 API 下的模型统一生效"></textarea></div>
          <label class="default-profile-check">
            <input v-model="profile.is_default" type="checkbox" :disabled="profile.is_default">
            设为默认 API（错题分析、单词翻译和题库校正会优先使用它）
          </label>

          <div class="api-actions">
            <button class="button" type="button" :disabled="busy[busyKey('save',profile.id)]" @click="saveProfile(profile)">
              <LoaderCircle v-if="busy[busyKey('save',profile.id)]" :size="16" class="spinning" />
              <Save v-else :size="16" />保存配置
            </button>
            <button class="button secondary" type="button" :disabled="busy[busyKey('sync',profile.id)]" @click="syncModels(profile)">
              <RefreshCw :size="16" :class="{spinning:busy[busyKey('sync',profile.id)]}" />同步模型
            </button>
            <button class="button secondary" type="button" :disabled="busy[busyKey('test',profile.id)] || !profile.default_model" @click="testProfile(profile)">
              <PlugZap :size="16" />测试连接
            </button>
            <button class="button ghost api-delete" type="button" @click="removeProfile(profile)">
              <Trash2 :size="16" />删除
            </button>
          </div>
          <p v-if="notices[profile.id]" class="api-profile-notice" role="status">{{ notices[profile.id] }}</p>

          <section class="api-model-section">
            <div class="api-model-heading">
              <div><h3>模型选择器</h3><p>关闭“显示”后，该模型仍保留在配置中，但不会出现在助手的切换菜单里。</p></div>
              <div>
                <button type="button" @click="setAllVisible(profile,true)"><Eye :size="15" />全部显示</button>
                <button type="button" @click="setAllVisible(profile,false)"><EyeOff :size="15" />全部隐藏</button>
              </div>
            </div>
            <div v-if="profile.models.length" class="api-model-list">
              <div v-for="model in profile.models" :key="model.model_id" class="api-model-row" :class="{ unavailable: !model.is_available }">
                <div><strong>{{ model.display_name || model.model_id }}</strong><small>{{ model.owned_by || model.provider || '接口模型' }}<template v-if="!model.is_available"> · 本次同步未发现</template></small></div>
                <button
                  type="button"
                  role="switch"
                  :aria-checked="model.is_visible"
                  :disabled="!model.is_available"
                  :class="{ active:model.is_visible }"
                  @click="setModelVisible(profile,model)"
                >
                  <Eye v-if="model.is_visible" :size="15" /><EyeOff v-else :size="15" />
                  {{ model.is_visible ? '显示' : '隐藏' }}
                </button>
              </div>
            </div>
            <div v-else class="api-model-empty">还没有模型列表。保存配置后点击“同步模型”。</div>
          </section>
        </div>
      </article>

      <!-- v2.95: 内置反馈入口 (内测方案 P0) -->
      <article class="card feedback-card">
        <div class="card-header"><h2>反馈建议</h2><p>遇到问题？有想法？3 秒告诉我们——帮助我们把墨题做得更好。</p></div>
        <button class="button" type="button" @click="fbOpen = true">📮 提交反馈</button>
              </article>

              <!-- v3.3: 我的墨题——版本信息 + 检查更新入口 -->
              <article class="card">
                <div class="card-header">
                  <div>
                    <span class="eyebrow">关于墨题</span>
                    <h2>我的墨题</h2>
                    <p>查看版本号、开发时间与检查更新</p>
                  </div>
                  <a class="button ghost" href="#/about">
                    v2.0.0 →
                  </a>
                </div>
              </article>
            </div>
          </div>

  <!-- 反馈弹窗 -->
  <div v-if="fbOpen" class="modal-backdrop" @click.self="fbOpen = false">
    <div class="modal-card feedback-modal">
      <div class="modal-header"><h3>反馈建议</h3><button class="modal-close" type="button" @click="fbOpen = false">×</button></div>
      <div class="feedback-form">
        <div class="feedback-cats">
          <button v-for="c in fbCats" :key="c.value" type="button" :class="{ active: fbCat === c.value }" @click="fbCat = c.value">{{ c.label }}</button>
        </div>
        <textarea v-model="fbContent" rows="4" maxlength="2000" placeholder="请描述你的问题或建议（必填）"></textarea>
        <input v-model="fbContact" maxlength="200" placeholder="联系方式（选填，方便我们回复你）" />
        <div class="feedback-actions">
          <button class="button secondary" type="button" @click="fbOpen = false">取消</button>
          <button class="button" type="button" :disabled="fbSending || fbContent.trim().length < 2" @click="submitFeedback">{{ fbSending ? '提交中…' : '提交反馈' }}</button>
        </div>
        <p v-if="fbMsg" class="feedback-msg">{{ fbMsg }}</p>
      </div>
    </div>
  </div>
</template>
