// src/stores/auth.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';

import {
  registerUser,
  loginUser,
  loginWithMicrosoft,
  logoutUser,
  onAuthChange,
  mapFirebaseUser,
  User as AuthUser,
} from '@/services/auth';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null);
  const loading = ref(true);

  // Initialize auth state listener
  async function init() {
    loading.value = true;
    onAuthChange((firebaseUser) => {
      user.value = firebaseUser;
      loading.value = false;
    });
  }

  async function register(email: string, password: string, firstName?: string, lastName?: string) {
    const { user: registeredUser } = await registerUser(email, password, firstName, lastName);
    user.value = registeredUser;
    return registeredUser;
  }

  async function login(email: string, password: string) {
    const { user: loggedInUser } = await loginUser(email, password);
    user.value = loggedInUser;
    return loggedInUser;
  }

  async function loginWithMicrosoftSSO() {
    const { user: loggedInUser } = await loginWithMicrosoft();
    user.value = loggedInUser;
    return loggedInUser;
  }

  async function logout() {
    await logoutUser();
    user.value = null;
  }

  return {
    user,
    loading,
    init,
    register,
    login,
    loginWithMicrosoftSSO,
    logout,
  };
});
