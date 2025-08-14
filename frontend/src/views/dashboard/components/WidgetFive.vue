<!-- Copyright (c) 2025 BunkerM -->
<script setup lang="ts">
import { computed } from 'vue';
import { RiseOutlined, FallOutlined } from '@ant-design/icons-vue';

interface Props {
  totalMessagesReceived: string;
  totalConnectedClients: number;
  totalSubscriptions: number;
  retainedMessages: number;
  messagesTrend?: number;
  subscriptionsTrend?: number;
  clientsTrend?: number; // Added clientsTrend prop
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  totalMessagesReceived: "0",
  totalConnectedClients: 0,
  totalSubscriptions: 0,
  retainedMessages: 0,
  messagesTrend: 0,
  subscriptionsTrend: 0,
  clientsTrend: 0,
  loading: false
});

const formatLocalNumber = (num: number): string => {
  return new Intl.NumberFormat().format(num);
};

const cards = computed(() => [
  {
    name: 'Messages Received',
    value: props.totalMessagesReceived,
    trend: props.messagesTrend,
    text: getTrendDescription('messages', props.messagesTrend),
    icon: getTrendIcon(props.messagesTrend),
    showTrend: true
  },
  {
    name: 'Connected Clients',
    value: formatLocalNumber(props.totalConnectedClients),
    trend: props.clientsTrend,
    text: getTrendDescription('clients', props.clientsTrend),
    icon: getTrendIcon(props.clientsTrend),
    showTrend: true
  },
  {
    name: 'Active Subscriptions',
    value: formatLocalNumber(props.totalSubscriptions),
    trend: props.subscriptionsTrend,
    text: getTrendDescription('subscriptions', props.subscriptionsTrend),
    icon: getTrendIcon(props.subscriptionsTrend),
    showTrend: true
  },
  {
    name: 'Retained Messages',
    value: formatLocalNumber(props.retainedMessages),
    trend: null,
    text: 'retained messages in broker',
    icon: RiseOutlined,
    showTrend: false
  }
]);

const getTrendIcon = (trend: number | null) => {
  if (trend === null || trend === 0) return RiseOutlined;
  return trend > 0 ? RiseOutlined : FallOutlined;
};

const getColor = (trend: number | null) => {
  if (trend === null) return 'primary';
  if (trend === 0) return 'surface-variant';
  return trend > 0 ? 'success' : 'error';
};

const getTrendText = (trend: number | null) => {
  if (trend === null) return '';
  if (trend === 0) return '0%';
  const sign = trend > 0 ? '+' : '';
  return `${sign}${trend}%`;
};

const getTrendDescription = (type: string, trend: number | null): string => {
  if (trend === null) return `current ${type} count`;
  
  if (trend === 0) return `no change in ${type}`;
  
  const direction = trend > 0 ? 'increase' : 'decrease';
  const magnitude = Math.abs(trend);
  
  if (magnitude >= 50) {
    return `significant ${direction} in ${type}`;
  } else if (magnitude >= 20) {
    return `moderate ${direction} in ${type}`;
  } else {
    return `slight ${direction} in ${type}`;
  }
};

const getTrendTooltip = (trend: number | null, type: string): string => {
  if (trend === null) return `${type} count (no trend data)`;
  
  if (trend === 0) return `${type} unchanged from previous period`;
  
  const direction = trend > 0 ? 'increased' : 'decreased';
  return `${type} ${direction} by ${Math.abs(trend)}% from previous period`;
};
</script>

<template>
  <v-row class="my-0">
    <v-col 
      cols="12" 
      sm="6" 
      md="3" 
      v-for="(card, i) in cards" 
      :key="i"
    >
      <v-card elevation="0" :loading="props.loading">
        <v-card variant="outlined">
          <v-card-text>
            <div class="d-flex align-items-center justify-space-between">
              <div class="flex-grow-1">
                <h6 class="text-h6 text-lightText mb-1">{{ card.name }}</h6>
                <h4 class="text-h4 d-flex align-center mb-0 flex-wrap">
                  <span>{{ card.value }}</span>
                  <v-tooltip
                    v-if="card.showTrend && card.trend !== null"
                    :text="getTrendTooltip(card.trend, card.name.toLowerCase())"
                    location="top"
                  >
                    <template v-slot:activator="{ props: tooltipProps }">
                      <v-chip 
                        v-bind="tooltipProps"
                        :color="getColor(card.trend)" 
                        :variant="card.trend === 0 ? 'tonal' : 'flat'"
                        :border="card.trend === 0 ? `${getColor(card.trend)} solid thin opacity-50` : 'none'" 
                        class="ml-2" 
                        size="small" 
                        label
                      >
                        <template v-slot:prepend v-if="card.trend !== 0">
                          <component 
                            :is="card.icon" 
                            :style="{ fontSize: '12px' }" 
                            :class="'mr-1 text-' + getColor(card.trend)" 
                          />
                        </template>
                        {{ getTrendText(card.trend) }}
                      </v-chip>
                    </template>
                  </v-tooltip>
                  
                  <!-- Show loading indicator in trend position if loading -->
                  <v-skeleton-loader
                    v-else-if="props.loading && card.showTrend"
                    type="chip"
                    class="ml-2"
                    width="60"
                    height="24"
                  ></v-skeleton-loader>
                </h4>
                <span class="text-lightText text-caption pt-3 d-block">
                  {{ card.text }}
                </span>
              </div>
              
              <!-- Optional icon or indicator on the right side -->
              <div class="ml-3 d-flex align-center" v-if="!props.loading">
                <div 
                  :class="`trend-indicator trend-indicator--${getColor(card.trend)}`"
                  v-if="card.showTrend && card.trend !== null && card.trend !== 0"
                >
                  <component 
                    :is="card.icon" 
                    :style="{ fontSize: '16px' }" 
                  />
                </div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-card>
    </v-col>
  </v-row>
</template>

<style scoped>
.trend-indicator {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.6;
  transition: opacity 0.2s ease;
}

.trend-indicator:hover {
  opacity: 1;
}

.trend-indicator--success {
  background-color: rgba(76, 175, 80, 0.1);
  color: #4caf50;
}

.trend-indicator--error {
  background-color: rgba(244, 67, 54, 0.1);
  color: #f44336;
}

.trend-indicator--primary {
  background-color: rgba(33, 150, 243, 0.1);
  color: #2196f3;
}

.trend-indicator--surface-variant {
  background-color: rgba(158, 158, 158, 0.1);
  color: #9e9e9e;
}
</style>