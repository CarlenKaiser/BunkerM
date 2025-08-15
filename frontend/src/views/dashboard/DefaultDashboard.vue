<!-- Copyright (c) 2025 BunkerM -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch, ComputedRef } from 'vue'
import WidgetFive from './components/WidgetFive.vue'
import UniqueVisitor from './components/UniqueVisitor.vue'
import { generateNonce } from '../../utils/security'
import { getRuntimeConfig } from '@/config/runtime'
import { useAuthStore } from '@/stores/auth'

// =========================
// Types
// =========================
interface ByteStats {
  timestamps: string[]
  bytes_received: number[]
  bytes_sent: number[]
}

interface DailyMessageStats {
  dates: string[]
  counts: number[]
}

interface Stats {
  total_messages_received: string
  total_subscriptions: number
  retained_messages: number
  total_connected_clients: number
  bytes_stats: ByteStats
  daily_message_stats: DailyMessageStats
  mqtt_connected: boolean
  connection_error?: string
}

type RangeOption = '6hr' | 'daily'

/** Shape UniqueVisitor expects (kept backward-compatible) */
interface VisitorStatsPayload {
  fullStats: ByteStats
  sixHourStats: ByteStats
}

/** Window totals used solely for trend math */
interface WindowTotals {
  messages: number
  subs: number
  clients: number
}

// =========================
// Setup
// =========================
const authStore = useAuthStore()
const config = getRuntimeConfig()
const API_BASE_URL: string = config.MONITOR_API_URL

// Default stats object
const defaultStats: Stats = {
  total_messages_received: '0',
  total_subscriptions: 0,
  retained_messages: 0,
  total_connected_clients: 0,
  bytes_stats: { timestamps: [], bytes_received: [], bytes_sent: [] },
  daily_message_stats: { dates: [], counts: [] },
  mqtt_connected: false
}

// =========================
// State
// =========================
const stats = ref<Stats>({ ...defaultStats })
const error = ref<string | null>(null)
const isLoading = ref<boolean>(false)
let intervalId: number | null = null

// Trends (shown in WidgetFive)
const messagesTrend = ref<number>(0)
const subscriptionsTrend = ref<number>(0)
const clientsTrend = ref<number>(0)

// Track previous totals for the selected window
const previousWindowTotals = ref<WindowTotals | null>(null)

// Range selection (driven by WidgetFive via @range-change)
const selectedRange = ref<RangeOption>('6hr')

// =========================
/* Helpers */
// =========================
const calculateTrend = (previous: number, current: number): number => {
  if (previous === 0) return 0
  return Math.round(((current - previous) / previous) * 100)
}

const sumArray = (arr: number[]): number =>
  arr.reduce((a, b) => a + b, 0)

// Parse timestamps robustly (accepts ISO, ISO w/o Z, and "YYYY-MM-DD HH:mm:ss" as UTC)
const toDate = (ts: string): Date => {
  try {
    if (ts.includes('T')) {
      // ISO-like. Ensure Z if missing timezone and seconds present.
      return ts.endsWith('Z') || ts.includes('+') || (ts.match(/:/g) || []).length > 2
        ? new Date(ts)
        : new Date(ts + 'Z')
    }
    // Non-ISO: treat as UTC
    return new Date(ts + ' UTC')
  } catch {
    return new Date('invalid')
  }
}

// =========================
// Computed: visitor stats payload (keeps UniqueVisitor working)
// =========================
const visitorStats: ComputedRef<VisitorStatsPayload> = computed((): VisitorStatsPayload => {
  const byteStats: ByteStats = stats.value.bytes_stats

  // Always provide fullStats (raw, as received)
  const fullStats: ByteStats = byteStats ?? { timestamps: [], bytes_received: [], bytes_sent: [] }

  // Compute six-hour slice (used by 6hr selection and as a safe default)
  const sixHoursAgo = new Date(Date.now() - 6 * 60 * 60 * 1000)
  const sixHourStats: ByteStats = { timestamps: [], bytes_received: [], bytes_sent: [] }

  if (fullStats.timestamps?.length) {
    fullStats.timestamps.forEach((ts: string, i: number) => {
      const d = toDate(ts)
      if (!isNaN(d.getTime()) && d >= sixHoursAgo) {
        if (i < fullStats.bytes_received.length && i < fullStats.bytes_sent.length) {
          sixHourStats.timestamps.push(ts)
          sixHourStats.bytes_received.push(fullStats.bytes_received[i])
          sixHourStats.bytes_sent.push(fullStats.bytes_sent[i])
        }
      }
    })
  }

  return { fullStats, sixHourStats }
})

// =========================
// Computed: window totals used for trend math
// - Messages: uses selectedRange
//   * '6hr'  -> sum(bytes_received) from sixHourStats
//   * 'daily'-> sum(daily_message_stats.counts)
// - Subs/Clients: snapshot totals (we don't have historical arrays for these)
// =========================
const windowTotals: ComputedRef<WindowTotals> = computed((): WindowTotals => {
  if (selectedRange.value === '6hr') {
    const msgs = sumArray(visitorStats.value.sixHourStats.bytes_received)
    return {
      messages: msgs,
      subs: stats.value.total_subscriptions,
      clients: stats.value.total_connected_clients
    }
  } else {
    const dailyTotal = sumArray(stats.value.daily_message_stats.counts)
    return {
      messages: dailyTotal,
      subs: stats.value.total_subscriptions,
      clients: stats.value.total_connected_clients
    }
  }
})

// =========================
/* Watch: recalc trends whenever selected window data changes */
// =========================
watch(windowTotals, (curr: WindowTotals) => {
  if (previousWindowTotals.value) {
    messagesTrend.value = calculateTrend(previousWindowTotals.value.messages, curr.messages)
    subscriptionsTrend.value = calculateTrend(previousWindowTotals.value.subs, curr.subs)
    clientsTrend.value = calculateTrend(previousWindowTotals.value.clients, curr.clients)
  }
  previousWindowTotals.value = { ...curr }
})

// If the range changes, we want to reset the baseline so the
// next calculation compares within the new window, not across windows.
watch(selectedRange, () => {
  previousWindowTotals.value = null
  messagesTrend.value = 0
  subscriptionsTrend.value = 0
  clientsTrend.value = 0
})

// =========================
// Fetch API data
// =========================
const fetchStats = async (): Promise<void> => {
  isLoading.value = true
  try {
    const timestamp = Date.now() / 1000
    const nonce = generateNonce()

    const headers: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json'
    }
    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    const response: Response = await fetch(
      `${API_BASE_URL}/stats?nonce=${nonce}&timestamp=${timestamp}`,
      { method: 'GET', headers, credentials: 'include' }
    )

    if (!response.ok) {
      const errorData: Partial<{ message: string }> = await response.json().catch(() => ({}))
      switch (response.status) {
        case 401:
          throw new Error('Session expired. Please login again.')
        case 403:
          throw new Error('You do not have permission to view these stats.')
        case 429:
          throw new Error('Too many requests. Please slow down.')
        default:
          throw new Error(errorData.message || `API request failed with status ${response.status}`)
      }
    }

    const data: Stats = await response.json()
    const merged: Stats = {
      ...defaultStats,
      ...data,
      mqtt_connected: data.mqtt_connected ?? false
    }

    stats.value = merged

    if (!merged.mqtt_connected && merged.connection_error) {
      error.value = merged.connection_error
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : 'Failed to load dashboard data'
    stats.value = { ...defaultStats }
  } finally {
    isLoading.value = false
  }
}

// =========================
// Lifecycle
// =========================
onMounted((): void => {
  fetchStats()
  intervalId = window.setInterval(fetchStats, 2000)
})

onUnmounted((): void => {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
})
</script>

<template>
  <div class="dashboard-container">
    <!-- Connection status alert -->
    <v-alert v-if="!stats.mqtt_connected" type="warning" variant="tonal" class="mb-4">
      MQTT Broker is disconnected. Some data may not be current.
      <template v-if="error"><br>{{ error }}</template>
    </v-alert>

    <!-- Error alert -->
    <v-alert
      v-if="error && stats.mqtt_connected"
      type="error"
      variant="tonal"
      closable
      class="mb-4"
      @click:close="error = null"
    >
      {{ error }}
    </v-alert>

    <!-- Loading indicator -->
    <v-progress-linear
      v-if="isLoading"
      indeterminate
      color="primary"
      height="2"
      class="loading-bar"
    ></v-progress-linear>

    <!-- MQTT Stats Cards -->
    <WidgetFive
      :total-messages-received="stats.total_messages_received"
      :total-connected-clients="stats.total_connected_clients"
      :total-subscriptions="stats.total_subscriptions"
      :retained-messages="stats.retained_messages"
      :messages-trend="messagesTrend"
      :subscriptions-trend="subscriptionsTrend"
      :clients-trend="clientsTrend"
      @range-change="(range: RangeOption) => { selectedRange.value = range }"
    />

    <v-row>
      <!-- Message Rates Chart -->
      <v-col cols="12">
        <!-- Keep UniqueVisitor prop shape intact -->
        <UniqueVisitor
          :stats="visitorStats"
          @refresh="fetchStats"
        />
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.dashboard-container {
  padding: 1rem;
  max-width: 1800px;
  margin: 0 auto;
  position: relative;
}

.mb-4 {
  margin-bottom: 1rem;
}

.loading-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  margin: 0;
  padding: 0;
}
</style>
