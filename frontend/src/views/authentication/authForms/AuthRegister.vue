<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { EyeInvisibleOutlined, EyeOutlined } from '@ant-design/icons-vue';
import { useAuthStore } from '@/stores/auth';

import { auth, firestore } from '@/firebase'; // your firebase config export
import { createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';
import { doc, setDoc } from 'firebase/firestore';

const router = useRouter();
const authStore = useAuthStore();

const show1 = ref(false);
const password = ref('');
const email = ref('');
const firstname = ref('');
const lastname = ref('');
const registrationSuccess = ref(false);
const registrationError = ref('');

// Check if user logged in on mount
onMounted(async () => {
  await authStore.init();
  if (authStore.isAuthenticated()) {
    router.push('/dashboard');
  }
});

const passwordRules = ref([
  (v: string) => !!v || 'Password is required',
  (v: string) => (v && v.length >= 6) || 'Password must be at least 6 characters'
]);

const firstRules = ref([(v: string) => !!v || 'First Name is required']);
const lastRules = ref([(v: string) => !!v || 'Last Name is required']);
const emailRules = ref([
  (v: string) => !!v || 'E-mail is required',
  (v: string) => /.+@.+\..+/.test(v) || 'E-mail must be valid'
]);

async function validate() {
  registrationError.value = '';
  try {
    // Create Firebase user with email/password
    const userCredential = await createUserWithEmailAndPassword(auth, email.value, password.value);
    const user = userCredential.user;

    // Update profile with first and last name
    await updateProfile(user, {
      displayName: `${firstname.value} ${lastname.value}`
    });

    // Optionally, save additional user info in Firestore (recommended)
    await setDoc(doc(firestore, 'users', user.uid), {
      firstName: firstname.value,
      lastName: lastname.value,
      email: email.value,
      createdAt: new Date()
    });

    // Set user in your authStore if needed
    await authStore.setUser({
      uid: user.uid,
      email: user.email,
      displayName: user.displayName
    }, 'firebase-auth-token');

    registrationSuccess.value = true;

    setTimeout(() => {
      router.push('/dashboard');
    }, 1500);
  } catch (error: any) {
    console.error(error);
    registrationError.value = error.message || 'Failed to register. Please try again.';
  }
}
</script>
