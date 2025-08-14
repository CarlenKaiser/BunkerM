<script setup lang="ts">
import { ref, onMounted, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import type { Ref } from 'vue';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();

const loading: Ref<boolean> = ref(false);
const error: Ref<string> = ref('');

// Watch for authentication changes
watch(
  () => authStore.isAuthenticated,
  (isAuthenticated: boolean) => {
    if (isAuthenticated) {
      handleRedirect();
    }
  }
);

// Initialize auth store on mount
onMounted(async () => {
  try {
    await authStore.init();
    
    // If already authenticated, redirect immediately
    if (authStore.isAuthenticated) {
      handleRedirect();
    }
  } catch (err) {
    console.error('Auth initialization error:', err);
    error.value = 'Failed to initialize authentication';
  }
});

function handleRedirect() {
  const redirectPath = route.query.redirect 
    ? String(route.query.redirect)
    : '/dashboard';
  
  console.log('Redirecting to:', redirectPath);
  router.push(redirectPath);
}

async function loginWithAzureAD() {
  loading.value = true;
  error.value = '';

  try {
    await authStore.loginWithMicrosoftSSO();
    // The redirect will be handled by the watcher
  } catch (err: unknown) {
    console.error('Azure AD login failed:', err);
    error.value = err instanceof Error ? err.message : 'Login failed. Please try again.';
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
  <!-- Your template remains the same -->
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
  </div>
</template>

<style lang="scss" scoped>
/* Your styles remain the same */
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