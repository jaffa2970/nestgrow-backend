<template>
  <div class="dashboard">

    <!-- Upgrade banner -->
    <div v-if="license && license.culle_disponibili === 0" class="upgrade-banner">
      <span>
        Hai raggiunto il limite di
        <strong>{{ license.max_culle }} {{ license.max_culle === 1 ? 'culla' : 'culle' }}</strong>
        del piano <strong>{{ license.piano?.toUpperCase() }}</strong>.
      </span>
      <button class="btn-upgrade" @click="$router.push('/register?upgrade=true')">
        Cambia piano →
      </button>
    </div>

    <!-- Unread messages notification -->
    <div v-if="unreadCount > 0 && tab !== 'messaggi'" class="msg-banner">
      📬 Hai <strong>{{ unreadCount }}</strong> {{ unreadCount === 1 ? 'nuovo messaggio' : 'nuovi messaggi' }} da lake8.dev
      <button class="btn-msg-link" @click="tab = 'messaggi'">Visualizza →</button>
    </div>

    <!-- Tabs -->
    <div class="tabs">
      <button :class="{ active: tab === 'culle' }" @click="tab = 'culle'">🌱 Culle</button>
      <button :class="{ active: tab === 'licenza' }" @click="tab = 'licenza'">📋 Licenza</button>
      <button :class="{ active: tab === 'messaggi' }" @click="tab = 'messaggi'">
        📬 Messaggi
        <span v-if="unreadCount > 0" class="badge">{{ unreadCount }}</span>
      </button>
    </div>

    <!-- ===== TAB CULLE ===== -->
    <div v-if="tab === 'culle'">
      <div class="section-header">
        <h2>Culle attive</h2>
        <button class="btn-add" @click="showAddModal = true">+ Nuova culla</button>
      </div>

      <div v-if="loadError" class="alert-error">{{ loadError }}</div>

      <div v-if="culle.length === 0 && !loadError" class="empty-state">
        Nessuna culla attiva. Crea la prima!
      </div>

      <div class="culle-list">
        <div v-for="culla in culle" :key="culla.id" class="culla-card">
          <div class="culla-header">
            <span class="culla-id">#{{ culla.id }}</span>
            <span class="culla-nome">{{ culla.nome }}</span>
            <span v-if="culla.device_id" class="device-tag">{{ culla.device_id }}</span>
            <button class="btn-icon" title="Disattiva culla" @click="deleteCulla(culla.id)">✕</button>
          </div>

          <!-- 4 zone rows -->
          <table class="zone-table">
            <thead>
              <tr>
                <th>Zona</th>
                <th>Coltura</th>
                <th>Umidità</th>
                <th>Ultima lettura</th>
                <th>Pompa</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="zona in culla.zone" :key="zona.numero_zona">
                <td class="zona-num">{{ zona.numero_zona }}</td>
                <td class="zona-nome">
                  <div v-if="zona.umidita_soglia_min != null">
                    <div class="zona-nome-text">{{ zona.nome || `Zona ${zona.numero_zona}` }}</div>
                    <div v-if="zona.descrizione_coltura" class="coltura-desc">{{ zona.descrizione_coltura }}</div>
                  </div>
                  <div v-else class="not-configured">— Non configurata</div>
                </td>
                <td>
                  <span class="humidity-pill" :class="humidityClass(zona.ultima_umidita, zona.umidita_soglia_min, zona.umidita_soglia_max)">
                    {{ zona.ultima_umidita != null ? zona.ultima_umidita.toFixed(1) + '%' : '—' }}
                  </span>
                </td>
                <td class="ts-cell">
                  {{ zona.ultima_lettura_ts ? formatTs(zona.ultima_lettura_ts) : '—' }}
                </td>
                <td class="pump-cell">
                  <button
                    class="btn-pump on"
                    :disabled="zona.pompa_on || pumping[`${culla.id}-${zona.numero_zona}`]"
                    @click="pumpCmd(culla.id, zona.numero_zona, 'on')"
                  >ON</button>
                  <button
                    class="btn-pump off"
                    :disabled="!zona.pompa_on || pumping[`${culla.id}-${zona.numero_zona}`]"
                    @click="pumpCmd(culla.id, zona.numero_zona, 'off')"
                  >OFF</button>
                  <span v-if="zona.pompa_on" class="pump-indicator">💧</span>
                </td>
                <td class="edit-cell">
                  <span
                    v-if="savedZonaKey === `${culla.id}-${zona.numero_zona}`"
                    class="saved-flash"
                  >✓ Salvato</span>
                  <button
                    v-else
                    class="btn-edit"
                    title="Configura zona"
                    @click="openZoneModal(culla.id, zona)"
                  >✏️</button>
                </td>
              </tr>
            </tbody>
          </table>

          <div v-if="pumpError[culla.id]" class="alert-error small">{{ pumpError[culla.id] }}</div>
        </div>
      </div>
    </div>

    <!-- ===== TAB LICENZA ===== -->
    <div v-if="tab === 'licenza'" class="license-section">
      <div v-if="!license || !license.registrato" class="empty-state">
        Licenza non registrata.
        <a href="#" @click.prevent="$router.push('/register')">Registra ora →</a>
      </div>
      <template v-else>
        <div class="license-card">
          <div class="license-row">
            <span class="license-label">Piano attivo</span>
            <span class="plan-badge" :class="license.piano">{{ license.piano?.toUpperCase() }}</span>
          </div>
          <div class="license-row">
            <span class="license-label">Culle utilizzate</span>
            <div class="progress-wrap">
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: progressPct + '%' }"
                  :class="{ full: license.culle_disponibili === 0 }"
                ></div>
              </div>
              <span class="progress-text">
                {{ license.culle_usate }} / {{ license.max_culle }}
              </span>
            </div>
          </div>
          <div class="license-row">
            <span class="license-label">Valida fino</span>
            <span>{{ formatDate(license.valida_fino) }}</span>
          </div>
          <div v-if="license.ragione_sociale" class="license-row">
            <span class="license-label">Intestatario</span>
            <span>{{ license.ragione_sociale }}</span>
          </div>
          <div v-if="license.email" class="license-row">
            <span class="license-label">Email</span>
            <span>{{ license.email }}</span>
          </div>
          <div class="license-actions">
            <button class="btn-upgrade-full" @click="$router.push('/register?upgrade=true')">
              🔄 Aggiorna piano
            </button>
          </div>
        </div>
      </template>
    </div>

    <!-- ===== TAB MESSAGGI ===== -->
    <div v-if="tab === 'messaggi'" class="messages-section">
      <div class="section-header">
        <h2>Comunicazioni lake8.dev</h2>
      </div>

      <div v-if="messages.length === 0" class="empty-state">
        Nessuna comunicazione da lake8.dev
      </div>

      <div class="messages-list">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="msg-card"
          :class="[msg.tipo, { unread: !msg.letto }]"
          @click="toggleMsg(msg)"
        >
          <div class="msg-header">
            <span class="msg-icon">{{ msgIcon(msg.tipo) }}</span>
            <span class="msg-titolo" :class="{ bold: !msg.letto }">{{ msg.titolo }}</span>
            <span class="msg-data">{{ formatDate(msg.data_msg) }}</span>
            <span class="msg-chevron">{{ expandedMsg === msg.id ? '▲' : '▼' }}</span>
          </div>
          <div v-if="expandedMsg === msg.id" class="msg-corpo">{{ msg.corpo }}</div>
        </div>
      </div>
    </div>

    <!-- ===== ADD CULLA MODAL ===== -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h3>Nuova culla</h3>
        <div class="field">
          <label>Nome</label>
          <input v-model="newCulla.nome" type="text" placeholder="Serra principale" />
        </div>
        <div class="field">
          <label>Device ID (opzionale)</label>
          <input v-model="newCulla.device_id" type="text" placeholder="nestgrow-a4b2" />
        </div>
        <p v-if="addError" class="alert-error small">{{ addError }}</p>
        <div class="modal-actions">
          <button @click="showAddModal = false">Annulla</button>
          <button class="btn-primary" @click="createCulla" :disabled="addLoading">
            {{ addLoading ? 'Creazione...' : 'Crea culla (+ 4 zone)' }}
          </button>
        </div>
      </div>
    </div>

    <!-- ===== ZONE CONFIG MODAL ===== -->
    <div v-if="showZoneModal" class="modal-overlay" @click.self="showZoneModal = false">
      <div class="modal modal-wide">
        <h3>Configura Zona {{ zoneForm.numero_zona }}</h3>

        <div class="field">
          <label>Nome zona</label>
          <input v-model="zoneForm.nome" type="text" placeholder="Zona basilico" />
        </div>

        <div class="field">
          <label>Descrizione coltura</label>
          <input v-model="zoneForm.descrizione_coltura" type="text"
            placeholder="Cosa stai coltivando in questa zona?" />
        </div>

        <div class="field field-toggle">
          <label>Irrigazione automatica</label>
          <label class="toggle">
            <input v-model="zoneForm.irrigazione_auto" type="checkbox" />
            <span class="toggle-slider"></span>
            <span class="toggle-label">{{ zoneForm.irrigazione_auto ? 'ON' : 'OFF' }}</span>
          </label>
        </div>

        <div class="field">
          <label>
            Soglia irrigazione:
            <strong>{{ zoneForm.umidita_soglia_min }}%</strong> di umidità
          </label>
          <input v-model.number="zoneForm.umidita_soglia_min" type="range"
            min="0" max="100" step="1" class="range-input" />
          <div class="range-ticks"><span>0%</span><span>50%</span><span>100%</span></div>
        </div>

        <div class="field">
          <label>
            Obiettivo umidità:
            <strong>{{ zoneForm.umidita_soglia_max }}%</strong>
          </label>
          <input v-model.number="zoneForm.umidita_soglia_max" type="range"
            min="0" max="100" step="1" class="range-input" />
          <div class="range-ticks"><span>0%</span><span>50%</span><span>100%</span></div>
        </div>

        <div class="field">
          <label>
            Durata ogni ciclo di irrigazione:
            <strong>{{ zoneForm.durata_irrigazione_sec }} secondi</strong>
          </label>
          <input v-model.number="zoneForm.durata_irrigazione_sec" type="number"
            min="1" max="300" class="input-small" />
        </div>

        <p v-if="zoneError" class="alert-error small">{{ zoneError }}</p>

        <div class="modal-actions">
          <button @click="showZoneModal = false">Annulla</button>
          <button class="btn-primary" @click="saveZoneConfig" :disabled="zoneSaving">
            {{ zoneSaving ? 'Salvataggio...' : 'Salva configurazione' }}
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const culle = ref([])
const license = ref(null)
const messages = ref([])
const loadError = ref('')
const tab = ref('culle')

const pumping = ref({})
const pumpError = ref({})
const showAddModal = ref(false)
const addError = ref('')
const addLoading = ref(false)
const newCulla = ref({ nome: '', device_id: '' })

// Zone config modal
const showZoneModal = ref(false)
const zoneEditCullaId = ref(null)
const zoneForm = ref({})
const zoneError = ref('')
const zoneSaving = ref(false)
const savedZonaKey = ref('')
let savedFlashTimer = null

// Messages
const expandedMsg = ref(null)

let pollInterval = null

const progressPct = computed(() => {
  if (!license.value || !license.value.max_culle) return 0
  return Math.min(100, (license.value.culle_usate / license.value.max_culle) * 100)
})

const unreadCount = computed(() => messages.value.filter(m => !m.letto).length)

async function load() {
  try {
    const [culleRes, licRes] = await Promise.all([
      axios.get('/culle/'),
      axios.get('/license/'),
    ])
    culle.value = culleRes.data
    license.value = licRes.data
    loadError.value = ''
  } catch (e) {
    if (e.response?.status === 401) {
      router.push('/login')
    } else {
      loadError.value = e.response?.data?.detail || 'Errore nel caricamento dati'
    }
  }
}

async function loadMessages() {
  try {
    const { data } = await axios.get('/messages/')
    messages.value = data
  } catch { /* not critical */ }
}

async function pumpCmd(cullaId, numeroZona, cmd) {
  const key = `${cullaId}-${numeroZona}`
  pumping.value[key] = true
  pumpError.value[cullaId] = ''
  try {
    await axios.post(`/culle/${cullaId}/zone/${numeroZona}/pump`, { cmd, sec: 30 })
    await load()
  } catch (e) {
    pumpError.value[cullaId] = e.response?.data?.detail || 'Errore comando pompa'
  } finally {
    pumping.value[key] = false
  }
}

async function createCulla() {
  addError.value = ''
  addLoading.value = true
  try {
    await axios.post('/culle/', newCulla.value)
    showAddModal.value = false
    newCulla.value = { nome: '', device_id: '' }
    await load()
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Errore creazione culla'
  } finally {
    addLoading.value = false
  }
}

async function deleteCulla(cullaId) {
  if (!confirm(`Disattivare culla #${cullaId}?`)) return
  try {
    await axios.delete(`/culle/${cullaId}`)
    await load()
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Errore'
  }
}

function openZoneModal(cullaId, zona) {
  zoneEditCullaId.value = cullaId
  zoneForm.value = {
    numero_zona: zona.numero_zona,
    nome: zona.nome || '',
    descrizione_coltura: zona.descrizione_coltura || '',
    irrigazione_auto: zona.irrigazione_auto ?? true,
    umidita_soglia_min: zona.umidita_soglia_min ?? 35,
    umidita_soglia_max: zona.umidita_soglia_max ?? 70,
    durata_irrigazione_sec: zona.durata_irrigazione_sec ?? 20,
  }
  zoneError.value = ''
  showZoneModal.value = true
}

async function saveZoneConfig() {
  zoneError.value = ''
  zoneSaving.value = true
  const cullaId = zoneEditCullaId.value
  const num = zoneForm.value.numero_zona

  const body = {
    nome: zoneForm.value.nome || null,
    descrizione_coltura: zoneForm.value.descrizione_coltura || null,
    irrigazione_auto: zoneForm.value.irrigazione_auto,
    umidita_soglia_min: zoneForm.value.umidita_soglia_min,
    umidita_soglia_max: zoneForm.value.umidita_soglia_max,
    durata_irrigazione_sec: zoneForm.value.durata_irrigazione_sec,
  }

  try {
    const { data } = await axios.put(`/culle/${cullaId}/zone/${num}`, body)
    // Update zona in-place without full reload
    const culla = culle.value.find(c => c.id === cullaId)
    if (culla) {
      const idx = culla.zone.findIndex(z => z.numero_zona === num)
      if (idx !== -1) {
        culla.zone[idx] = { ...culla.zone[idx], ...data }
      }
    }
    showZoneModal.value = false
    // Show "✓ Salvato" flash in the row
    if (savedFlashTimer) clearTimeout(savedFlashTimer)
    savedZonaKey.value = `${cullaId}-${num}`
    savedFlashTimer = setTimeout(() => { savedZonaKey.value = '' }, 2500)
  } catch (e) {
    zoneError.value = e.response?.data?.detail || 'Errore salvataggio zona'
  } finally {
    zoneSaving.value = false
  }
}

async function toggleMsg(msg) {
  if (expandedMsg.value === msg.id) {
    expandedMsg.value = null
    return
  }
  expandedMsg.value = msg.id
  if (!msg.letto) {
    try {
      await axios.post(`/messages/${msg.id}/read`)
      msg.letto = true
    } catch { /* ignore */ }
  }
}

function humidityClass(v, soglia_min, soglia_max) {
  if (v == null) return 'unknown'
  if (soglia_min != null && v < soglia_min) return 'low'
  if (soglia_max != null && v > soglia_max) return 'high'
  return 'ok'
}

function formatTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  const today = new Date()
  const isToday = d.toDateString() === today.toDateString()
  if (isToday) {
    return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  }
  const day = d.toLocaleDateString('it-IT', { day: 'numeric', month: 'short' })
  const time = d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
  return `${day} ${time}`
}

function formatDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('it-IT', {
    year: 'numeric', month: 'long', day: 'numeric',
  })
}

function msgIcon(tipo) {
  if (tipo === 'critical') return '🔴'
  if (tipo === 'warning') return '⚠️'
  return 'ℹ️'
}

onMounted(() => {
  load()
  loadMessages()
  pollInterval = setInterval(load, 10000)
})
onUnmounted(() => {
  clearInterval(pollInterval)
  if (savedFlashTimer) clearTimeout(savedFlashTimer)
})
</script>

<style scoped>
.dashboard { padding: 0; max-width: 1200px; margin: 0 auto; }

/* Banners */
.upgrade-banner {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff3cd; border-bottom: 2px solid #ffc107;
  padding: 12px 24px; font-size: 0.9rem; color: #664d03;
}
.btn-upgrade {
  background: #ffc107; border: none; padding: 7px 16px;
  border-radius: 6px; cursor: pointer; font-weight: 700; color: #333;
  white-space: nowrap; margin-left: 16px;
}
.btn-upgrade:hover { background: #e0a800; }

.msg-banner {
  display: flex; align-items: center; gap: 12px;
  background: #e3f2fd; border-bottom: 2px solid #1976d2;
  padding: 10px 24px; font-size: 0.88rem; color: #1565c0;
}
.btn-msg-link {
  background: none; border: none; color: #1565c0;
  cursor: pointer; font-weight: 700; font-size: 0.88rem;
  text-decoration: underline; padding: 0;
}

/* Tabs */
.tabs {
  display: flex; border-bottom: 2px solid #e0e0e0;
  padding: 0 24px; background: white;
}
.tabs button {
  padding: 14px 20px; border: none; background: none;
  font-size: 0.95rem; cursor: pointer; color: #666;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: color 0.2s; position: relative; display: flex; align-items: center; gap: 6px;
}
.tabs button.active { color: #1f5c2e; border-bottom-color: #1f5c2e; font-weight: 700; }
.badge {
  background: #e53935; color: white; font-size: 0.65rem;
  font-weight: 700; padding: 1px 6px; border-radius: 10px; line-height: 1.4;
}

/* Section header */
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 24px 12px;
}
.section-header h2 { font-size: 1.2rem; color: #1f5c2e; }
.btn-add {
  background: #1f5c2e; color: white; border: none;
  padding: 8px 18px; border-radius: 8px; cursor: pointer; font-weight: 600;
}
.btn-add:hover { background: #2d8048; }

/* Culle list */
.culle-list { padding: 0 24px 24px; display: flex; flex-direction: column; gap: 20px; }

.culla-card {
  background: white; border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
  border-left: 4px solid #2d8048; overflow: hidden;
}
.culla-header {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px; background: #f8fdf9; border-bottom: 1px solid #e8f5e9;
}
.culla-id { color: #888; font-size: 0.85rem; }
.culla-nome { font-weight: 700; font-size: 1rem; flex: 1; }
.device-tag {
  background: #e8f5e9; color: #2d8048; font-size: 0.75rem;
  padding: 2px 8px; border-radius: 12px; font-family: monospace;
}
.btn-icon {
  background: none; border: none; color: #bbb; cursor: pointer;
  font-size: 0.9rem; padding: 4px 6px; border-radius: 4px;
}
.btn-icon:hover { color: #e53935; background: #ffebee; }

/* Zone table */
.zone-table { width: 100%; border-collapse: collapse; }
.zone-table th {
  font-size: 0.75rem; color: #888; font-weight: 600;
  text-align: left; padding: 8px 14px;
  border-bottom: 1px solid #f0f0f0; background: #fafafa;
}
.zone-table td { padding: 10px 14px; font-size: 0.88rem; border-bottom: 1px solid #f7f7f7; }
.zone-table tr:last-child td { border-bottom: none; }

.zona-num { font-weight: 700; color: #555; width: 40px; }
.zona-nome { width: 160px; }
.zona-nome-text { color: #333; font-weight: 600; }
.coltura-desc { color: #999; font-size: 0.78rem; margin-top: 2px; }
.not-configured { color: #bbb; font-style: italic; font-size: 0.85rem; }
.ts-cell { color: #999; font-size: 0.8rem; }

.humidity-pill {
  display: inline-block; padding: 3px 10px;
  border-radius: 12px; font-weight: 600; font-size: 0.82rem;
}
.humidity-pill.low { background: #fff3e0; color: #e65100; }
.humidity-pill.ok { background: #e8f5e9; color: #2e7d32; }
.humidity-pill.high { background: #e3f2fd; color: #1565c0; }
.humidity-pill.unknown { background: #f5f5f5; color: #999; }

.pump-cell { display: flex; align-items: center; gap: 6px; }
.btn-pump {
  padding: 4px 10px; border: none; border-radius: 6px;
  cursor: pointer; font-size: 0.78rem; font-weight: 600;
  transition: opacity 0.2s;
}
.btn-pump:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-pump.on { background: #1565c0; color: white; }
.btn-pump.on:not(:disabled):hover { background: #1976d2; }
.btn-pump.off { background: #f0f0f0; color: #555; }
.btn-pump.off:not(:disabled):hover { background: #e0e0e0; }
.pump-indicator { font-size: 1rem; animation: pulse 1.5s ease-in-out infinite; }
@keyframes pulse { 0%,100% { opacity:1 } 50% { opacity:0.4 } }

.edit-cell { width: 80px; text-align: center; }
.btn-edit {
  background: none; border: none; cursor: pointer;
  font-size: 1rem; padding: 2px 6px; border-radius: 4px;
  transition: background 0.15s;
}
.btn-edit:hover { background: #f0f0f0; }
.saved-flash { color: #2e7d32; font-size: 0.78rem; font-weight: 700; }

/* License section */
.license-section { padding: 24px; }
.license-card {
  background: white; border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.07);
  padding: 28px; max-width: 540px;
}
.license-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 0; border-bottom: 1px solid #f0f0f0; gap: 16px;
}
.license-row:last-of-type { border-bottom: none; }
.license-label { font-size: 0.85rem; color: #666; flex-shrink: 0; }

.plan-badge {
  display: inline-block; padding: 4px 14px; border-radius: 20px;
  font-size: 0.82rem; font-weight: 700;
}
.plan-badge.free { background: #e8f5e9; color: #2e7d32; }
.plan-badge.pro { background: #e3f2fd; color: #1565c0; }
.plan-badge.enterprise { background: #f3e5f5; color: #6a1b9a; }
.plan-badge.ultra { background: #fff8e1; color: #e65100; }

.progress-wrap { display: flex; align-items: center; gap: 12px; flex: 1; justify-content: flex-end; }
.progress-bar { width: 160px; height: 8px; background: #e0e0e0; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: #2d8048; border-radius: 4px; transition: width 0.4s; }
.progress-fill.full { background: #e53935; }
.progress-text { font-size: 0.85rem; font-weight: 600; color: #333; white-space: nowrap; }

.license-actions { padding-top: 16px; }
.btn-upgrade-full {
  background: #1f5c2e; color: white; border: none;
  padding: 10px 24px; border-radius: 8px;
  cursor: pointer; font-weight: 700; font-size: 0.95rem;
}
.btn-upgrade-full:hover { background: #2d8048; }

/* Messages section */
.messages-section { padding: 0 24px 24px; }
.messages-list { display: flex; flex-direction: column; gap: 10px; }

.msg-card {
  border-radius: 10px; border: 1.5px solid #e0e0e0;
  overflow: hidden; cursor: pointer;
  transition: box-shadow 0.15s;
}
.msg-card:hover { box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
.msg-card.unread { border-color: #1976d2; }
.msg-card.critical { background: #fff5f5; border-color: #e53935; }
.msg-card.warning { background: #fffde7; border-color: #fbc02d; }
.msg-card.info { background: white; }

.msg-header {
  display: flex; align-items: center; gap: 10px;
  padding: 14px 16px;
}
.msg-icon { font-size: 1.1rem; flex-shrink: 0; }
.msg-titolo { flex: 1; font-size: 0.92rem; color: #333; }
.msg-titolo.bold { font-weight: 700; }
.msg-data { font-size: 0.78rem; color: #999; white-space: nowrap; }
.msg-chevron { color: #999; font-size: 0.7rem; margin-left: 6px; }

.msg-corpo {
  padding: 0 16px 16px 42px;
  font-size: 0.88rem; color: #555; line-height: 1.6;
  white-space: pre-wrap;
}

/* Empty state */
.empty-state { text-align: center; padding: 60px 24px; color: #888; font-size: 1rem; }
.empty-state a { color: #1f5c2e; }

/* Errors */
.alert-error {
  background: #ffebee; color: #c62828;
  padding: 10px 16px; border-radius: 8px;
  margin: 0 24px 16px; font-size: 0.88rem;
}
.alert-error.small { margin: 8px 0 0; padding: 8px 12px; font-size: 0.82rem; }

/* Modal */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  background: white; border-radius: 16px; padding: 32px;
  width: 400px; max-height: 90vh; overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal-wide { width: 480px; }
.modal h3 { margin-bottom: 20px; color: #1f5c2e; }
.field { margin-bottom: 18px; }
.field label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 6px; color: #444; }
.field input[type="text"],
.field input[type="number"] {
  width: 100%; padding: 9px 13px;
  border: 1.5px solid #ddd; border-radius: 8px; font-size: 0.95rem;
}
.field input:focus { outline: none; border-color: #2d8048; }
.input-small { width: 100px !important; }

.field-toggle { display: flex; align-items: center; justify-content: space-between; }
.field-toggle label:first-child { margin-bottom: 0; }

/* Toggle switch */
.toggle { display: flex; align-items: center; gap: 8px; cursor: pointer; }
.toggle input[type="checkbox"] { display: none; }
.toggle-slider {
  width: 40px; height: 22px; background: #ddd; border-radius: 11px;
  position: relative; transition: background 0.2s; flex-shrink: 0;
}
.toggle-slider::after {
  content: ''; position: absolute; width: 18px; height: 18px;
  background: white; border-radius: 50%; top: 2px; left: 2px;
  transition: transform 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}
.toggle input:checked + .toggle-slider { background: #1f5c2e; }
.toggle input:checked + .toggle-slider::after { transform: translateX(18px); }
.toggle-label { font-size: 0.85rem; font-weight: 600; color: #444; }

/* Range input */
.range-input {
  width: 100%; accent-color: #1f5c2e; margin-top: 4px;
}
.range-ticks {
  display: flex; justify-content: space-between;
  font-size: 0.72rem; color: #aaa; margin-top: 2px;
}

.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.modal-actions button {
  padding: 9px 20px; border-radius: 8px;
  border: 1.5px solid #ddd; cursor: pointer; font-size: 0.9rem;
  background: white;
}
.modal-actions .btn-primary { background: #1f5c2e; color: white; border-color: #1f5c2e; font-weight: 600; }
.modal-actions .btn-primary:hover:not(:disabled) { background: #2d8048; }
.modal-actions .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
