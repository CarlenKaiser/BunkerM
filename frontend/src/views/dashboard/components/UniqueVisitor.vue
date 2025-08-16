<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import { getInfo, getdarkPrimary, getLightBorder, getSecondary } from './UpdateColors';
import type { ApexOptions } from 'apexcharts';
import { mdiReload } from '@mdi/js';

interface ByteStats {
  timestamps: string[];
  bytes_received: number[];
  bytes_sent: number[];
}

interface VisitorStats {
  fullStats: ByteStats;
  sixHourStats: ByteStats;
}

interface Props {
  stats: VisitorStats;
}

const props = withDefaults(defineProps<Props>(), {
  stats: () => ({
    fullStats: {
      timestamps: [],
      bytes_received: [],
      bytes_sent: []
    },
    sixHourStats: {
      timestamps: [],
      bytes_received: [],
      bytes_sent: []
    }
  })
});

// Emit events for refresh functionality
const emit = defineEmits<{
  refresh: []
}>();

// Enhanced formatBytes function with proper typing
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'] as const;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Enhanced formatTime function with proper typing
const formatTime = (timestamp: string | number): string => {
  try {
    const date = typeof timestamp === 'string' 
      ? timestamp.includes('T') 
        ? new Date(timestamp) 
        : new Date(timestamp + 'Z')
      : new Date(timestamp);
      
    if (isNaN(date.getTime())) return typeof timestamp === 'string' ? timestamp : timestamp.toString();
    
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    return typeof timestamp === 'string' ? timestamp : timestamp.toString();
  }
};

// Helper function to filter data points by time range for daily view
const filterDataByTimeRange = (data: ByteStats, hours: number): ByteStats => {
  const cutoffTime = new Date();
  cutoffTime.setHours(cutoffTime.getHours() - hours);

  const filteredIndexes = data.timestamps
    .map((timestamp: string, index: number) => ({ timestamp, index }))
    .filter(({ timestamp }) => new Date(timestamp) >= cutoffTime)
    .map(({ index }) => index);

  return {
    timestamps: filteredIndexes.map((i: number) => data.timestamps[i]),
    bytes_received: filteredIndexes.map((i: number) => data.bytes_received[i]),
    bytes_sent: filteredIndexes.map((i: number) => data.bytes_sent[i])
  };
};

// Last 6 hours view chart options with proper typing
const chartOptions1 = computed((): ApexOptions => {
  const dataLength = sixHourSeriesData.value[0]?.data.length || 0
  return {
    chart: {
      type: 'area',
      height: 450,
      fontFamily: 'inherit',
      foreColor: getSecondary.value,
      toolbar: {
        show: false
      }
    },
    colors: [getInfo.value, getdarkPrimary.value],
    dataLabels: {
      enabled: false
    },
    stroke: {
      curve: 'smooth',
      width: 2
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.7,
        opacityTo: 0.4,
        stops: [0, 100]
      }
    },
    grid: {
      borderColor: getLightBorder.value,
      xaxis: {
        lines: {
          show: true
        }
      }
    },
    xaxis: {
      type: 'datetime',
      tickPlacement: 'on',
      tickAmount: dataLength, 
      labels: {
        rotateAlways: true,
        rotate: -45,
        style: {
          fontSize: '12px'
        },
        formatter: function (value: string, timestamp?: number): string {
          if (!timestamp) return '';
          return formatTime(new Date(timestamp).toISOString());
        }
      },
      axisBorder: {
        show: true,
        color: getLightBorder.value
      },
      axisTicks: {
        color: getLightBorder.value
      },
    },
    yaxis: {
      labels: {
        formatter: (value: number) => formatBytes(value)
      }
    },
    legend: {
      show: true,
      position: 'top'
    },
    tooltip: {
      theme: 'dark',
      x: {
        formatter: function (val: number): string {
          return formatTime(val);
        }
      },
      y: {
        formatter: (value: number) => formatBytes(value)
      }
    }
  };
});

// Daily view chart options with proper typing
const chartOptions2 = computed((): ApexOptions => {
  const dataLength = dailySeriesData.value[0]?.data.length || 0;
  return {
    chart: {
      type: 'area',
      height: 450,
      fontFamily: 'inherit',
      foreColor: getSecondary.value,
      toolbar: {
        show: false
      }
    },
    colors: [getInfo.value, getdarkPrimary.value],
    dataLabels: {
      enabled: false
    },
    stroke: {
      curve: 'smooth',
      width: 2
    },
    fill: {
      type: 'gradient',
      gradient: {
        shadeIntensity: 1,
        opacityFrom: 0.7,
        opacityTo: 0.4,
        stops: [0, 100]
      }
    },
    grid: {
      borderColor: getLightBorder.value,
      xaxis: {
        lines: {
          show: true
        }
      }
    },
    xaxis: {
      type: 'datetime',
      tickPlacement: 'on',
      tickAmount: dataLength,
      labels: {
        rotateAlways: true,
        rotate: -45,
        style: {
          fontSize: '12px'
        },
        formatter: function (value: string, timestamp?: number): string {
          if (!timestamp) return '';
          return formatTime(new Date(timestamp).toISOString());
        }
      },
      axisBorder: {
        show: true,
        color: getLightBorder.value
      },
      axisTicks: {
        color: getLightBorder.value
      }
    },
    yaxis: {
      labels: {
        formatter: (value: number) => formatBytes(value)
      }
    },
    legend: {
      show: true,
      position: 'top'
    },
    tooltip: {
      theme: 'dark',
      x: {
        formatter: function (val: number): string {
          return formatTime(val);
        }
      },
      y: {
        formatter: (value: number) => formatBytes(value)
      }
    }
  };
});

// Series data with proper typing
interface SeriesDataPoint {
  x: number; 
  y: number;
}

interface SeriesData {
  name: string;
  data: SeriesDataPoint[];
}

const sixHourSeriesData = computed((): SeriesData[] => {
  const sixHourData = props.stats.sixHourStats;
  return [
    {
      name: 'Bytes Received',
      data: sixHourData.timestamps.map((ts: string, i: number) => ({
        x: new Date(ts).getTime(), // Convert string timestamp to number
        y: sixHourData.bytes_received[i] || 0
      }))
    },
    {
      name: 'Bytes Sent',
      data: sixHourData.timestamps.map((ts: string, i: number) => ({
        x: new Date(ts).getTime(), // Convert string timestamp to number
        y: sixHourData.bytes_sent[i] || 0
      }))
    }
  ];
});

const dailySeriesData = computed((): SeriesData[] => {
  const oneDayData = filterDataByTimeRange(props.stats.fullStats, 24);
  return [
    {
      name: 'Bytes Received',
      data: oneDayData.timestamps.map((ts: string, i: number) => ({
        x: new Date(ts).getTime(), // Convert string timestamp to number
        y: oneDayData.bytes_received[i] || 0
      }))
    },
    {
      name: 'Bytes Sent',
      data: oneDayData.timestamps.map((ts: string, i: number) => ({
        x: new Date(ts).getTime(), // Convert string timestamp to number
        y: oneDayData.bytes_sent[i] || 0
      }))
    }
  ];
});

// State for tabs and refresh functionality
const tab = ref('one');
const isLoading = ref(false);
const autoRefresh = ref(true);
const refreshInterval = ref<number | null>(null);

// Refresh functionality
const handleRefresh = () => {
  isLoading.value = true;
  emit('refresh');
  // Simulate loading state (parent component should handle actual loading)
  setTimeout(() => {
    isLoading.value = false;
  }, 1000);
};

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value;
  if (autoRefresh.value) {
    refreshInterval.value = window.setInterval(handleRefresh, 5000);
  } else if (refreshInterval.value !== null) {
    clearInterval(refreshInterval.value);
    refreshInterval.value = null;
  }
};

// Setup auto-refresh on mount
onMounted(() => {
  if (autoRefresh.value) {
    refreshInterval.value = window.setInterval(handleRefresh, 5000);
  }
});

// Cleanup on unmount
onUnmounted(() => {
  if (refreshInterval.value !== null) {
    clearInterval(refreshInterval.value);
    refreshInterval.value = null;
  }
});
</script>

<template>
  <v-card class="title-card" variant="text">
    <v-card-item class="pb-2 px-0 pt-0">
      <div class="d-flex justify-space-between align-center">
        <v-card-title class="text-h5">Byte Transfer Rate (15min intervals)</v-card-title>
        <div class="d-flex align-center">
          <!-- Tab buttons -->
          <v-tabs v-model="tab" color="primary" class="tabBtn" density="compact" hide-slider>
            <v-tab value="one" class="mr-1" variant="outlined" rounded="md">Last 6h</v-tab>
            <v-tab value="two" class="mr-2" variant="outlined" rounded="md">Daily</v-tab>
          </v-tabs>
          
          <!-- Refresh controls -->
          <v-btn
            :color="autoRefresh ? 'primary' : 'default'"
            variant="outlined"
            size="small"
            class="ml-2"
            @click="toggleAutoRefresh"
            :title="autoRefresh ? 'Auto-refresh enabled' : 'Auto-refresh disabled'"
          >
            <v-icon :icon="mdiReload" />
            <span class="ml-1">{{ autoRefresh ? 'Auto' : 'Manual' }}</span>
          </v-btn>
          
          <v-btn
            color="primary"
            variant="outlined"
            size="small"
            class="ml-2"
            @click="handleRefresh"
            :loading="isLoading"
            :disabled="isLoading"
          >
            <v-icon :icon="mdiReload" />
            <span class="ml-1">Refresh</span>
          </v-btn>
        </div>
      </div>
    </v-card-item>
    <v-card-text class="rounded-md overflow-hidden">
      <v-window v-model="tab">
        <v-window-item value="one">
          <apexchart 
            type="area" 
            height="450" 
            :options="chartOptions1" 
            :series="sixHourSeriesData" 
          />
        </v-window-item>
        <v-window-item value="two">
          <apexchart 
            type="area" 
            height="450" 
            :options="chartOptions2" 
            :series="dailySeriesData" 
          />
        </v-window-item>
      </v-window>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.title-card {
  margin-bottom: 24px;
}
.tabBtn {
  margin-top: 8px;
}
</style>