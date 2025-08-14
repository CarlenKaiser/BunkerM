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

interface FilteredStats {
  bytes: ByteStats
  messages: number
  subs: number
  clients: number
}

type RangeOption = '6hr' | 'daily'

// =========================
// Setup
// =========================
const authStore = useAuthStore()
const config = getRuntimeConfig()
const API_BASE_URL: string = config.MONITOR_API_URL

// Default stats object
const defaultStats: Stats = {
  total_messages_received: "0",
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

// Trends
const messagesTrend = ref<number>(0)
const subscriptionsTrend = ref<number>(0)
const clientsTrend = ref<number>(0)

// Track previous window totals
const previousWindowStats = ref<{ messages: number; subs: number; clients: number } | null>(null)

// Range selection
const selectedRange = ref<RangeOption>('6hr')

// =========================
// Helper functions
// =========================
const parseNumber = (numStr: string): number =>
  parseFloat(numStr.replace(/,/g, ''))

const calculateTrend = (previous: number, current: number): number => {
  if (previous === 0) return 0
  return Math.round(((current - previous) / previous) * 100)
}

const sumArray = (arr: number[]): number =>
  arr.reduce((a, b) => a + b, 0)

// =========================
// Computed: filtered stats based on selected range
// =========================
const filteredStats: ComputedRef<FilteredStats> = computed((): FilteredStats => {
  const byteStats: ByteStats = stats.value.bytes_stats
  const messageStats: DailyMessageStats = stats.value.daily_message_stats

  if (selectedRange.value === '6hr') {
    const sixHoursAgo = new Date(Date.now() - 6 * 60 * 60 * 1000)
    const sixHourBytes: ByteStats = { timestamps: [], bytes_received: [], bytes_sent: [] }

    byteStats.timestamps.forEach((ts: string, i: number) => {
      let timestampDate: Date
      try {
        if (ts.includes('T')) {
          timestampDate = ts.endsWith('Z') || ts.includes('+') || (ts.match(/:/g) || []).length > 2
            ? new Date(ts)
            : new Date(ts + 'Z')
        } else {
          timestampDate = new Date(ts + ' UTC')
        }

        if (!isNaN(timestampDate.getTime()) && timestampDate >= sixHoursAgo) {
          sixHourBytes.timestamps.push(ts)
          sixHourBytes.bytes_received.push(byteStats.bytes_received[i])
          sixHourBytes.bytes_sent.push(byteStats.bytes_sent[i])
        }
      } catch {
        // Ignore bad timestamps
      }
    })

    return {
      bytes: sixHourBytes,
      messages: sumArray(sixHourBytes.bytes_received), // Using bytes as proxy for message count
      subs: stats.value.total_subscriptions,
      clients: stats.value.total_connected_clients
    }
  } else {
    // Daily
    const dailyTotal = sumArray(messageStats.counts)
    return {
      bytes: byteStats,
      messages: dailyTotal,
      subs: stats.value.total_subscriptions,
      clients: stats.value.total_connected_clients
    }
  }
})

// =========================
// Watch: recalc trends when filtered stats change
// =========================
watch(filteredStats, (curr: FilteredStats) => {
  if (previousWindowStats.value) {
    messagesTrend.value = calculateTrend(previousWindowStats.value.messages, curr.messages)
    subscriptionsTrend.value = calculateTrend(previousWindowStats.value.subs, curr.subs)
    clientsTrend.value = calculateTrend(previousWindowStats.value.clients, curr.clients)
  }
  previousWindowStats.value = { ...curr }
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
    stats.value = { ...defaultStats, ...data, mqtt_connected: data.mqtt_connected || false }

    if (!data.mqtt_connected && data.connection_error) {
      error.value = data.connection_error
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
      @range-change="(range: RangeOption) => selectedRange.value = range"
    />

    <v-row>
      <!-- Message Rates Chart -->
      <v-col cols="12">
        <UniqueVisitor :stats="filteredStats.bytes" />
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
}
</style>
