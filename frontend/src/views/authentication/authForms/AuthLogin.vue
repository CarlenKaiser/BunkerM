<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons-vue';
import { useAuthStore } from '@/stores/auth';
import { signInWithEmailAndPassword, OAuthProvider, signInWithPopup } from 'firebase/auth';
import { auth } from '@/firebase';  // import your firebase auth instance

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

    // Set user in store (you may want to store more user info/token as needed)
    await authStore.setUser({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      // any other user info you want
    }, 'firebase-auth-token'); // token can be fetched if needed

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

    // You can get additional profile info here if needed from result.additionalUserInfo

    await authStore.setUser({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
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
