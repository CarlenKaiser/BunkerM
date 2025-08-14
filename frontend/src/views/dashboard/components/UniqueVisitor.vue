/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
<script setup lang="ts">
import { computed, ref } from 'vue';
import { getInfo, getdarkPrimary, getLightBorder, getSecondary } from './UpdateColors';

interface ByteStats {
  timestamps: string[];
  bytes_received: number[];
  bytes_sent: number[];
}

interface TimestampedStats {
  timestamp: string;
  total_messages_received: string;
  total_subscriptions: number;
  retained_messages: number;
  total_connected_clients: number;
}

interface VisitorStats {
  fullStats: ByteStats;
  sixHourStats: ByteStats;
  timestampedMetrics?: TimestampedStats[];
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
    },
    timestampedMetrics: []
  })
});

// Helper function to format bytes
const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// Helper function to format time for display
const formatTime = (timestamp: string): string => {
  try {
    // Handle both ISO format and legacy format
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      // Try parsing legacy format if ISO fails
      const legacyDate = new Date(timestamp.replace(' ', 'T'));
      return legacyDate.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    }
    return date.toLocaleTimeString([], {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  } catch (e) {
    console.warn('Failed to parse timestamp:', timestamp, e);
    return timestamp;
  }
};

// Helper function to format date for display
const formatDate = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      // Try parsing legacy format if ISO fails
      const legacyDate = new Date(timestamp.replace(' ', 'T'));
      return legacyDate.toLocaleDateString('en-US', {
        month: 'short',
        day: '2-digit'
      });
    }
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: '2-digit'
    });
  } catch (e) {
    console.warn('Failed to parse timestamp:', timestamp, e);
    return timestamp;
  }
};

// Helper function to validate and clean timestamps
const validateTimestamp = (timestamp: string): boolean => {
  try {
    const date = new Date(timestamp);
    return !isNaN(date.getTime());
  } catch {
    return false;
  }
};

// Helper function to filter data points by time range for daily view
const filterDataByTimeRange = (data: ByteStats, hours: number): ByteStats => {
  const cutoffTime = new Date();
  cutoffTime.setHours(cutoffTime.getHours() - hours);

  const filteredData: ByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  };

  data.timestamps.forEach((timestamp: string, index: number) => {
    if (!validateTimestamp(timestamp)) {
      return; // Skip invalid timestamps
    }

    const timestampDate = new Date(timestamp);
    if (timestampDate >= cutoffTime && 
        index < data.bytes_received.length && 
        index < data.bytes_sent.length) {
      filteredData.timestamps.push(timestamp);
      filteredData.bytes_received.push(data.bytes_received[index]);
      filteredData.bytes_sent.push(data.bytes_sent[index]);
    }
  });

  return filteredData;
};

// Helper function to filter timestamps for x-axis labels (15-minute intervals)
const filterTimestampsForDisplay = (timestamps: string[], intervalMinutes: number = 15): string[] => {
  if (timestamps.length === 0) return [];
  
  const filtered: string[] = [];
  const intervalMs = intervalMinutes * 60 * 1000;
  let lastTimestamp = 0;

  timestamps.forEach((ts: string, index: number) => {
    if (!validateTimestamp(ts)) {
      filtered.push('');
      return;
    }

    const currentTime = new Date(ts).getTime();
    if (index === 0 || (currentTime - lastTimestamp) >= intervalMs) {
      filtered.push(ts);
      lastTimestamp = currentTime;
    } else {
      filtered.push('');
    }
  });

  return filtered;
};

// Helper function to filter timestamps for daily view
const filterTimestampsForDaily = (timestamps: string[]): string[] => {
  if (timestamps.length === 0) return [];
  
  const filtered: string[] = [];
  let lastDate = '';

  timestamps.forEach((ts: string) => {
    if (!validateTimestamp(ts)) {
      filtered.push('');
      return;
    }

    const currentDate = formatDate(ts);
    if (currentDate !== lastDate) {
      filtered.push(ts);
      lastDate = currentDate;
    } else {
      filtered.push('');
    }
  });

  return filtered;
};

// Enhanced data validation
const validateByteStats = (data: ByteStats): ByteStats => {
  const validData: ByteStats = {
    timestamps: [],
    bytes_received: [],
    bytes_sent: []
  };

  if (!data || !Array.isArray(data.timestamps)) {
    return validData;
  }

  data.timestamps.forEach((timestamp: string, index: number) => {
    if (validateTimestamp(timestamp) && 
        index < data.bytes_received.length && 
        index < data.bytes_sent.length &&
        typeof data.bytes_received[index] === 'number' &&
        typeof data.bytes_sent[index] === 'number') {
      validData.timestamps.push(timestamp);
      validData.bytes_received.push(data.bytes_received[index]);
      validData.bytes_sent.push(data.bytes_sent[index]);
    }
  });

  return validData;
};

// Last 6 hours view chart options
const chartOptions1 = computed(() => {
  const sixHourData = validateByteStats(props.stats.sixHourStats);
  const filteredTimestamps = filterTimestampsForDisplay(sixHourData.timestamps, 15);
  
  return {
    chart: {
      type: 'area',
      height: 450,
      fontFamily: `inherit`,
      foreColor: getSecondary.value,
      toolbar: false
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
      categories: filteredTimestamps.map((ts: string) => ts ? formatTime(ts) : ''),
      axisBorder: {
        show: true,
        color: getLightBorder.value
      },
      axisTicks: {
        color: getLightBorder.value
      },
      labels: {
        rotateAlways: true,
        rotate: -45,
        style: {
          fontSize: '12px'
        },
        formatter: function (value: string): string {
          return value || '';  // Hide empty labels
        }
      },
      tickAmount: Math.min(8, filteredTimestamps.filter((ts: string) => ts).length)
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
      y: {
        formatter: (value: number) => formatBytes(value)
      },
      x: {
        formatter: function(value: any, { dataPointIndex }: any) {
          const timestamp = filteredTimestamps[dataPointIndex];
          return timestamp ? formatTime(timestamp) : '';
        }
      }
    }
  };
});

// Daily view chart options
const chartOptions2 = computed(() => {
  const sevenDayData = filterDataByTimeRange(validateByteStats(props.stats.fullStats), 24 * 7);
  const filteredTimestamps = filterTimestampsForDaily(sevenDayData.timestamps);
  
  return {
    chart: {
      type: 'area',
      height: 450,
      fontFamily: `inherit`,
      foreColor: getSecondary.value,
      toolbar: false
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
      categories: filteredTimestamps.map((ts: string) => ts ? formatDate(ts) : ''),
      axisBorder: {
        show: true,
        color: getLightBorder.value
      },
      axisTicks: {
        color: getLightBorder.value
      },
      labels: {
        rotateAlways: true,
        rotate: -45,
        style: {
          fontSize: '12px'
        },
        formatter: function (value: string): string {
          return value || '';  // Hide empty labels
        }
      },
      tickAmount: 7
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
      y: {
        formatter: (value: number) => formatBytes(value)
      },
      x: {
        formatter: function(value: any, { dataPointIndex }: any) {
          const timestamp = filteredTimestamps[dataPointIndex];
          return timestamp ? formatDate(timestamp) : '';
        }
      }
    }
  };
});

// Chart series data for 6-hour view
const sixHourSeriesData = computed(() => {
  const sixHourData = validateByteStats(props.stats.sixHourStats);
  return [
    {
      name: 'Bytes Received',
      data: sixHourData.bytes_received || []
    },
    {
      name: 'Bytes Sent',
      data: sixHourData.bytes_sent || []
    }
  ];
});

// Chart series data for daily view
const dailySeriesData = computed(() => {
  const sevenDayData = filterDataByTimeRange(validateByteStats(props.stats.fullStats), 24 * 7);
  return [
    {
      name: 'Bytes Received',
      data: sevenDayData.bytes_received || []
    },
    {
      name: 'Bytes Sent',
      data: sevenDayData.bytes_sent || []
    }
  ];
});

// Computed property for debugging timestamp data
const timestampDebugInfo = computed(() => {
    return {
      sixHourTimestamps: props.stats.sixHourStats.timestamps.length,
      fullStatsTimestamps: props.stats.fullStats.timestamps.length,
      timestampedMetrics: props.stats.timestampedMetrics?.length || 0,
      firstSixHourTimestamp: props.stats.sixHourStats.timestamps[0] || 'N/A',
      lastSixHourTimestamp: props.stats.sixHourStats.timestamps[props.stats.sixHourStats.timestamps.length - 1] || 'N/A'
    };
});

const tab = ref('one');
</script>

<template>
  <v-card class="title-card" variant="text">
    <v-card-item class="pb-2 px-0 pt-0">
      <div class="d-flex justify-space-between">
        <v-card-title class="text-h5">Byte Transfer Rate (15min intervals)</v-card-title>
        <div class="d-flex flex-wrap">
          <v-tabs v-model="tab" color="primary" class="tabBtn" density="compact" hide-slider>
            <v-tab value="one" class="mr-1" variant="outlined" rounded="md">Last 6h</v-tab>
            <v-tab value="two" variant="outlined" rounded="md">Daily</v-tab>
          </v-tabs>
        </div>
      </div>
    </v-card-item>

    <!-- Debug info for development -->
    <div class="ma-2 pa-2 bg-grey-lighten-4 rounded text-caption">
      <strong>Debug Info:</strong><br>
      6h timestamps: {{ timestampDebugInfo.sixHourTimestamps }}<br>
      Full timestamps: {{ timestampDebugInfo.fullStatsTimestamps }}<br>
      Metrics: {{ timestampDebugInfo.timestampedMetrics }}<br>
      First: {{ timestampDebugInfo.firstSixHourTimestamp }}<br>
      Last: {{ timestampDebugInfo.lastSixHourTimestamp }}
    </div>

    <v-card-text class="rounded-md overflow-hidden">
      <v-window v-model="tab">
        <v-window-item value="one">
          <div v-if="sixHourSeriesData[0].data.length === 0" class="text-center pa-4">
            <v-icon size="48" color="grey">mdi-chart-line-variant</v-icon>
            <p class="text-grey mt-2">No data available for the last 6 hours</p>
          </div>
          <apexchart 
            v-else 
            type="area" 
            height="450" 
            :options="chartOptions1" 
            :series="sixHourSeriesData" 
          />
        </v-window-item>
        <v-window-item value="two">
          <div v-if="dailySeriesData[0].data.length === 0" class="text-center pa-4">
            <v-icon size="48" color="grey">mdi-chart-line-variant</v-icon>
            <p class="text-grey mt-2">No data available for the daily view</p>
          </div>
          <apexchart 
            v-else 
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