<script setup lang="ts">
import { computed, ref } from 'vue';
import { getInfo, getdarkPrimary, getLightBorder, getSecondary } from './UpdateColors';
import type { ApexOptions } from 'apexcharts';

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

// Define type for tooltip formatter context
interface TooltipFormatterContext {
  series: number[][];
  seriesIndex: number;
  dataPointIndex: number;
  w: {
    config: {
      series: Array<{
        data: Array<{ x: number; y: number }>; // x is number (timestamp in ms)
      }>;
    };
    globals: {
      categoryLabels: string[];
    };
  };
}

// Last 6 hours view chart options with proper typing
const chartOptions1 = computed((): ApexOptions => {
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
      tickAmount: 8
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
        formatter: function (val: number, opts?: { seriesIndex: number, dataPointIndex: number, w: any }): string {
          if (!opts) return '';
          const timestamp = opts.w.config.series[0].data[opts.dataPointIndex]?.x || 
                          opts.w.globals.categoryLabels[opts.dataPointIndex];
          return formatTime(new Date(timestamp).toISOString());
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
      tickAmount: 12
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