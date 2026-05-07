<template>
  <div id="app">
    <nav v-if="isLoggedIn" class="navbar">
      <span class="brand">🌱 NestGrow</span>
      <span class="tagline">by lake8.dev</span>
      <button class="logout-btn" @click="logout">Esci</button>
    </nav>
    <router-view />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const isLoggedIn = computed(() => !!localStorage.getItem('ng_token'))

async function logout() {
  try {
    await axios.post('/auth/logout')
  } catch {}
  localStorage.removeItem('ng_token')
  router.push('/login')
}
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #f0f4f0; color: #1a2e1a; }

.navbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 24px;
  background: #1f5c2e;
  color: white;
}
.brand { font-size: 1.2rem; font-weight: 700; }
.tagline { font-size: 0.8rem; opacity: 0.7; flex: 1; }
.logout-btn {
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.3);
  color: white;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
}
.logout-btn:hover { background: rgba(255,255,255,0.25); }
</style>
