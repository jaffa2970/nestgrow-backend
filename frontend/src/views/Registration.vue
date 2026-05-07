<template>
  <div class="reg-page">
    <div class="reg-card">
      <div class="reg-header">
        <h1>🌱 NestGrow</h1>
        <p class="subtitle">by lake8.dev</p>
        <p class="reg-title">{{ isUpgrade ? 'Aggiorna il tuo piano' : 'Attiva NestGrow' }}</p>
      </div>

      <form @submit.prevent="handleSubmit">
        <!-- Tenant info (read-only in upgrade mode) -->
        <div class="field">
          <label>Ragione Sociale</label>
          <input v-model="form.ragione_sociale" type="text"
            placeholder="Mario Rossi / Azienda Agricola SRL" required />
        </div>

        <div class="field">
          <label>P.IVA o Codice Fiscale</label>
          <input v-model="form.piva" type="text"
            placeholder="P.IVA (11 cifre) o Codice Fiscale (16 caratteri)"
            @input="pivaError = ''" required />
          <span v-if="pivaError" class="field-error">{{ pivaError }}</span>
        </div>

        <div class="field">
          <label>Email</label>
          <input v-model="form.email" type="email"
            placeholder="email@azienda.it" required />
        </div>

        <!-- Plan selection -->
        <div class="field">
          <label>Seleziona piano</label>
          <div class="plans-grid">
            <div
              v-for="p in plans"
              :key="p.id"
              class="plan-card"
              :class="{
                selected: form.piano === p.id,
                current: isUpgrade && p.id === currentPiano,
                disabled: p.contact || (isUpgrade && p.id === currentPiano),
              }"
              @click="!p.contact && !(isUpgrade && p.id === currentPiano) ? (form.piano = p.id) : null"
            >
              <div class="plan-name">{{ p.name }}</div>
              <div class="plan-price">{{ p.price }}</div>
              <div class="plan-culle">{{ p.culle }}</div>
              <div v-if="isUpgrade && p.id === currentPiano" class="plan-badge current">
                Piano attivo
              </div>
              <button
                type="button"
                class="plan-btn"
                :class="{ active: form.piano === p.id }"
                :disabled="p.contact || (isUpgrade && p.id === currentPiano)"
              >
                <template v-if="p.contact">Contattaci</template>
                <template v-else-if="isUpgrade && p.id === currentPiano">Attivo</template>
                <template v-else-if="form.piano === p.id">✓ Selezionato</template>
                <template v-else>Seleziona</template>
              </button>
            </div>
          </div>
        </div>

        <!-- TOS (only on initial registration) -->
        <div v-if="!isUpgrade" class="field tos-field">
          <label class="tos-label">
            <input v-model="form.tos_accettato" type="checkbox" />
            <span>
              Accetto i
              <a href="https://license.lake8.dev/tos" target="_blank">Termini di Servizio</a>
              e la
              <a href="https://license.lake8.dev/privacy" target="_blank">Privacy Policy</a>
            </span>
          </label>
        </div>

        <p v-if="error" class="alert-error">{{ error }}</p>

        <button
          type="submit"
          class="submit-btn"
          :disabled="loading || (!isUpgrade && !form.tos_accettato)"
        >
          <span v-if="loading">⏳ {{ loadingMsg }}</span>
          <span v-else>{{ isUpgrade ? '🔄 Aggiorna piano' : '🌱 Attiva NestGrow' }}</span>
        </button>

        <div v-if="loading" class="loading-detail">
          <div class="loading-steps">
            <span :class="{ active: loadingStep >= 1 }">Verifica dati</span>
            <span class="sep">→</span>
            <span :class="{ active: loadingStep >= 2 }">Registrazione</span>
            <span class="sep">→</span>
            <span :class="{ active: loadingStep >= 3 }">Attesa JWT</span>
          </div>
        </div>

        <div v-if="pendingApproval" class="pending-banner">
          ⏳ Registrazione inviata! La licenza sarà attivata entro 24 ore da lake8.dev.<br>
          Puoi già accedere con il piano Free — il supporto si abiliterà dopo l'approvazione.
        </div>

        <div v-if="isUpgrade" class="back-link">
          <a href="#" @click.prevent="$router.back()">← Torna alla dashboard</a>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import axios from 'axios'

const router = useRouter()
const route = useRoute()

const isUpgrade = computed(() => route.query.upgrade === 'true')
const currentPiano = ref('')
const loading = ref(false)
const loadingMsg = ref('Attivazione in corso...')
const loadingStep = ref(0)
const pendingApproval = ref(false)
const error = ref('')
const pivaError = ref('')
let loadingTimer = null

const form = ref({
  ragione_sociale: '',
  piva: '',
  email: '',
  piano: 'free',
  tos_accettato: false,
})

// enterprise maps to the "ai" plan on the License Server (10 culle)
const plans = [
  { id: 'free',       name: 'Free',       price: '€0/mese',   culle: '1 culla',   contact: false },
  { id: 'pro',        name: 'Pro',        price: '€29/mese',  culle: '5 culle',   contact: false },
  { id: 'enterprise', name: 'Enterprise', price: '€99/mese',  culle: '10 culle',  contact: false },
  { id: 'ultra',      name: 'Ultra',      price: 'Su misura', culle: 'Illimitato', contact: true },
]

onMounted(async () => {
  if (isUpgrade.value) {
    try {
      const { data } = await axios.get('/license/')
      if (data.registrato) {
        form.value.ragione_sociale = data.ragione_sociale || ''
        form.value.piva = data.piva || ''
        form.value.email = data.email || ''
        form.value.piano = data.piano || 'free'
        currentPiano.value = data.piano || 'free'
      }
    } catch { /* ignore */ }
  }
})

function validatePiva(v) {
  const s = v.trim().toUpperCase()
  if (s.length === 11 && /^\d+$/.test(s)) return true
  if (s.length === 16 && /^[A-Z0-9]+$/i.test(s)) return true
  return false
}

async function handleSubmit() {
  error.value = ''
  pivaError.value = ''

  if (!validatePiva(form.value.piva)) {
    pivaError.value = 'P.IVA (11 cifre) o Codice Fiscale (16 caratteri alfanumerici)'
    return
  }

  if (!isUpgrade.value && !form.value.tos_accettato) {
    error.value = 'Devi accettare i Termini di Servizio per continuare'
    return
  }

  loading.value = true
  loadingStep.value = 1
  loadingMsg.value = 'Verifica dati...'
  pendingApproval.value = false

  // Animate loading steps
  loadingTimer = setTimeout(() => {
    loadingStep.value = 2
    loadingMsg.value = 'Registrazione in corso...'
  }, 800)
  const t2 = setTimeout(() => {
    loadingStep.value = 3
    loadingMsg.value = 'Attesa conferma JWT...'
  }, 2500)

  try {
    const { data } = await axios.post('/license/register', {
      ...form.value,
      tos_accettato: isUpgrade.value ? true : form.value.tos_accettato,
    }, { timeout: 30000 })

    if (isUpgrade.value) {
      router.push('/')
    } else if (data.pending_approval) {
      pendingApproval.value = true
      // Redirect after 4 seconds so user can read the message
      setTimeout(() => router.push('/login'), 4000)
    } else {
      router.push('/login')
    }
  } catch (e) {
    const detail = e.response?.data?.detail
    if (Array.isArray(detail)) {
      error.value = detail.map(d => d.msg).join(', ')
    } else {
      error.value = detail || 'Errore durante la registrazione'
    }
  } finally {
    clearTimeout(loadingTimer)
    clearTimeout(t2)
    loading.value = false
    loadingStep.value = 0
  }
}

onUnmounted(() => {
  if (loadingTimer) clearTimeout(loadingTimer)
})
</script>

<style scoped>
.reg-page {
  min-height: 100vh;
  background: linear-gradient(135deg, #1f5c2e 0%, #2d8048 100%);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 32px 16px;
}
.reg-card {
  background: white;
  border-radius: 20px;
  padding: 40px;
  width: 100%;
  max-width: 780px;
  box-shadow: 0 24px 64px rgba(0,0,0,0.2);
}
.reg-header { text-align: center; margin-bottom: 32px; }
.reg-header h1 { font-size: 2rem; color: #1f5c2e; }
.subtitle { color: #888; font-size: 0.85rem; margin-bottom: 8px; }
.reg-title { font-size: 1.2rem; font-weight: 700; color: #333; }

.field { margin-bottom: 18px; }
.field label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 6px; color: #444; }
.field input[type="text"],
.field input[type="email"] {
  width: 100%; padding: 10px 14px;
  border: 1.5px solid #ddd; border-radius: 8px;
  font-size: 0.95rem; transition: border-color 0.2s;
}
.field input:focus { outline: none; border-color: #2d8048; }
.field input.readonly { background: #f5f5f5; color: #666; cursor: not-allowed; }
.field-error { color: #c0392b; font-size: 0.78rem; margin-top: 4px; display: block; }

/* Plan cards */
.plans-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-top: 8px;
}
.plan-card {
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  padding: 16px 10px;
  text-align: center;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
  position: relative;
}
.plan-card:hover:not(.disabled) { border-color: #2d8048; transform: translateY(-2px); box-shadow: 0 4px 16px rgba(45,128,72,0.15); }
.plan-card.selected { border-color: #1f5c2e; background: #f0faf2; box-shadow: 0 4px 16px rgba(31,92,46,0.2); }
.plan-card.disabled { cursor: default; opacity: 0.85; }
.plan-card.current { border-color: #aaa; background: #f8f8f8; }

.plan-name { font-weight: 700; font-size: 1rem; margin-bottom: 4px; color: #222; }
.plan-price { font-size: 0.85rem; color: #555; margin-bottom: 4px; }
.plan-culle { font-size: 0.8rem; color: #888; margin-bottom: 12px; }

.plan-badge { font-size: 0.7rem; font-weight: 600; margin-bottom: 6px; }
.plan-badge.current { color: #888; }

.plan-btn {
  width: 100%; padding: 6px;
  border: 1.5px solid #ccc; border-radius: 6px;
  background: white; font-size: 0.78rem; cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}
.plan-btn.active { background: #1f5c2e; color: white; border-color: #1f5c2e; }
.plan-btn:disabled { cursor: not-allowed; background: #eee; color: #999; border-color: #ddd; }

/* TOS */
.tos-field { margin-top: 8px; }
.tos-label {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 0.88rem;
  color: #555;
  cursor: pointer;
}
.tos-label input[type="checkbox"] { margin-top: 2px; flex-shrink: 0; }
.tos-label a { color: #1f5c2e; }

.alert-error {
  background: #ffebee; color: #c62828;
  padding: 10px 14px; border-radius: 8px;
  margin-bottom: 14px; font-size: 0.88rem;
}

.submit-btn {
  width: 100%; padding: 14px;
  background: #1f5c2e; color: white;
  border: none; border-radius: 10px;
  font-size: 1rem; font-weight: 700;
  cursor: pointer; margin-top: 8px;
  transition: background 0.2s, opacity 0.2s;
}
.submit-btn:hover:not(:disabled) { background: #2d8048; }
.submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.loading-detail { margin-top: 10px; text-align: center; }
.loading-steps {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 0.78rem; color: #888;
}
.loading-steps span { opacity: 0.4; transition: opacity 0.3s; }
.loading-steps span.active { opacity: 1; color: #1f5c2e; font-weight: 600; }
.loading-steps .sep { opacity: 0.3; }

.pending-banner {
  background: #e8f5e9; border: 1.5px solid #2d8048;
  border-radius: 10px; padding: 14px 16px;
  font-size: 0.88rem; color: #1b5e20; margin-top: 12px;
  line-height: 1.6; text-align: center;
}

.back-link { text-align: center; margin-top: 16px; font-size: 0.88rem; }
.back-link a { color: #555; text-decoration: none; }
.back-link a:hover { color: #1f5c2e; }

@media (max-width: 600px) {
  .plans-grid { grid-template-columns: repeat(2, 1fr); }
  .reg-card { padding: 24px 16px; }
}
</style>
