<template>
  <div class="grafici-wrap">
    <div class="period-bar">
      <span class="period-label">Periodo:</span>
      <button
        v-for="p in periods"
        :key="p.value"
        :class="['period-btn', { active: periodo === p.value }]"
        @click="setPeriodo(p.value)"
      >{{ p.label }}</button>
    </div>

    <div v-if="loading" class="chart-loading">⏳ Caricamento grafici...</div>
    <div v-else-if="fetchError" class="chart-error">⚠️ {{ fetchError }}</div>

    <template v-else>
      <div class="charts-grid">
        <!-- Grafico 1: Umidità per zona -->
        <div class="chart-box">
          <h4 class="chart-title">💧 Umidità per zona</h4>
          <v-chart v-if="hasHumidityData" class="chart" :option="humidityOption" autoresize />
          <div v-else class="no-data">Nessun dato disponibile per il periodo selezionato 📊</div>
        </div>

        <!-- Grafico 2: Serbatoio -->
        <div class="chart-box">
          <h4 class="chart-title">🛢️ Livello serbatoio</h4>
          <v-chart v-if="hasTankData" class="chart" :option="tankOption" autoresize />
          <div v-else class="no-data">Nessun dato disponibile per il periodo selezionato 📊</div>
        </div>

        <!-- Grafico 3: Irrigazioni per zona (bar) -->
        <div class="chart-box">
          <h4 class="chart-title">🌿 Irrigazioni per zona</h4>
          <v-chart v-if="hasIrrigazioniData" class="chart" :option="irrigazioniOption" autoresize />
          <div v-else class="no-data">Nessun dato disponibile per il periodo selezionato 📊</div>
        </div>

        <!-- Grafico 4: Efficacia irrigazione (scatter) -->
        <div class="chart-box">
          <h4 class="chart-title">📈 Efficacia irrigazione</h4>
          <v-chart v-if="hasScatterData" class="chart" :option="scatterOption" autoresize />
          <div v-else class="no-data">Nessun dato disponibile per il periodo selezionato 📊</div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, BarChart, ScatterChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
  MarkLineComponent,
} from 'echarts/components'
import axios from 'axios'

use([
  CanvasRenderer,
  LineChart, BarChart, ScatterChart,
  GridComponent, TooltipComponent, LegendComponent, MarkLineComponent,
])

const props = defineProps({
  culla: { type: Object, required: true },
})

const ZONA_COLORS = ['#2d6a4f', '#1d6fa4', '#e07b00', '#6b2d8b']

const periods = [
  { label: '24h',  value: 1  },
  { label: '7gg',  value: 7  },
  { label: '30gg', value: 30 },
]

const periodo    = ref(7)
const loading    = ref(false)
const fetchError = ref('')
const stats      = ref(null)
const statsIrr   = ref(null)

async function fetchStats() {
  loading.value = true
  fetchError.value = ''
  try {
    const [s, si] = await Promise.all([
      axios.get(`/culle/${props.culla.id}/stats`,             { params: { giorni: periodo.value } }),
      axios.get(`/culle/${props.culla.id}/stats/irrigazioni`, { params: { giorni: periodo.value } }),
    ])
    stats.value    = s.data
    statsIrr.value = si.data
  } catch (e) {
    fetchError.value = e.response?.data?.detail || 'Errore caricamento grafici'
  } finally {
    loading.value = false
  }
}

function setPeriodo(v) {
  periodo.value = v
  fetchStats()
}

onMounted(fetchStats)

// ── Guards ──────────────────────────────────────────────────────────────────

const hasHumidityData  = computed(() => stats.value?.zona_umidita?.some(z => z.dati.length > 0))
const hasTankData      = computed(() => stats.value?.serbatoio?.length > 0)
const hasIrrigazioniData = computed(() => statsIrr.value?.per_zona?.some(z => z.totale_irrigazioni > 0))
const hasScatterData   = computed(() =>
  stats.value?.irrigazioni?.some(i => i.umidita_pre != null && i.umidita_post != null)
)

// ── Grafico 1: Umidità ──────────────────────────────────────────────────────

const humidityOption = computed(() => {
  if (!stats.value) return {}
  const zonaData = stats.value.zona_umidita

  const series = zonaData.map((z, idx) => {
    const color = ZONA_COLORS[idx] || ZONA_COLORS[0]
    const seriesName = z.coltura ? `Z${z.zona} ${z.nome} — ${z.coltura}` : `Z${z.zona} ${z.nome}`

    const thresholdLines = []
    if (z.umidita_soglia_min != null) {
      thresholdLines.push({
        yAxis: z.umidita_soglia_min,
        lineStyle: { color, type: 'dashed', opacity: 0.4, width: 1 },
        label: { show: false },
        symbol: 'none',
      })
    }
    if (z.umidita_soglia_max != null) {
      thresholdLines.push({
        yAxis: z.umidita_soglia_max,
        lineStyle: { color, type: 'dashed', opacity: 0.4, width: 1 },
        label: { show: false },
        symbol: 'none',
      })
    }

    const irrLines = stats.value.irrigazioni
      .filter(irr => irr.zona === z.zona)
      .map(irr => ({
        xAxis: irr.ts_inizio,
        lineStyle: { color: '#e53935', width: 1, type: 'solid', opacity: 0.5 },
        label: { show: false },
        symbol: 'none',
      }))

    return {
      name: seriesName,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: z.dati.map(d => [d.ts, d.v]),
      lineStyle: { color, width: 2 },
      itemStyle: { color },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        data: [...thresholdLines, ...irrLines],
      },
    }
  })

  return {
    backgroundColor: '#fff',
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        if (!params.length) return ''
        const ts = new Date(params[0].axisValue).toLocaleString('it-IT', {
          day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
        })
        let html = `<b>${ts}</b><br/>`
        for (const p of params) {
          if (p.value) {
            html += `<span style="color:${p.color}">●</span> ${p.seriesName}: <b>${p.value[1]}%</b><br/>`
          }
        }
        return html
      },
    },
    legend: {
      type: 'scroll',
      bottom: 0,
      textStyle: { fontSize: 11 },
    },
    grid: { left: 48, right: 16, top: 16, bottom: 64 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: {
      type: 'value', min: 0, max: 100,
      axisLabel: { formatter: '{value}%', fontSize: 11 },
    },
    series,
  }
})

// ── Grafico 2: Serbatoio ────────────────────────────────────────────────────

const tankOption = computed(() => {
  if (!stats.value) return {}
  return {
    backgroundColor: '#fff',
    animation: true,
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        if (!params.length) return ''
        const ts = new Date(params[0].axisValue).toLocaleString('it-IT', {
          day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
        })
        return `${ts}<br/>Livello: <b>${params[0].value[1]}%</b>`
      },
    },
    grid: { left: 52, right: 16, top: 16, bottom: 40 },
    xAxis: { type: 'time', axisLabel: { fontSize: 10 } },
    yAxis: {
      type: 'value', min: 0, max: 100,
      axisLabel: { formatter: '{value}%', fontSize: 11 },
    },
    series: [{
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: stats.value.serbatoio.map(d => [d.ts, d.v]),
      lineStyle: { color: '#1976d2', width: 2 },
      itemStyle: { color: '#1976d2' },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(25,118,210,0.5)' },
            { offset: 1, color: 'rgba(187,222,251,0.08)' },
          ],
        },
      },
      markLine: {
        silent: true,
        symbol: ['none', 'none'],
        data: [{
          yAxis: 10,
          lineStyle: { color: '#e53935', type: 'dashed', width: 2 },
          label: { formatter: '⚠ 10% blocco', color: '#e53935', fontSize: 10 },
        }],
      },
    }],
  }
})

// ── Grafico 3: Bar irrigazioni ──────────────────────────────────────────────

const irrigazioniOption = computed(() => {
  if (!statsIrr.value) return {}
  const zones = statsIrr.value.per_zona
  return {
    backgroundColor: '#fff',
    animation: true,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const z = zones[params[0].dataIndex]
        return `<b>${z.nome}</b><br/>Irrigazioni: ${z.totale_irrigazioni}<br/>Durata media: ${z.durata_media_sec}s<br/>Umidità pre: ${z.umidita_media_pre ?? '—'}%<br/>Umidità post: ${z.umidita_media_post ?? '—'}%`
      },
    },
    grid: { left: 100, right: 40, top: 16, bottom: 36 },
    xAxis: { type: 'value', name: 'N. irrigazioni', nameTextStyle: { fontSize: 11 } },
    yAxis: {
      type: 'category',
      data: zones.map(z => z.nome),
      axisLabel: { fontSize: 11 },
    },
    series: [{
      type: 'bar',
      label: { show: true, position: 'right', fontSize: 11 },
      data: zones.map((z, i) => ({
        value: z.totale_irrigazioni,
        itemStyle: { color: ZONA_COLORS[i] || ZONA_COLORS[0] },
      })),
    }],
  }
})

// ── Grafico 4: Scatter efficacia ────────────────────────────────────────────

const scatterOption = computed(() => {
  if (!stats.value) return {}
  const zonaData = stats.value.zona_umidita

  const series = zonaData.map((z, idx) => ({
    name: z.nome,
    type: 'scatter',
    symbolSize: 9,
    itemStyle: { color: ZONA_COLORS[idx] || ZONA_COLORS[0], opacity: 0.85 },
    data: stats.value.irrigazioni
      .filter(irr => irr.zona === z.zona && irr.umidita_pre != null && irr.umidita_post != null)
      .map(irr => [irr.umidita_pre, irr.umidita_post, irr.ts_inizio, irr.durata_sec]),
  }))

  series.push({
    name: 'y = x',
    type: 'line',
    data: [[0, 0], [100, 100]],
    lineStyle: { type: 'dashed', color: '#ccc', width: 1 },
    itemStyle: { color: '#ccc' },
    symbol: 'none',
    silent: true,
    legendHoverLink: false,
  })

  return {
    backgroundColor: '#fff',
    animation: true,
    tooltip: {
      trigger: 'item',
      formatter(params) {
        if (params.seriesName === 'y = x') return ''
        const [pre, post, ts, durata] = params.data
        const d = new Date(ts).toLocaleDateString('it-IT')
        return `<b>${params.seriesName}</b><br/>${d}<br/>Pre: ${pre}% → Post: ${post}%<br/>Durata: ${durata ?? '—'}s`
      },
    },
    legend: {
      bottom: 0,
      data: zonaData.map(z => z.nome),
      textStyle: { fontSize: 11 },
    },
    grid: { left: 52, right: 16, top: 16, bottom: 64 },
    xAxis: {
      type: 'value', name: 'Umidità pre %',
      min: 0, max: 100,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { formatter: '{value}%', fontSize: 10 },
    },
    yAxis: {
      type: 'value', name: 'Umidità post %',
      min: 0, max: 100,
      nameTextStyle: { fontSize: 11 },
      axisLabel: { formatter: '{value}%', fontSize: 10 },
    },
    series,
  }
})
</script>

<style scoped>
.grafici-wrap {
  border-top: 1px solid #e8f5e9;
  background: #f8fdf9;
  padding: 16px;
}

.period-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.period-label { font-size: 0.82rem; color: #666; font-weight: 600; }
.period-btn {
  padding: 4px 14px;
  border: 1.5px solid #ccc;
  border-radius: 20px;
  background: white;
  cursor: pointer;
  font-size: 0.82rem;
  transition: all 0.15s;
}
.period-btn.active { background: #1f5c2e; color: white; border-color: #1f5c2e; }
.period-btn:hover:not(.active) { border-color: #2d8048; color: #1f5c2e; }

.chart-loading { text-align: center; padding: 40px; color: #888; }
.chart-error {
  text-align: center; padding: 16px; color: #c62828;
  background: #ffebee; border-radius: 8px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.chart-box {
  background: white;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 12px 16px;
}
.chart-title {
  font-size: 0.88rem;
  font-weight: 700;
  color: #1f5c2e;
  margin-bottom: 8px;
}
.chart { height: 280px; width: 100%; }

.no-data {
  height: 160px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #aaa;
  font-size: 0.88rem;
}

@media (max-width: 760px) {
  .charts-grid { grid-template-columns: 1fr; }
  .chart { height: 240px; }
}
</style>
