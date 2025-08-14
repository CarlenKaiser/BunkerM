<!-- Copyright (c) 2025 BunkerM -->
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import WidgetFive from './components/WidgetFive.vue'
import UniqueVisitor from './components/UniqueVisitor.vue'
import { generateNonce } from '../../utils/security'
import { getRuntimeConfig } from '@/config/runtime'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const config = getRuntimeConfig()

// API configuration
const API_BASE_URL = config.MONITOR_API_URL

interface Stats {
  total_messages_received: string
  total_subscriptions: number
  retained_messages: number
  total_connected_clients: number
  bytes_stats: ByteStats
  daily_message_stats: DailyMessageStats
  mqtt_connected: boolean
  connection_error?: string
  stats_timestamp?: string
  message_stats_timestamps?: string[]
  subscription_stats_timestamps?: string[]
  client_stats_timestamps?: string[]
  retained_stats_timestamps?: string[]
}

interface ByteStats {
  timestamps: string[]
  bytes_received: number[]
  bytes_sent: number[]
}

interface DailyMessageStats {
  dates: string[]
  counts: number[]
  timestamps?: string[] // Add timestamps for daily stats
}

// New interface for comprehensive stats with timestamps
interface TimestampedStats {
  timestamp: string
  total_messages_received: string
  total_subscriptions: number
  retained_messages: number
  total_connected_clients: number
}

// Enhanced visitor stats interface
interface VisitorStats {
  fullStats: ByteStats
  sixHourStats: ByteStats
  timestampedMetrics?: TimestampedStats[]
}

const defaultStats: Stats = {
  total_messages_received: "0",
  total_subscriptions: 0,
  retained_messages: 0,
  total_connected_clients: 0,
  bytes_stats: {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  },
  daily_message_stats: {
    dates: [],
    counts: [],
    timestamps: []
  },
  mqtt_connected: false,
  stats_timestamp: new Date().toISOString(),
  message_stats_timestamps: [],
  subscription_stats_timestamps: [],
  client_stats_timestamps: [],
  retained_stats_timestamps: []
}

const stats = ref<Stats>({ ...defaultStats })
const error = ref<string | null>(null)
const isLoading = ref(false)
let intervalId: number | null = null

const visitorStats = computed(() => {
  const byteStats = stats.value.bytes_stats
  const sixHoursAgo = new Date(Date.now() - 6 * 60 * 60 * 1000)
  
  const sixHourStats: ByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  }

  if (byteStats.timestamps?.length) {
    byteStats.timestamps.forEach((ts: string, i: number) => {
      const timestampDate = new Date(ts)
      if (timestampDate >= sixHoursAgo && 
          i < byteStats.bytes_received.length && 
          i < byteStats.bytes_sent.length) {
        sixHourStats.timestamps.push(ts)
        sixHourStats.bytes_received.push(byteStats.bytes_received[i])
        sixHourStats.bytes_sent.push(byteStats.bytes_sent[i])
      }
    })
  }

  // Create timestamped metrics array for other stats
  const timestampedMetrics: TimestampedStats[] = []
  
  // If you have historical data for other metrics, combine them here
  if (stats.value.message_stats_timestamps?.length) {
    stats.value.message_stats_timestamps.forEach((timestamp: string, index: number) => {
      timestampedMetrics.push({
        timestamp,
        total_messages_received: stats.value.total_messages_received,
        total_subscriptions: stats.value.total_subscriptions,
        retained_messages: stats.value.retained_messages,
        total_connected_clients: stats.value.total_connected_clients
      })
    })
  } else {
    // Fallback: use current timestamp for current values
    timestampedMetrics.push({
      timestamp: stats.value.stats_timestamp || new Date().toISOString(),
      total_messages_received: stats.value.total_messages_received,
      total_subscriptions: stats.value.total_subscriptions,
      retained_messages: stats.value.retained_messages,
      total_connected_clients: stats.value.total_connected_clients
    })
  }

  return {
    fullStats: byteStats,
    sixHourStats,
    timestampedMetrics
  }
})

const fetchStats = async () => {
  isLoading.value = true
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), 15000) // 15 second timeout
  
  try {
    const timestamp = Date.now() / 1000
    const nonce = generateNonce()

    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    }

    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`
    }

    const response = await fetch(
      `${API_BASE_URL}/stats?nonce=${nonce}&timestamp=${timestamp}&include_timestamps=true`,
      {
        method: 'GET',
        headers,
        credentials: 'include',
        signal: controller.signal // Add abort signal
      }
    )

    clearTimeout(timeoutId) // Clear timeout if request succeeds

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      console.error('API Error:', response.status, errorData)

      switch (response.status) {
        case 401:
          throw new Error('Session expired. Please login again.')
        case 403:
          throw new Error('You do not have permission to view these stats.')
        case 429:
          throw new Error('Too many requests. Please slow down.')
        case 504:
          throw new Error('Request timed out. The server is taking too long to respond.')
        case 502:
        case 503:
          throw new Error('Server temporarily unavailable. Please try again in a moment.')
        default:
          throw new Error(errorData.message || `API request failed with status ${response.status}`)
      }
    }

    const data = await response.json()
    
    // Validate the response data structure
    if (!data || typeof data !== 'object') {
      throw new Error('Invalid response format from server')
    }
    
    stats.value = {
      ...defaultStats,
      ...data,
      mqtt_connected: data.mqtt_connected || false
    }

    if (!data.mqtt_connected && data.connection_error) {
      error.value = data.connection_error
    } else {
      error.value = null // Clear error on successful response
    }

  } catch (err: unknown) {
  clearTimeout(timeoutId)
  console.error('Fetch error:', err)
  
  if (err instanceof DOMException && err.name === 'AbortError') {
    error.value = 'Request timed out. Please try again.'
  } else if (err instanceof Error) {
    error.value = err.message
  } else {
    error.value = 'Failed to load dashboard data'
  }
  
  // Don't reset stats completely on timeout, keep showing last known good data
  if (!(err instanceof DOMException && err.name === 'AbortError')) {
    stats.value = { ...defaultStats }
  }
} finally {
  isLoading.value = false
}
}

onMounted(() => {
  fetchStats()
  intervalId = window.setInterval(fetchStats, 2000)
})

onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId)
    intervalId = null
  }
})
</script>

<template>
  <div class="dashboard-container">
    <!-- Connection status alert -->
    <v-alert 
      v-if="!stats.mqtt_connected"
      type="warning"
      variant="tonal"
      class="mb-4"
    >
      MQTT Broker is disconnected. Some data may not be current.
      <template v-if="error">
        <br>{{ error }}
      </template>
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
    />

    <v-row>
      <!-- Message Rates Chart -->
      <v-col cols="12">
        <UniqueVisitor 
          :stats="visitorStats" 
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