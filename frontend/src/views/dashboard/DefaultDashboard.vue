// Enhanced dashboard with window-based trends
<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
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

interface TimeWindow {
  label: string
  value: string
  hours: number
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

// Component state
const stats = ref<Stats>({ ...defaultStats })
const selectedTimeWindow = ref<string>('6h')
const error = ref<string | null>(null)
const isLoading = ref(false)
let intervalId: number | null = null

// Time window options
const timeWindows: TimeWindow[] = [
  { label: '1 Hour', value: '1h', hours: 1 },
  { label: '6 Hours', value: '6h', hours: 6 },
  { label: '24 Hours', value: '24h', hours: 24 },
  { label: '7 Days', value: '7d', hours: 168 }
]

// Helper functions
const parseNumber = (numStr: string): number => {
  const cleaned = numStr.toString().replace(/[,\s]/g, '')
  const parsed = parseFloat(cleaned)
  
  if (isNaN(parsed)) {
    console.warn(`Failed to parse number: "${numStr}"`)
    return 0
  }
  
  return parsed
}

const calculateTrend = (previous: number, current: number): number => {
  if (previous === 0 && current === 0) return 0
  if (previous === 0 && current > 0) return 100
  if (previous > 0 && current === 0) return -100
  return Math.round(((current - previous) / previous) * 100)
}

const getCurrentTimeWindow = (): TimeWindow => {
  return timeWindows.find(w => w.value === selectedTimeWindow.value) || timeWindows[1]
}

interface WindowDataPoint {
  timestamp: string
  value: number
}

interface TrendResult {
  messagesTrend: number
  subscriptionsTrend: number
  clientsTrend: number
}

// Calculate trends based on selected time window
const calculateWindowBasedTrends = (): TrendResult => {
  const currentWindow = getCurrentTimeWindow()
  const cutoffTime = new Date(Date.now() - currentWindow.hours * 60 * 60 * 1000)
  
  const byteStats = stats.value.bytes_stats
  
  // For byte-based trends (messages received/sent)
  const getWindowStats = (timestamps: string[], values: number[]): WindowDataPoint[] => {
    const windowData = timestamps
      .map((ts: string, i: number): WindowDataPoint => ({ timestamp: ts, value: values[i] || 0 }))
      .filter((item: WindowDataPoint): boolean => {
        try {
          const date = new Date(item.timestamp.includes('T') 
            ? (item.timestamp.endsWith('Z') || item.timestamp.includes('+') ? item.timestamp : item.timestamp + 'Z')
            : item.timestamp + ' UTC'
          )
          return date >= cutoffTime && !isNaN(date.getTime())
        } catch {
          return false
        }
      })
      .sort((a: WindowDataPoint, b: WindowDataPoint): number => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      )
    
    return windowData
  }
  
  // Calculate message trends from byte stats
  let messagesTrend = 0
  if (byteStats.timestamps?.length > 0 && byteStats.bytes_received?.length > 0) {
    const windowData = getWindowStats(byteStats.timestamps, byteStats.bytes_received)
    
    if (windowData.length >= 2) {
      const firstHalf = windowData.slice(0, Math.floor(windowData.length / 2))
      const secondHalf = windowData.slice(Math.floor(windowData.length / 2))
      
      const firstAvg = firstHalf.reduce((sum: number, item: WindowDataPoint): number => sum + item.value, 0) / firstHalf.length
      const secondAvg = secondHalf.reduce((sum: number, item: WindowDataPoint): number => sum + item.value, 0) / secondHalf.length
      
      messagesTrend = calculateTrend(firstAvg, secondAvg)
    }
  }
  
  // Calculate subscription trends (use current vs previous poll)
  // This is trickier as we need to maintain a history of subscription counts
  const subscriptionsTrend = 0 // Will be calculated from polling history
  
  // Calculate client trends (similar to subscriptions)
  const clientsTrend = 0 // Will be calculated from polling history
  
  return {
    messagesTrend,
    subscriptionsTrend,
    clientsTrend
  }
}

interface VisitorStatsResult {
  fullStats: ByteStats
  windowStats: ByteStats
  selectedWindow: TimeWindow
}

// Enhanced visitor stats computation
const visitorStats = computed((): VisitorStatsResult => {
  const byteStats = stats.value.bytes_stats
  const currentWindow = getCurrentTimeWindow()
  const windowAgo = new Date(Date.now() - currentWindow.hours * 60 * 60 * 1000)
  
  const windowStats: ByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  }

  if (byteStats.timestamps?.length) {
    byteStats.timestamps.forEach((ts: string, i: number): void => {
      let timestampDate: Date
      
      try {
        if (ts.includes('T')) {
          timestampDate = ts.endsWith('Z') || ts.includes('+') || (ts.match(/:/g) || []).length > 2
            ? new Date(ts)
            : new Date(ts + 'Z')
        } else {
          timestampDate = new Date(ts + ' UTC')
        }
        
        if (isNaN(timestampDate.getTime())) {
          console.warn(`Invalid timestamp: ${ts}`)
          return
        }
        
        if (timestampDate >= windowAgo && 
            i < byteStats.bytes_received.length && 
            i < byteStats.bytes_sent.length) {
          windowStats.timestamps.push(ts)
          windowStats.bytes_received.push(byteStats.bytes_received[i])
          windowStats.bytes_sent.push(byteStats.bytes_sent[i])
        }
      } catch (error) {
        console.warn(`Error parsing timestamp ${ts}:`, error)
      }
    })
  }
  
  return {
    fullStats: byteStats,
    windowStats,
    selectedWindow: currentWindow
  }
})

// Computed trends based on window
const windowBasedTrends = computed(() => {
  return calculateWindowBasedTrends()
})

// Watch for time window changes and recalculate
watch(selectedTimeWindow, () => {
  // Trends will be automatically recalculated via computed property
  console.log(`Time window changed to: ${getCurrentTimeWindow().label}`)
})

interface PollingHistoryEntry {
  timestamp: Date
  stats: Stats
}

interface HistoryBasedTrends {
  subscriptionsTrend: number
  clientsTrend: number
}

// Maintain polling history for subscription/client trends
const pollingHistory = ref<PollingHistoryEntry[]>([])
const MAX_HISTORY_SIZE = 100

const addToHistory = (newStats: Stats): void => {
  pollingHistory.value.push({
    timestamp: new Date(),
    stats: { ...newStats }
  })
  
  // Keep only recent history
  if (pollingHistory.value.length > MAX_HISTORY_SIZE) {
    pollingHistory.value = pollingHistory.value.slice(-MAX_HISTORY_SIZE)
  }
}

// Calculate trends from polling history
const calculateHistoryBasedTrends = (): HistoryBasedTrends => {
  const currentWindow = getCurrentTimeWindow()
  const cutoffTime = new Date(Date.now() - currentWindow.hours * 60 * 60 * 1000)
  
  const windowHistory = pollingHistory.value.filter((h: PollingHistoryEntry): boolean => h.timestamp >= cutoffTime)
  
  if (windowHistory.length < 2) return { subscriptionsTrend: 0, clientsTrend: 0 }
  
  const midPoint = Math.floor(windowHistory.length / 2)
  const firstHalf = windowHistory.slice(0, midPoint)
  const secondHalf = windowHistory.slice(midPoint)
  
  // Calculate averages for each half
  const firstSubsAvg = firstHalf.reduce((sum: number, h: PollingHistoryEntry): number => sum + h.stats.total_subscriptions, 0) / firstHalf.length
  const secondSubsAvg = secondHalf.reduce((sum: number, h: PollingHistoryEntry): number => sum + h.stats.total_subscriptions, 0) / secondHalf.length
  
  const firstClientsAvg = firstHalf.reduce((sum: number, h: PollingHistoryEntry): number => sum + h.stats.total_connected_clients, 0) / firstHalf.length
  const secondClientsAvg = secondHalf.reduce((sum: number, h: PollingHistoryEntry): number => sum + h.stats.total_connected_clients, 0) / secondHalf.length
  
  return {
    subscriptionsTrend: calculateTrend(firstSubsAvg, secondSubsAvg),
    clientsTrend: calculateTrend(firstClientsAvg, secondClientsAvg)
  }
}

// Combined trends computation
const allTrends = computed(() => {
  const windowTrends = windowBasedTrends.value
  const historyTrends = calculateHistoryBasedTrends()
  
  return {
    messagesTrend: windowTrends.messagesTrend,
    subscriptionsTrend: historyTrends.subscriptionsTrend,
    clientsTrend: historyTrends.clientsTrend
  }
})

// Fetch stats function
const fetchStats = async (): Promise<void> => {
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
      const errorData = await response.json().catch((): Record<string, unknown> => ({}))
      console.error('API Error:', response.status, errorData)

      switch (response.status) {
        case 401:
          throw new Error('Session expired. Please login again.')
        case 403:
          throw new Error('You do not have permission to view these stats.')
        case 429:
          throw new Error('Too many requests. Please slow down.')
        default:
          throw new Error(errorData.message as string || `API request failed with status ${response.status}`)
      }
    }

    const data = await response.json()
    const newStats: Stats = {
      ...defaultStats,
      ...data,
      mqtt_connected: data.mqtt_connected || false
    }

    stats.value = newStats
    addToHistory(newStats)

    if (!data.mqtt_connected && data.connection_error) {
      error.value = data.connection_error
    } else {
      error.value = null
    }

  } catch (err) {
    console.error('Fetch error:', err)
    error.value = err instanceof Error ? err.message : 'Failed to load dashboard data'
    stats.value = { ...defaultStats }
  } finally {
    isLoading.value = false
  }
}

// Lifecycle hooks
onMounted((): void => {
  fetchStats()
  intervalId = window.setInterval(fetchStats, 30000) // Increased to 30 seconds
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
    <!-- Time Window Selector -->
    <v-card class="mb-4" elevation="0" variant="outlined">
      <v-card-text class="py-3">
        <div class="d-flex align-items-center justify-space-between flex-wrap">
          <h6 class="text-h6 mb-0">Dashboard View</h6>
          <v-chip-group
            v-model="selectedTimeWindow"
            color="primary"
            selected-class="text-primary"
            mandatory
          >
            <v-chip
              v-for="window in timeWindows"
              :key="window.value"
              :value="window.value"
              variant="outlined"
              size="small"
            >
              {{ window.label }}
            </v-chip>
          </v-chip-group>
        </div>
        <v-divider class="mt-3 mb-2"></v-divider>
        <div class="text-caption text-medium-emphasis">
          Showing trends and data for the last {{ getCurrentTimeWindow().label.toLowerCase() }}
          • Updates every 30 seconds
        </div>
      </v-card-text>
    </v-card>

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

    <!-- MQTT Stats Cards with Window-based Trends -->
    <WidgetFive 
      :total-messages-received="stats.total_messages_received"
      :total-connected-clients="stats.total_connected_clients" 
      :total-subscriptions="stats.total_subscriptions"
      :retained-messages="stats.retained_messages" 
      :messages-trend="allTrends.messagesTrend"
      :subscriptions-trend="allTrends.subscriptionsTrend"
      :clients-trend="allTrends.clientsTrend"
      :loading="isLoading"
    />

    <v-row>
      <!-- Message Rates Chart with Selected Window -->
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