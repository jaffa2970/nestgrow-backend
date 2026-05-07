<template>
  <div class="utenti-page">
    <div class="page-header">
      <h2>👥 Gestione utenti</h2>
      <button class="btn-add" @click="openCreate">+ Nuovo utente</button>
    </div>

    <p v-if="loadError" class="alert-error">{{ loadError }}</p>

    <table class="utenti-table">
      <thead>
        <tr>
          <th>Username</th>
          <th>Ruolo</th>
          <th>Stato</th>
          <th>Creato il</th>
          <th>Azioni</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in utenti" :key="u.id" :class="{ disabled: !u.attivo }">
          <td class="td-username">{{ u.username }}</td>
          <td>
            <span class="ruolo-badge" :class="u.ruolo">{{ u.ruolo }}</span>
          </td>
          <td>
            <span class="stato-badge" :class="u.attivo ? 'attivo' : 'disattivo'">
              {{ u.attivo ? 'Attivo' : 'Disattivato' }}
            </span>
          </td>
          <td class="td-date">{{ formatDate(u.creato_il) }}</td>
          <td class="td-actions">
            <button class="btn-icon" title="Modifica" @click="openEdit(u)">✏️</button>
            <button class="btn-icon" title="Cambia password" @click="openPassword(u)">🔑</button>
            <button
              class="btn-icon"
              title="Disattiva"
              @click="disattiva(u)"
              :disabled="!u.attivo"
            >🗑️</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- CREATE / EDIT MODAL -->
    <div v-if="showFormModal" class="modal-overlay" @click.self="showFormModal = false">
      <div class="modal-box">
        <h3>{{ editingId ? 'Modifica utente' : 'Nuovo utente' }}</h3>

        <div class="field">
          <label>Username</label>
          <input v-model="form.username" type="text" />
        </div>

        <div v-if="!editingId" class="field">
          <label>Password</label>
          <input v-model="form.password" type="password" />
        </div>

        <div class="field">
          <label>Ruolo</label>
          <select v-model="form.ruolo">
            <option value="user">User (sola lettura)</option>
            <option value="administrator">Administrator</option>
          </select>
        </div>

        <div v-if="editingId" class="field">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.attivo" />
            Utente attivo
          </label>
        </div>

        <p v-if="formError" class="alert-error small">{{ formError }}</p>
        <div class="modal-actions">
          <button @click="showFormModal = false">Annulla</button>
          <button class="btn-save" @click="submitForm" :disabled="formSaving">
            {{ formSaving ? 'Salvataggio...' : 'Salva' }}
          </button>
        </div>
      </div>
    </div>

    <!-- PASSWORD MODAL -->
    <div v-if="showPwdModal" class="modal-overlay" @click.self="showPwdModal = false">
      <div class="modal-box">
        <h3>Cambia password — {{ pwdTarget?.username }}</h3>
        <div class="field">
          <label>Nuova password</label>
          <input v-model="pwdForm.nuova_password" type="password" />
        </div>
        <div class="field">
          <label>Conferma password</label>
          <input v-model="pwdForm.conferma" type="password" />
        </div>
        <p v-if="pwdError" class="alert-error small">{{ pwdError }}</p>
        <div class="modal-actions">
          <button @click="showPwdModal = false">Annulla</button>
          <button class="btn-save" @click="submitPassword" :disabled="pwdSaving">
            {{ pwdSaving ? 'Salvataggio...' : 'Aggiorna password' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const utenti = ref([])
const loadError = ref('')

// Form (create / edit)
const showFormModal = ref(false)
const editingId = ref(null)
const form = ref({ username: '', password: '', ruolo: 'user', attivo: true })
const formError = ref('')
const formSaving = ref(false)

// Password change (admin setting another user's password)
const showPwdModal = ref(false)
const pwdTarget = ref(null)
const pwdForm = ref({ nuova_password: '', conferma: '' })
const pwdError = ref('')
const pwdSaving = ref(false)

async function load() {
  try {
    const { data } = await axios.get('/utenti/')
    utenti.value = data
    loadError.value = ''
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Errore caricamento utenti'
  }
}

onMounted(load)

function formatDate(d) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('it-IT')
}

function openCreate() {
  editingId.value = null
  form.value = { username: '', password: '', ruolo: 'user', attivo: true }
  formError.value = ''
  showFormModal.value = true
}

function openEdit(u) {
  editingId.value = u.id
  form.value = { username: u.username, password: '', ruolo: u.ruolo, attivo: u.attivo }
  formError.value = ''
  showFormModal.value = true
}

async function submitForm() {
  formError.value = ''
  formSaving.value = true
  try {
    if (editingId.value) {
      await axios.put(`/utenti/${editingId.value}`, {
        username: form.value.username,
        ruolo: form.value.ruolo,
        attivo: form.value.attivo,
      })
    } else {
      if (form.value.password.length < 8) {
        formError.value = 'La password deve avere almeno 8 caratteri'
        return
      }
      await axios.post('/utenti/', {
        username: form.value.username,
        password: form.value.password,
        ruolo: form.value.ruolo,
      })
    }
    showFormModal.value = false
    await load()
  } catch (e) {
    formError.value = e.response?.data?.detail || 'Errore durante il salvataggio'
  } finally {
    formSaving.value = false
  }
}

async function disattiva(u) {
  if (!confirm(`Disattivare l'utente "${u.username}"?`)) return
  try {
    await axios.delete(`/utenti/${u.id}`)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Errore durante la disattivazione')
  }
}

function openPassword(u) {
  pwdTarget.value = u
  pwdForm.value = { nuova_password: '', conferma: '' }
  pwdError.value = ''
  showPwdModal.value = true
}

async function submitPassword() {
  pwdError.value = ''
  if (pwdForm.value.nuova_password.length < 8) {
    pwdError.value = 'La password deve avere almeno 8 caratteri'
    return
  }
  if (pwdForm.value.nuova_password !== pwdForm.value.conferma) {
    pwdError.value = 'Le password non coincidono'
    return
  }
  pwdSaving.value = true
  try {
    await axios.post(`/utenti/${pwdTarget.value.id}/password`, {
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

<style scoped>
.utenti-page { max-width: 900px; margin: 32px auto; padding: 0 16px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header h2 { font-size: 1.4rem; color: #1f5c2e; }

.btn-add {
  background: #1f5c2e; color: white;
  border: none; border-radius: 8px;
  padding: 8px 16px; cursor: pointer; font-size: 0.9rem; font-weight: 600;
}
.btn-add:hover { background: #2d8048; }

.utenti-table { width: 100%; border-collapse: collapse; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
.utenti-table th { background: #f5f5f5; padding: 12px 14px; text-align: left; font-size: 0.82rem; color: #666; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.utenti-table td { padding: 12px 14px; border-top: 1px solid #f0f0f0; font-size: 0.9rem; }
.utenti-table tr.disabled { opacity: 0.5; }
.td-username { font-weight: 600; color: #222; }
.td-date { color: #999; font-size: 0.82rem; }
.td-actions { display: flex; gap: 4px; }

.ruolo-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.ruolo-badge.administrator { background: #e8f5e9; color: #1f5c2e; }
.ruolo-badge.user { background: #f5f5f5; color: #666; }

.stato-badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem; }
.stato-badge.attivo { background: #e8f5e9; color: #1b5e20; }
.stato-badge.disattivo { background: #fafafa; color: #bbb; }

.btn-icon { background: none; border: 1px solid #e0e0e0; border-radius: 6px; padding: 4px 8px; cursor: pointer; font-size: 0.88rem; transition: background 0.15s; }
.btn-icon:hover:not(:disabled) { background: #f5f5f5; }
.btn-icon:disabled { opacity: 0.35; cursor: not-allowed; }

.alert-error { background: #ffebee; color: #c62828; padding: 10px 14px; border-radius: 8px; font-size: 0.88rem; margin-bottom: 12px; }
.alert-error.small { padding: 8px 12px; font-size: 0.82rem; margin-top: 10px; }

.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.45); display: flex; align-items: center; justify-content: center; z-index: 200; }
.modal-box { background: white; border-radius: 14px; padding: 28px; width: 100%; max-width: 380px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.modal-box h3 { font-size: 1.1rem; margin-bottom: 18px; color: #1f5c2e; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 5px; color: #555; }
.field input, .field select { width: 100%; padding: 9px 12px; border: 1.5px solid #ddd; border-radius: 7px; font-size: 0.95rem; }
.field input:focus, .field select:focus { outline: none; border-color: #2d8048; }
.checkbox-label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.checkbox-label input { width: auto; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.modal-actions button { padding: 8px 18px; border-radius: 7px; border: 1.5px solid #ccc; cursor: pointer; font-size: 0.9rem; background: white; }
.btn-save { background: #1f5c2e !important; color: white !important; border-color: #1f5c2e !important; }
.btn-save:hover:not(:disabled) { background: #2d8048 !important; }
.btn-save:disabled { opacity: 0.5 !important; cursor: not-allowed; }
</style>
