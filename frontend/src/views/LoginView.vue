<template>
  <div class="login-page">
    <div class="login-card">
      <h1 class="login-title">墨题</h1>
      <p class="login-subtitle">{{ mode === 'login' ? '初登墨题 · 开卷立案' : '立卷注册' }}</p>

      <form @submit.prevent="submit">
        <div class="field">
          <label>用户名</label>
          <input
            v-model="username"
            type="text"
            placeholder="2-32 位字符"
            autocomplete="username"
            required
          />
        </div>
        <div class="field">
          <label>密码</label>
          <input
            v-model="password"
            type="password"
            placeholder="至少 6 位"
            autocomplete="current-password"
            required
          />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <p v-if="notice" class="notice">{{ notice }}</p>
        <button type="submit" class="submit-btn" :disabled="loading">
          {{ loading ? '请稍候…' : (mode === 'login' ? '启卷研习' : '立卷') }}
        </button>
      </form>

      <p class="switch">
        <a href="#" @click.prevent="toggleMode">
          {{ mode === 'login' ? '没有账号？注册一个' : '已有账号？去登录' }}
        </a>
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi, setToken } from '../api'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const error = ref('')
const notice = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  notice.value = ''
  if (username.value.trim().length < 2 || username.value.trim().length > 32) {
    error.value = '用户名需 2-32 位'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码至少 6 位'
    return
  }
  loading.value = true
  try {
    const resp = mode.value === 'login'
      ? await authApi.login(username.value.trim(), password.value)
      : await authApi.register(username.value.trim(), password.value)
    setToken(resp.token)
    if (mode.value === 'register' && (resp.user as any)?.migrated_legacy) {
      notice.value = '首个账号已创建，原有数据已迁移'
    }
    router.push('/')
  } catch (e: any) {
    error.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}

function toggleMode() {
  mode.value = mode.value === 'login' ? 'register' : 'login'
  error.value = ''
  notice.value = ''
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(160deg, #f6f3ec 0%, #ece4d3 100%);
}
.login-card {
  width: 360px;
  padding: 40px 32px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(72, 109, 92, 0.15);
}
.login-title {
  margin: 0 0 4px;
  text-align: center;
  color: #486d5c;
  font-size: 28px;
}
.login-subtitle {
  margin: 0 0 24px;
  text-align: center;
  color: #8a8a8a;
}
.field {
  margin-bottom: 16px;
}
.field label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  color: #555;
}
.field input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
}
.field input:focus {
  border-color: #486d5c;
}
.error {
  color: #d33;
  font-size: 13px;
  margin: 0 0 12px;
}
.notice {
  color: #486d5c;
  font-size: 13px;
  margin: 0 0 12px;
}
.submit-btn {
  width: 100%;
  padding: 12px;
  background: #486d5c;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 16px;
  cursor: pointer;
}
.submit-btn:disabled {
  opacity: 0.6;
}
.switch {
  margin: 16px 0 0;
  text-align: center;
  font-size: 14px;
}
.switch a {
  color: #486d5c;
  text-decoration: none;
}
</style>
