<template>
  <div class="login-page">
    <div class="login-card">
      <h1>🌱 NestGrow</h1>
      <p class="subtitle">by lake8.dev</p>

      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>Username</label>
          <input v-model="username" type="text" autocomplete="username" required />
        </div>
        <div class="field">
          <label>Password</label>
          <input v-model="password" type="password" autocomplete="current-password" required />
        </div>

        <p v-if="error" class="error">{{ error }}</p>

        <button type="submit" :disabled="loading">
          {{ loading ? 'Accesso in corso...' : 'Accedi' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { setAuth } from '../auth.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const params = new URLSearchParams()
    params.append('username', username.value)
    params.append('password', password.value)

    const { data } = await axios.post('/auth/login', params, {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    })
    setAuth(data.access_token)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Errore di connessione'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1f5c2e 0%, #2d8048 100%);
}
.login-card {
  background: white;
  border-radius: 16px;
  padding: 40px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
h1 { font-size: 2rem; color: #1f5c2e; text-align: center; }
.subtitle { text-align: center; color: #888; margin-bottom: 32px; font-size: 0.85rem; }

.field { margin-bottom: 16px; }
.field label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 6px; color: #444; }
.field input {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.2s;
}
.field input:focus { outline: none; border-color: #2d8048; }

.error { color: #c0392b; font-size: 0.85rem; margin-bottom: 12px; }

button[type="submit"] {
  width: 100%;
  padding: 12px;
  background: #1f5c2e;
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  transition: background 0.2s;
}
button[type="submit"]:hover:not(:disabled) { background: #2d8048; }
button[type="submit"]:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
