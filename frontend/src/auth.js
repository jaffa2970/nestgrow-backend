import { computed, ref } from 'vue'

// Module-level reactive refs — shared across all components.
// These are the single source of truth; localStorage is just persistence.

function _parseJwt(token) {
  try {
    const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b64))
  } catch {
    return {}
  }
}

const _ruolo    = ref(localStorage.getItem('ng_ruolo')    || 'user')
const _username = ref(localStorage.getItem('ng_username') || '')

export const ruolo    = _ruolo
export const username = _username
export const isAdmin  = computed(() => _ruolo.value === 'administrator')

export function setAuth(token) {
  localStorage.setItem('ng_token', token)
  const claims = _parseJwt(token)
  _ruolo.value    = claims.ruolo || 'user'
  _username.value = claims.sub   || ''
  localStorage.setItem('ng_ruolo',    _ruolo.value)
  localStorage.setItem('ng_username', _username.value)
}

export function clearAuth() {
  _ruolo.value    = 'user'
  _username.value = ''
  localStorage.removeItem('ng_token')
  localStorage.removeItem('ng_ruolo')
  localStorage.removeItem('ng_username')
}
