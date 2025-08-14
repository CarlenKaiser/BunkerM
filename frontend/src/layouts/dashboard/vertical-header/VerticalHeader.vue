/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
<script setup lang="ts">
import { useCustomizerStore } from '../../../stores/customizer';
import { computed } from 'vue';
// icons
import { MenuFoldOutlined, SearchOutlined, GithubOutlined, RedditOutlined, LogoutOutlined, SettingOutlined, MoreOutlined } from '@ant-design/icons-vue';

// dropdown imports
import NotificationDD from './NotificationDD.vue';
import Searchbar from './SearchBarPanel.vue';
import ProfileDD from './ProfileDD.vue';

import { useAuthStore } from '@/stores/auth';
import { useRouter } from 'vue-router';

const customizer = useCustomizerStore();
const authStore = useAuthStore();
const router = useRouter();

// Get current user information from auth store
const currentUser = computed(() => {
  const user = authStore.user;
  console.log('Current user object:', user);
  return user;
});

const userDisplayName = computed(() => {
  if (!currentUser.value) {
    console.log('No current user');
    return '';
  }
  
  try {
    const fullName = [currentUser.value.firstName, currentUser.value.lastName]
      .filter(name => name && typeof name === 'string')
      .join(' ');
    
    console.log('Computed fullName:', fullName);
    return fullName || currentUser.value.email?.split('@')[0] || 'User';
  } catch (error) {
    console.error('Error computing display name:', error);
    return currentUser.value.email?.split('@')[0] || 'User';
  }
});

const userInitials = computed(() => {
  try {
    const name = userDisplayName.value || '';
    console.log('Computing initials for:', name);
    
    const names = name.trim().split(/\s+/);
    if (names.length === 0) return 'U';
    if (names.length === 1) return names[0][0].toUpperCase();
    return (names[0][0] + names[names.length - 1][0]).toUpperCase();
  } catch (error) {
    console.error('Error computing initials:', error);
    return 'U';
  }
});

// Generate a consistent color based on user's name
const avatarColor = computed(() => {
  // Use actual color values instead of names
  const colors = [
    '#4CAF50', // green
    '#2196F3', // blue
    '#F44336', // red
    '#673AB7', // deep-purple
    '#009688', // teal
    '#FF9800', // orange
    '#E91E63', // pink
    '#3F51B5', // indigo
    '#00BCD4', // cyan
    '#FF5722', // deep-orange
    '#795548', // brown
    '#607D8B'  // blue-grey
  ];
  
  const str = userDisplayName.value || 'User';
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = str.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
});
</script>

<template>
  <v-app-bar elevation="0" height="60">
    <v-btn class="hidden-md-and-down text-secondary mr-3" color="darkText" icon rounded="sm" variant="text"
      @click.stop="customizer.SET_MINI_SIDEBAR(!customizer.mini_sidebar)" size="small">
      <MenuFoldOutlined :style="{ fontSize: '26px' }" />
    </v-btn>
    <v-btn class="hidden-lg-and-up text-secondary ms-3" color="darkText" icon rounded="sm" variant="text"
      @click.stop="customizer.SET_SIDEBAR_DRAWER" size="small">
      <MenuFoldOutlined :style="{ fontSize: '16px' }" />
    </v-btn>

    <!-- search mobile -->
    <v-menu :close-on-content-click="false" class="hidden-lg-and-up" offset="10, 0">
      <template v-slot:activator="{ props }">
        <v-btn class="hidden-lg-and-up text-secondary ml-1" color="lightsecondary" icon rounded="sm" variant="flat"
          size="small" v-bind="props">
          <SearchOutlined :style="{ fontSize: '17px' }" />
        </v-btn>
      </template>
      <v-sheet class="search-sheet v-col-12 pa-0" width="320">
        <v-text-field persistent-placeholder placeholder="Search here.." color="primary" variant="solo" hide-details>
          <template v-slot:prepend-inner>
            <SearchOutlined :style="{ fontSize: '17px' }" />
          </template>
        </v-text-field>
      </v-sheet>
    </v-menu>

    <!-- ---------------------------------------------- -->
    <!-- Search part -->
    <!-- ---------------------------------------------- -->
    <v-sheet class="d-none d-lg-block" width="250">
      <Searchbar />
    </v-sheet>

    <!---/Search part -->

    <v-spacer />
    <!-- ---------------------------------------------- -->
    <!---right part -->
    <!-- ---------------------------------------------- -->

    <!-- ---------------------------------------------- -->
    <!-- Github -->
    <!-- ---------------------------------------------- -->
    <v-btn icon class="text-secondary hidden-sm-and-down d-flex" color="darkText" rounded="sm" variant="text"
      href="https://github.com/bunkeriot/BunkerM" target="_blank">
      <GithubOutlined :style="{ fontSize: '26px' }" />
    </v-btn>

    <!-- ---------------------------------------------- -->
    <!-- Notification -->
    <!-- ---------------------------------------------- -->
    <NotificationDD />

    <!-- ---------------------------------------------- -->
    <!-- User Profile Section -->
    <!-- ---------------------------------------------- -->
    <div class="d-flex align-center ml-3" v-if="currentUser">
      <!-- User Info (hidden on mobile) -->
      <div class="d-none d-sm-flex flex-column mr-3 text-right">
        <span class="text-body-2 font-weight-medium text-darkText">
          {{ userDisplayName }}
        </span>
        <span class="text-caption text-secondary">
          {{ currentUser.email }}
        </span>
      </div>
      
      <!-- Initials Avatar -->
      <v-avatar 
          size="36" 
          class="mr-2" 
          :style="{ backgroundColor: avatarColor }"
        >
          <span class="text-white font-weight-bold">
            {{ userInitials }}
          </span>
        </v-avatar>
    </div>

    <!-- ---------------------------------------------- -->
    <!-- Profile Menu -->
    <!-- ---------------------------------------------- -->
    <v-menu :close-on-content-click="false" offset="8, 0">
      <template v-slot:activator="{ props }">
        <v-btn class="profileBtn" variant="text" rounded="sm" v-bind="props">
          <div class="d-flex align-center">
            <MoreOutlined class="v-icon--start" :style="{ fontSize: '26px' }" />
          </div>
        </v-btn>
      </template>
      <v-sheet rounded="md" width="290">
        <ProfileDD />
      </v-sheet>
    </v-menu>

  </v-app-bar>
</template>

<style scoped>
.profileBtn {
  min-width: auto;
}

/* Ensure avatar visibility */
.v-avatar {
  box-shadow: 0 0 0 1px rgba(0,0,0,0.1) !important;
}

.v-avatar span {
  font-size: 14px !important;
  text-shadow: 0 0 1px rgba(0,0,0,0.3);
}
</style>