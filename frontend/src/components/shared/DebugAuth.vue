<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { auth } from '@/firebase';
import { getRedirectResult, onAuthStateChanged } from 'firebase/auth';

const debugInfo = ref<any[]>([]);
const currentUser = ref<any>(null);

function addDebugInfo(message: string, data?: any) {
  debugInfo.value.push({
    timestamp: new Date().toISOString(),
    message,
    data: data ? JSON.stringify(data, null, 2) : null
  });
  console.log(message, data);
}

onMounted(async () => {
  addDebugInfo('Debug component mounted');
  
  // Check for redirect result
  try {
    addDebugInfo('Checking for redirect result...');
    const result = await getRedirectResult(auth);
    
    if (result) {
      addDebugInfo('Redirect result found', {
        user: result.user.email,
        provider: result.providerId
      });
    } else {
      addDebugInfo('No redirect result');
    }
  } catch (error: any) {
    addDebugInfo('Redirect result error', {
      code: error.code,
      message: error.message
    });
  }
  
  // Listen for auth state changes
  onAuthStateChanged(auth, (user) => {
    currentUser.value = user;
    if (user) {
      addDebugInfo('User signed in', {
        uid: user.uid,
        email: user.email,
        displayName: user.displayName,
        providerId: user.providerData[0]?.providerId
      });
    } else {
      addDebugInfo('User signed out');
    }
  });
  
  // Check current URL for any error parameters
  const urlParams = new URLSearchParams(window.location.search);
  const error = urlParams.get('error');
  const errorDescription = urlParams.get('error_description');
  
  if (error) {
    addDebugInfo('URL contains error parameters', {
      error,
      errorDescription
    });
  }
});
</script>

<template>
  <v-container>
    <v-card>
      <v-card-title>Auth Debug Information</v-card-title>
      <v-card-text>
        <div class="mb-4">
          <strong>Current User:</strong>
          <pre v-if="currentUser">{{ JSON.stringify(currentUser, null, 2) }}</pre>
          <span v-else>Not signed in</span>
        </div>
        
        <v-divider class="my-4"></v-divider>
        
        <div>
          <strong>Debug Log:</strong>
          <div 
            v-for="(info, index) in debugInfo" 
            :key="index"
            class="mb-2 pa-2 bg-grey-lighten-5"
          >
            <div class="text-caption">{{ info.timestamp }}</div>
            <div class="font-weight-bold">{{ info.message }}</div>
            <pre v-if="info.data" class="text-caption">{{ info.data }}</pre>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>