<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const error = ref('');

// On mount, just initialize auth state (no redirect handling needed)
onMounted(async () => {
  try {
    await authStore.init();

    // If already authenticated, redirect to dashboard
    if (authStore.isAuthenticated) {
      router.push('/dashboard');
    }
  } catch (err: any) {
    console.error('Error initializing auth:', err);
    error.value = err.message || 'Failed to initialize authentication';
  }
});

async function loginWithMicrosoftPopup() {
  loading.value = true;
  error.value = '';

  try {
    await authStore.loginWithMicrosoftSSO();
    
    // Success - redirect to dashboard
    router.push('/dashboard');
  } catch (err: any) {
    console.error('OIDC login failed:', err);
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
  <div class="login-container">
    <div class="login-card">
      <h2>Sign In</h2>
      
      <button
        type="button"
        class="ms-login-btn"
        @click="loginWithMicrosoftPopup"
        :disabled="loading"
      >
        <span class="ms-icon">
          <!-- Microsoft icon SVG here -->
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M11.4 24H0V12.6h11.4V24zM24 24H12.6V12.6H24V24zM11.4 11.4H0V0h11.4v11.4zM24 11.4H12.6V0H24v11.4z" fill="#00BCF2"/>
          </svg>
        </span>
        <span v-if="loading">Signing in...</span>
        <span v-else>Sign in with Azure AD</span>
      </button>

      <!-- Error display -->
      <div v-if="error" class="error-container">
        <p class="error-message">{{ error }}</p>
        <button @click="clearError" class="clear-error-btn">×</button>
      </div>
      
      <!-- Loading indicator -->
      <div v-if="authStore.loading && !loading" class="loading-message">
        Checking authentication status...
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background-color: #f5f5f5;
}

.login-card {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
}

.login-card h2 {
  text-align: center;
  margin-bottom: 2rem;
  color: #333;
}

.ms-login-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background-color: #0078d4;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 1rem;
  cursor: pointer;
  transition: background-color 0.2s;
}

.ms-login-btn:hover:not(:disabled) {
  background-color: #106ebe;
}

.ms-login-btn:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.error-container {
  margin-top: 1rem;
  padding: 0.75rem;
  background-color: #fee;
  border: 1px solid #fcc;
  border-radius: 4px;
  position: relative;
}

.error-message {
  color: #c33;
  margin: 0;
  font-size: 0.9rem;
}

.clear-error-btn {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #c33;
  cursor: pointer;
  padding: 0;
  width: 1.5rem;
  height: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.loading-message {
  margin-top: 1rem;
  text-align: center;
  color: #666;
  font-size: 0.9rem;
}

.ms-icon svg {
  width: 20px;
  height: 20px;
}
</style>