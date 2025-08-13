<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { getRedirectResult, OAuthProvider, signInWithRedirect } from 'firebase/auth';
import { auth } from '@/firebase';

const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const error = ref('');

// On mount, initialize auth state and handle redirect result
onMounted(async () => {
  loading.value = true;
  try {
    await authStore.init();

    const result = await getRedirectResult(auth);
    if (result && result.user) {
      const user = result.user;
      const token = await user.getIdToken();

      authStore.setUser({
        id: user.uid,
        email: user.email || '',
        firstName: user.displayName?.split(' ')[0] || '',
        lastName: user.displayName?.split(' ').slice(1).join(' ') || '',
        createdAt: ''
      }, token);

      router.push('/dashboard');
      return;
    }

    if (authStore.isAuthenticated) {
      router.push('/dashboard');
    }
  } catch (err: any) {
    console.error('Error processing auth:', err);
    error.value = err.message || 'Login failed. Please try again.';
  } finally {
    loading.value = false;
  }
});

function loginWithMicrosoftRedirect() {
  loading.value = true;
  error.value = '';

  const provider = new OAuthProvider('microsoft.com');
  provider.setCustomParameters({ prompt: 'select_account' });

  signInWithRedirect(auth, provider);
}
</script>

<template>
  <div>
    <button
      type="button"
      class="ms-login-btn"
      @click="loginWithMicrosoftRedirect"
      :disabled="loading"
    >
      <span class="ms-icon">
        <!-- Microsoft icon SVG here -->
      </span>
      Login with Microsoft
    </button>

    <p v-if="error" class="error-message">{{ error }}</p>
  </div>
</template>
