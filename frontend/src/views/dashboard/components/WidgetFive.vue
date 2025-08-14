<!-- Copyright (c) 2025 BunkerM -->
<script setup lang="ts">
import { computed } from 'vue';
import { RiseOutlined, FallOutlined } from '@ant-design/icons-vue';

interface Props {
  totalMessagesReceived: string; // Changed to string to match backend format
  totalConnectedClients: number;
  totalSubscriptions: number;
  retainedMessages: number;
  messagesTrend?: number;
  subscriptionsTrend?: number;
  loading?: boolean; // Added loading prop
}

const props = withDefaults(defineProps<Props>(), {
  totalMessagesReceived: "0",
  totalConnectedClients: 0,
  totalSubscriptions: 0,
  retainedMessages: 0,
  messagesTrend: 0,
  subscriptionsTrend: 0,
  loading: false
});

// Remove formatNumber since backend already formats numbers
// Keep only for local formatting if needed
const formatLocalNumber = (num: number): string => {
  return new Intl.NumberFormat().format(num);
};

const cards = computed(() => [
  {
    name: 'Messages Received',
    value: props.totalMessagesReceived,
    trend: props.messagesTrend,
    text: 'messages from last period',
    icon: props.messagesTrend >= 0 ? RiseOutlined : FallOutlined
  },
  {
    name: 'Connected Clients',
    value: formatLocalNumber(props.totalConnectedClients),
    trend: null, // No trend for clients unless you track it separately
    text: 'total connected clients',
    icon: RiseOutlined
  },
  {
    name: 'Active Subscriptions',
    value: formatLocalNumber(props.totalSubscriptions),
    trend: props.subscriptionsTrend,
    text: 'subscriptions from last check',
    icon: props.subscriptionsTrend >= 0 ? RiseOutlined : FallOutlined
  },
  {
    name: 'Retained Messages',
    value: formatLocalNumber(props.retainedMessages),
    trend: null, // No trend for retained messages
    text: 'retained messages in broker',
    icon: RiseOutlined
  }
]);

const getColor = (trend: number | null) => {
  if (trend === null) return 'primary';
  return trend >= 0 ? 'success' : 'error';
};

const getTrendText = (trend: number | null) => {
  if (trend === null) return 'Current';
  return `${Math.abs(trend)}%`;
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
              <div>
                <h6 class="text-h6 text-lightText mb-1">{{ card.name }}</h6>
                <h4 class="text-h4 d-flex align-center mb-0">
                  {{ card.value }}
                  <v-chip 
                    v-if="card.trend !== null"
                    :color="getColor(card.trend)" 
                    :border="`${getColor(card.trend)} solid thin opacity-50`" 
                    class="ml-2" 
                    size="small" 
                    label
                  >
                    <template v-slot:prepend>
                      <component 
                        :is="card.icon" 
                        :style="{ fontSize: '12px' }" 
                        :class="'mr-1 text-' + getColor(card.trend)" 
                      />
                    </template>
                    {{ getTrendText(card.trend) }}
                  </v-chip>
                </h4>
                <span class="text-lightText text-caption pt-5 d-block">
                  {{ card.text }}
                </span>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-card>
    </v-col>
  </v-row>
</template>