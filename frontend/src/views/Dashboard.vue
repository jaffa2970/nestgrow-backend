<template>
  <div class="dashboard">
    <div class="top-bar">
      <h2>Culle attive</h2>
      <div class="license-badge" v-if="license">
        Piano: <strong>{{ license.piano.toUpperCase() }}</strong>
        &nbsp;·&nbsp;{{ license.culle_usate }}/{{ license.culle_usate + license.culle_disponibili }} culle
      </div>
      <button class="btn-add" @click="showAddModal = true">+ Nuova zona</button>
    </div>

    <div v-if="loadError" class="alert-error">{{ loadError }}</div>

    <div v-if="zones.length === 0 && !loadError" class="empty-state">
      Nessuna zona attiva. Crea la prima culla!
    </div>

    <div class="zones-grid">
      <div v-for="zone in zones" :key="zone.id" class="zone-card">
        <div class="zone-header">
          <span class="zone-id">#{{ zone.id }}</span>
          <span class="zone-name">{{ zone.nome }}</span>
          <span class="pump-badge" :class="{ on: zone.pompa_on }">
            {{ zone.pompa_on ? '💧 Pompa ON' : 'Pompa OFF' }}
          </span>
        </div>

        <div class="zone-metrics">
          <div class="metric">
            <span class="metric-label">Umidità</span>
            <span class="metric-value">
              {{ zone.ultima_umidita != null ? zone.ultima_umidita.toFixed(1) + '%' : '—' }}
            </span>
          </div>
          <div class="metric" v-if="zone.device_id">
            <span class="metric-label">Device</span>
            <span class="metric-value device-id">{{ zone.device_id }}</span>
          </div>
        </div>

        <div class="zone-actions">
          <button
            class="btn-pump on"
            :disabled="zone.pompa_on || pumping[zone.id]"
            @click="pumpCmd(zone.id, 'on')"
          >
            Irrigazione ON
          </button>
          <button
            class="btn-pump off"
            :disabled="!zone.pompa_on || pumping[zone.id]"
            @click="pumpCmd(zone.id, 'off')"
          >
            OFF
          </button>
        </div>

        <div v-if="pumpError[zone.id]" class="alert-error small">{{ pumpError[zone.id] }}</div>
      </div>
    </div>

    <!-- Add zone modal -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h3>Nuova zona</h3>
        <div class="field">
          <label>ID zona</label>
          <input v-model.number="newZone.id" type="number" min="1" />
        </div>
        <div class="field">
          <label>Nome</label>
          <input v-model="newZone.nome" type="text" />
        </div>
        <div class="field">
          <label>Device ID (opzionale)</label>
          <input v-model="newZone.device_id" type="text" placeholder="nestgrow-a4b2" />
        </div>
        <p v-if="addError" class="alert-error small">{{ addError }}</p>
        <div class="modal-actions">
          <button @click="showAddModal = false">Annulla</button>
          <button class="btn-primary" @click="createZone" :disabled="addLoading">
            {{ addLoading ? 'Creazione...' : 'Crea' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const zones = ref([])
const license = ref(null)
const loadError = ref('')
const pumping = ref({})
const pumpError = ref({})
const showAddModal = ref(false)
const addError = ref('')
const addLoading = ref(false)
const newZone = ref({ id: 1, nome: '', device_id: '' })

let pollInterval = null

async function load() {
  try {
    const [zonesRes, licRes] = await Promise.all([
      axios.get('/zones/'),
      axios.get('/license/'),
    ])
    zones.value = zonesRes.data
    license.value = licRes.data
    loadError.value = ''
  } catch (e) {
    loadError.value = e.response?.data?.detail || 'Errore nel caricamento dati'
  }
}

async function pumpCmd(zonaId, cmd) {
  pumping.value[zonaId] = true
  pumpError.value[zonaId] = ''
  try {
    await axios.post(`/zones/${zonaId}/pump`, { cmd, sec: 30 })
    await load()
  } catch (e) {
    pumpError.value[zonaId] = e.response?.data?.detail || 'Errore comando pompa'
  } finally {
    pumping.value[zonaId] = false
  }
}

async function createZone() {
  addError.value = ''
  addLoading.value = true
  try {
    await axios.post('/zones/', newZone.value)
    showAddModal.value = false
    newZone.value = { id: 1, nome: '', device_id: '' }
    await load()
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Errore creazione zona'
  } finally {
    addLoading.value = false
  }
}

onMounted(() => {
  load()
  pollInterval = setInterval(load, 10000)
})
onUnmounted(() => clearInterval(pollInterval))
</script>

<style scoped>
.dashboard { padding: 24px; max-width: 1200px; margin: 0 auto; }

.top-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}
.top-bar h2 { font-size: 1.4rem; color: #1f5c2e; flex: 1; }
.license-badge {
  font-size: 0.85rem;
  background: #e8f5e9;
  border: 1px solid #a5d6a7;
  padding: 6px 12px;
  border-radius: 20px;
  color: #2e7d32;
}
.btn-add {
  background: #1f5c2e;
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
}
.btn-add:hover { background: #2d8048; }

.zones-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
}

.zone-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  border-left: 4px solid #2d8048;
}
.zone-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.zone-id { color: #888; font-size: 0.85rem; }
.zone-name { font-weight: 700; flex: 1; }
.pump-badge {
  font-size: 0.75rem;
  padding: 3px 8px;
  border-radius: 12px;
  background: #f0f0f0;
  color: #666;
}
.pump-badge.on { background: #e3f2fd; color: #1565c0; }

.zone-metrics { display: flex; gap: 24px; margin-bottom: 16px; }
.metric { display: flex; flex-direction: column; gap: 2px; }
.metric-label { font-size: 0.75rem; color: #888; }
.metric-value { font-size: 1.1rem; font-weight: 600; color: #1f5c2e; }
.device-id { font-size: 0.8rem; font-family: monospace; color: #555; }

.zone-actions { display: flex; gap: 8px; }
.btn-pump {
  flex: 1;
  padding: 8px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: opacity 0.2s;
}
.btn-pump:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-pump.on { background: #1565c0; color: white; }
.btn-pump.on:not(:disabled):hover { background: #1976d2; }
.btn-pump.off { background: #f5f5f5; color: #555; }
.btn-pump.off:not(:disabled):hover { background: #e0e0e0; }

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #888;
  font-size: 1.1rem;
}

.alert-error {
  background: #ffebee;
  color: #c62828;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 0.9rem;
}
.alert-error.small { margin-top: 10px; margin-bottom: 0; padding: 8px 12px; font-size: 0.8rem; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: white;
  border-radius: 16px;
  padding: 32px;
  width: 400px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.modal h3 { margin-bottom: 20px; color: #1f5c2e; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 5px; }
.field input {
  width: 100%;
  padding: 9px 13px;
  border: 1.5px solid #ddd;
  border-radius: 8px;
  font-size: 0.95rem;
}
.field input:focus { outline: none; border-color: #2d8048; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.modal-actions button {
  padding: 9px 20px;
  border-radius: 8px;
  border: 1.5px solid #ddd;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-primary { background: #1f5c2e; color: white; border-color: #1f5c2e; font-weight: 600; }
.btn-primary:hover:not(:disabled) { background: #2d8048; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
