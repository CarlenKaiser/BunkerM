import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

import {
  registerUser,
  loginUser,
  loginWithMicrosoft,
  logoutUser,
  onAuthChange,
} from '@/services/auth';

import type { User as AuthUser } from '@/services/auth';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null);
  const token = ref<string | null>(null);
  const loading = ref(true);

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
    token.value = null;
  }

  // Updated setUser to accept user and token
  function setUser(newUser: AuthUser | null, authToken?: string) {
    user.value = newUser;
    token.value = authToken || null;
  }

  const isAuthenticated = computed(() => !!user.value && !!token.value);

  return {
    user,
    token,
    loading,
    init,
    register,
    login,
    loginWithMicrosoftSSO,
    logout,
    setUser,
    isAuthenticated,
  };
});
