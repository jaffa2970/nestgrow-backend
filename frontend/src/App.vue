<template>
  <div id="app">
    <nav v-if="isLoggedIn" class="navbar">
      <span class="brand">🌱 NestGrow</span>
      <span class="tagline">by lake8.dev</span>
      <router-link v-if="isAdmin" to="/utenti" class="nav-link">👥 Utenti</router-link>
      <div class="user-menu" ref="userMenuRef">
        <button class="user-btn" @click="userMenuOpen = !userMenuOpen">
          {{ username }} <span class="role-badge">{{ ruolo }}</span> ▾
        </button>
        <div v-if="userMenuOpen" class="user-dropdown">
          <button @click="openChangePassword">🔑 Cambia password</button>
          <button @click="logout">🚪 Esci</button>
        </div>
      </div>
    </nav>

    <router-view />

    <!-- Change password modal -->
    <div v-if="showPwdModal" class="modal-overlay" @click.self="showPwdModal = false">
      <div class="modal-box">
        <h3>Cambia password</h3>
        <div class="field">
          <label>Password attuale</label>
          <input v-model="pwdForm.password_attuale" type="password" autocomplete="current-password" />
        </div>
        <div class="field">
          <label>Nuova password</label>
          <input v-model="pwdForm.nuova_password" type="password" autocomplete="new-password" />
        </div>
        <div class="field">
          <label>Conferma nuova password</label>
          <input v-model="pwdForm.conferma" type="password" autocomplete="new-password" />
        </div>
        <p v-if="pwdError" class="pwd-error">{{ pwdError }}</p>
        <div class="modal-actions">
          <button @click="showPwdModal = false">Annulla</button>
          <button class="btn-save" @click="submitChangePassword" :disabled="pwdSaving">
            {{ pwdSaving ? 'Salvataggio...' : 'Aggiorna password' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { username, ruolo, isAdmin, clearAuth } from './auth.js'

const router = useRouter()

const isLoggedIn = computed(() => !!localStorage.getItem('ng_token'))

const userMenuOpen = ref(false)
const userMenuRef = ref(null)

function handleClickOutside(e) {
  if (userMenuRef.value && !userMenuRef.value.contains(e.target)) {
    userMenuOpen.value = false
  }
}
onMounted(() => document.addEventListener('click', handleClickOutside))
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

async function logout() {
  userMenuOpen.value = false
  try { await axios.post('/auth/logout') } catch {}
  clearAuth()
  router.push('/login')
}

// ── Change password ────────────────────────────────────────────────────────────
const showPwdModal = ref(false)
const pwdForm = ref({ password_attuale: '', nuova_password: '', conferma: '' })
const pwdError = ref('')
const pwdSaving = ref(false)

function openChangePassword() {
  userMenuOpen.value = false
  pwdForm.value = { password_attuale: '', nuova_password: '', conferma: '' }
  pwdError.value = ''
  showPwdModal.value = true
}

async function submitChangePassword() {
  pwdError.value = ''
  if (pwdForm.value.nuova_password.length < 8) {
    pwdError.value = 'La nuova password deve avere almeno 8 caratteri'
    return
  }
  if (pwdForm.value.nuova_password !== pwdForm.value.conferma) {
    pwdError.value = 'Le password non coincidono'
    return
  }
  pwdSaving.value = true
  try {
    await axios.post('/auth/change-password', {
      password_attuale: pwdForm.value.password_attuale,
      nuova_password: pwdForm.value.nuova_password,
    })
    showPwdModal.value = false
  } catch (e) {
    pwdError.value = e.response?.data?.detail || 'Errore durante il salvataggio'
  } finally {
    pwdSaving.value = false
  }
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

.nav-link {
  color: rgba(255,255,255,0.85);
  text-decoration: none;
  font-size: 0.88rem;
  padding: 6px 12px;
  border-radius: 6px;
  transition: background 0.2s;
}
.nav-link:hover { background: rgba(255,255,255,0.15); }

.user-menu { position: relative; }
.user-btn {
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.3);
  color: white;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.88rem;
  display: flex;
  align-items: center;
  gap: 6px;
}
.user-btn:hover { background: rgba(255,255,255,0.25); }
.role-badge {
  font-size: 0.7rem;
  background: rgba(255,255,255,0.2);
  padding: 1px 6px;
  border-radius: 10px;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.user-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.15);
  min-width: 180px;
  z-index: 100;
  overflow: hidden;
}
.user-dropdown button {
  display: block;
  width: 100%;
  padding: 10px 16px;
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.88rem;
  color: #333;
  transition: background 0.15s;
}
.user-dropdown button:hover { background: #f5f5f5; }

/* Change password modal */
.modal-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.45);
  display: flex; align-items: center; justify-content: center;
  z-index: 200;
}
.modal-box {
  background: white;
  border-radius: 14px;
  padding: 28px;
  width: 100%;
  max-width: 380px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal-box h3 { font-size: 1.1rem; margin-bottom: 18px; color: #1f5c2e; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 5px; color: #555; }
.field input {
  width: 100%; padding: 9px 12px;
  border: 1.5px solid #ddd; border-radius: 7px;
  font-size: 0.95rem;
}
.field input:focus { outline: none; border-color: #2d8048; }
.pwd-error { color: #c62828; font-size: 0.82rem; margin-bottom: 12px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.modal-actions button { padding: 8px 18px; border-radius: 7px; border: 1.5px solid #ccc; cursor: pointer; font-size: 0.9rem; }
.modal-actions .btn-save { background: #1f5c2e; color: white; border-color: #1f5c2e; }
.modal-actions .btn-save:hover:not(:disabled) { background: #2d8048; }
.modal-actions .btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
