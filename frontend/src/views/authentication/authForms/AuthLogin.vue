/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const error = ref('');

// Initialize auth store on mount
onMounted(async () => {
  // Initialize the auth store to check for existing sessions
  await authStore.init();
  
  // If already authenticated, redirect to dashboard
  if (authStore.isAuthenticated) {
    console.log('User already authenticated, redirecting to dashboard');
    router.push('/dashboard');
  }
});

async function loginWithAzureAD() {
  loading.value = true;
  error.value = '';

  try {
    await authStore.loginWithMicrosoftSSO();
    
    // Success - redirect to dashboard
    router.push('/dashboard');
  } catch (err: any) {
    console.error('Azure AD login failed:', err);
    error.value = err.message || 'Login failed. Please try again.';
  } finally {
    loading.value = false;
  }
}

function clearError() {
  error.value = '';
  authStore.clearError();
}
</script>

<template>
  <div class="d-flex justify-center align-center">
    <h3 class="text-h3 text-center mb-0">Login</h3>
  </div>
  
  <div class="mt-7 loginForm d-flex flex-column align-center">
    <!-- SSO Login Button -->
    <v-btn
      color="primary" 
      :loading="loading" 
      size="large"
      class="sso-login-btn"
      variant="flat"
      @click="loginWithAzureAD"
      :disabled="loading"
    >
      <v-icon class="me-2">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zM24 11.4H12.6V0H24v11.4z" fill="white"/>
        </svg>
      </v-icon>
      <span v-if="loading">Signing in...</span>
      <span v-else>Sign in with Azure AD</span>
    </v-btn>

    <!-- Error display -->
    <v-alert
      v-if="error"
      type="error"
      class="mt-4 error-alert"
      closable
      @click:close="clearError"
    >
      {{ error }}
    </v-alert>
    
    <!-- Loading indicator -->
    <div v-if="authStore.loading && !loading" class="mt-4 text-center">
      <v-progress-circular indeterminate size="24" class="me-2"></v-progress-circular>
      <span class="text-body-2">Checking authentication status...</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.loginForm {
  min-height: 200px;
  justify-content: center;
}

.sso-login-btn {
  min-width: 280px;
  height: 48px;
  font-size: 1rem;
  font-weight: 500;
  text-transform: none;
  letter-spacing: 0.02em;
}

.error-alert {
  max-width: 400px;
  width: 100%;
}

.v-btn--loading .v-btn__content {
  opacity: 1;
}
</style>