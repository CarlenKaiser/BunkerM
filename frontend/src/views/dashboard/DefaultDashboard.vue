<!-- Copyright (c) 2025 BunkerM -->

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue';
import WidgetFive from './components/WidgetFive.vue';
import UniqueVisitor from './components/UniqueVisitor.vue';
import { generateNonce } from '../../utils/security';
import { getRuntimeConfig } from '@/config/runtime';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const config = getRuntimeConfig();

// API configuration
const API_BASE_URL = config.MONITOR_API_URL;

interface ByteStats {
  timestamps: string[];
  bytes_received: number[];
  bytes_sent: number[];
}

interface Stats {
  total_messages_received: string; // Changed to string to match format_number output
  total_subscriptions: number;
  retained_messages: number;
  total_connected_clients: number;
  bytes_stats: ByteStats;
  daily_message_stats: {
    dates: string[];
    counts: number[];
  };
  mqtt_connected: boolean;
  connection_error?: string;
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
};

const stats = ref<Stats>({ ...defaultStats });
const error = ref<string | null>(null);
const loading = ref(false);
let intervalId: number | null = null;

const fetchStats = async () => {
  if (loading.value) return;
  
  loading.value = true;
  error.value = null;

  try {
    const timestamp = Date.now() / 1000;
    const nonce = generateNonce();

    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Content-Type': 'application/json'
    };

    // Add auth header if using token-based auth
    if (authStore.token) {
      headers['Authorization'] = `Bearer ${authStore.token}`;
    }

    const response = await fetch(
      `${API_BASE_URL}/stats?nonce=${nonce}&timestamp=${timestamp}`,
      {
        method: 'GET',
        headers,
        credentials: 'include' // Changed to 'include' if using cookies
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('API Error:', response.status, errorData);

      switch (response.status) {
        case 401:
          throw new Error('Session expired. Please login again.');
        case 403:
          throw new Error('You do not have permission to view these stats.');
        case 429:
          throw new Error('Too many requests. Please slow down.');
        default:
          throw new Error(errorData.message || `API request failed with status ${response.status}`);
      }
    }

    const data = await response.json();
    
    // Transform data if needed to match component expectations
    stats.value = {
      ...defaultStats,
      ...data,
      mqtt_connected: data.mqtt_connected || false
    };

    if (!data.mqtt_connected && data.connection_error) {
      error.value = data.connection_error;
    }

  } catch (err) {
    console.error('Fetch error:', err);
    error.value = err instanceof Error ? err.message : 'Failed to load dashboard data';
    
    // Reset to default stats on error
    stats.value = { ...defaultStats };
  } finally {
    loading.value = false;
  }
};

// Start polling when component mounts
onMounted(() => {
  fetchStats();
  intervalId = window.setInterval(fetchStats, 15000); // 15 seconds
});

// Clean up when component unmounts
onUnmounted(() => {
  if (intervalId) {
    clearInterval(intervalId);
    intervalId = null;
  }
});
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

    <!-- Loading state -->
    <v-progress-linear
      v-if="loading"
      indeterminate
      color="primary"
      class="mb-4"
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
          :byte-stats="stats.bytes_stats" 
          :loading="loading"
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
}

.mb-4 {
  margin-bottom: 1rem;
}
</style>