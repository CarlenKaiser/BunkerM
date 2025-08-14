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

interface FilteredByteStats {
  timestamps: string[]
  bytes_received: number[]
  bytes_sent: number[]
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
    counts: []
  },
  mqtt_connected: false
}

const stats = ref<Stats>({ ...defaultStats })
const error = ref<string | null>(null)
const isLoading = ref(false)
let intervalId: number | null = null

// Fixed computed property declaration
const processedByteStats = computed(() => {
  const byteStats = stats.value.bytes_stats
  
  const defaultReturn: FilteredByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  }

  if (!byteStats || 
      !byteStats.timestamps || 
      !byteStats.bytes_received || 
      !byteStats.bytes_sent ||
      byteStats.timestamps.length === 0) {
    return defaultReturn
  }

  const now = new Date()
  const sixHoursAgo = new Date(now.getTime() - 6 * 60 * 60 * 1000)

  const filteredData: FilteredByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  }

  byteStats.timestamps.forEach((timestamp: string, index: number) => {
    try {
      const date = new Date(timestamp)
      if (date >= sixHoursAgo && 
          index < byteStats.bytes_received.length && 
          index < byteStats.bytes_sent.length) {
        filteredData.timestamps.push(timestamp)
        filteredData.bytes_received.push(byteStats.bytes_received[index])
        filteredData.bytes_sent.push(byteStats.bytes_sent[index])
      }
    } catch (e) {
      console.warn('Error processing timestamp at index', index, e)
    }
  })

  return filteredData
})

const fetchStats = async () => {
  isLoading.value = true
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
      `${API_BASE_URL}/stats?nonce=${nonce}&timestamp=${timestamp}`,
      {
        method: 'GET',
        headers,
        credentials: 'include'
      }
    )

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
        default:
          throw new Error(errorData.message || `API request failed with status ${response.status}`)
      }
    }

    const data = await response.json()
    
    stats.value = {
      ...defaultStats,
      ...data,
      mqtt_connected: data.mqtt_connected || false
    }

    if (!data.mqtt_connected && data.connection_error) {
      error.value = data.connection_error
    }

  } catch (err) {
    console.error('Fetch error:', err)
    error.value = err instanceof Error ? err.message : 'Failed to load dashboard data'
    stats.value = { ...defaultStats }
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
          :byte-stats="processedByteStats" 
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