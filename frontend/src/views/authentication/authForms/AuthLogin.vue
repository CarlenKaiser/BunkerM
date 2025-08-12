<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/auth';
import { signInWithEmailAndPassword, OAuthProvider, signInWithPopup } from 'firebase/auth';
import { auth } from '@/firebase';

const router = useRouter();
const authStore = useAuthStore();

const checkbox = ref(false);
const show1 = ref(false);
const password = ref('');
const email = ref('');
const showDefaultCredentials = ref(true);
const loading = ref(false);
const error = ref('');

// On mount, set default creds and check auth
onMounted(async () => {
  email.value = 'admin@example.com';
  password.value = 'password123';

  await authStore.init();

  if (authStore.isAuthenticated()) {
    router.push('/dashboard');
  }
});

const passwordRules = ref([
  (v: string) => !!v || 'Password is required',
  (v: string) => (v && v.length >= 6) || 'Password must be at least 6 characters'
]);

const emailRules = ref([
  (v: string) => !!v || 'E-mail is required',
  (v: string) => /.+@.+\..+/.test(v) || 'E-mail must be valid'
]);

async function handleLogin() {
  try {
    loading.value = true;
    error.value = '';

    // Firebase email/password login
    const userCredential = await signInWithEmailAndPassword(auth, email.value, password.value);
    const user = userCredential.user;

    // Set user in store
    await authStore.setUser({
      id: user.uid,
      email: user.email,
      firstName: user.displayName?.split(' ')[0] || '',
      lastName: user.displayName?.split(' ').slice(1).join(' ') || '',
      createdAt: ''  // or whatever value you have here
    }, 'firebase-auth-token');

    router.push('/dashboard');
  } catch (err: any) {
    console.error('Firebase login error:', err);
    error.value = err.message || 'Login failed. Please try again.';
  } finally {
    loading.value = false;
  }
}

// Microsoft SSO login
async function loginWithMicrosoft() {
  try {
    loading.value = true;
    error.value = '';

    const provider = new OAuthProvider('microsoft.com');
    const result = await signInWithPopup(auth, provider);
    const user = result.user;

    await authStore.setUser({
      id: user.uid,
      email: user.email,
      firstName: user.displayName?.split(' ')[0] || '',
      lastName: user.displayName?.split(' ').slice(1).join(' ') || '',
      createdAt: ''  // or whatever value you have here
    }, 'firebase-auth-token');

    router.push('/dashboard');
  } catch (err: any) {
    console.error('Microsoft SSO login error:', err);
    error.value = err.message || 'Microsoft login failed. Please try again.';
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <form @submit.prevent="handleLogin">
    <div>
      <label for="email">Email</label>
      <input id="email" v-model="email" type="email" required />
    </div>

    <div>
      <label for="password">Password</label>
      <input id="password" v-model="password" type="password" required />
    </div>

    <button type="submit" :disabled="loading">Login</button>

    <button
      type="button"
      class="ms-login-btn"
      @click="loginWithMicrosoft"
      :disabled="loading"
    >
      <span class="ms-icon">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="1" y="1" width="10" height="10" fill="#F35325"/>
          <rect x="13" y="1" width="10" height="10" fill="#81BC06"/>
          <rect x="1" y="13" width="10" height="10" fill="#05A6F0"/>
          <rect x="13" y="13" width="10" height="10" fill="#FFBA08"/>
        </svg>
      </span>
      Login with Microsoft
    </button>

    <p v-if="error" class="error-message">{{ error }}</p>
  </form>
</template>

<style scoped>
.ms-login-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  border: 1px solid #1f2937;
  border-radius: 6px;
  background-color: #fff;
  font-weight: 600;
  font-size: 14px;
  color: #1f2937;
  cursor: pointer;
  transition: background-color 0.2s ease;
  margin-top: 12px;
}

.ms-login-btn:hover {
  background-color: #f3f4f6;
}

.ms-login-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ms-icon {
  display: inline-flex;
  align-items: center;
}
.error-message {
  color: #d32f2f;
  margin-top: 10px;
}
</style>
