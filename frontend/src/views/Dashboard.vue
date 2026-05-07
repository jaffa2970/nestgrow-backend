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

    <!-- Tabs -->
    <div class="tabs">
      <button :class="{ active: tab === 'culle' }" @click="tab = 'culle'">🌱 Culle</button>
      <button :class="{ active: tab === 'licenza' }" @click="tab = 'licenza'">📋 Licenza</button>
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
                <th>Nome</th>
                <th>Umidità</th>
                <th>Ultima lettura</th>
                <th>Pompa</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="zona in culla.zone" :key="zona.numero_zona">
                <td class="zona-num">{{ zona.numero_zona }}</td>
                <td class="zona-nome">{{ zona.nome || '—' }}</td>
                <td>
                  <span
                    class="humidity-pill"
                    :class="humidityClass(zona.ultima_umidita)"
                  >
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

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const culle = ref([])
const license = ref(null)
const loadError = ref('')
const tab = ref('culle')

const pumping = ref({})
const pumpError = ref({})
const showAddModal = ref(false)
const addError = ref('')
const addLoading = ref(false)
const newCulla = ref({ nome: '', device_id: '' })

let pollInterval = null

const progressPct = computed(() => {
  if (!license.value || !license.value.max_culle) return 0
  return Math.min(100, (license.value.culle_usate / license.value.max_culle) * 100)
})

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

function humidityClass(v) {
  if (v == null) return 'unknown'
  if (v < 30) return 'low'
  if (v > 75) return 'high'
  return 'ok'
}

function formatTs(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function formatDate(dt) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('it-IT', { year: 'numeric', month: 'long', day: 'numeric' })
}

onMounted(() => {
  load()
  pollInterval = setInterval(load, 10000)
})
onUnmounted(() => clearInterval(pollInterval))
</script>

<style scoped>
.dashboard { padding: 0; max-width: 1200px; margin: 0 auto; }

/* Upgrade banner */
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

/* Tabs */
.tabs {
  display: flex; border-bottom: 2px solid #e0e0e0;
  padding: 0 24px; background: white;
}
.tabs button {
  padding: 14px 20px; border: none; background: none;
  font-size: 0.95rem; cursor: pointer; color: #666;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: color 0.2s;
}
.tabs button.active { color: #1f5c2e; border-bottom-color: #1f5c2e; font-weight: 700; }

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
.zona-nome { color: #444; width: 120px; }
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
.progress-bar {
  width: 160px; height: 8px; background: #e0e0e0;
  border-radius: 4px; overflow: hidden;
}
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
  width: 380px; box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal h3 { margin-bottom: 20px; color: #1f5c2e; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 5px; }
.field input {
  width: 100%; padding: 9px 13px;
  border: 1.5px solid #ddd; border-radius: 8px; font-size: 0.95rem;
}
.field input:focus { outline: none; border-color: #2d8048; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.modal-actions button {
  padding: 9px 20px; border-radius: 8px;
  border: 1.5px solid #ddd; cursor: pointer; font-size: 0.9rem;
  background: white;
}
.btn-primary { background: #1f5c2e; color: white; border-color: #1f5c2e; font-weight: 600; }
.btn-primary:hover:not(:disabled) { background: #2d8048; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
