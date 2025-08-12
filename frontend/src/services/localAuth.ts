// src/stores/auth.ts
import { defineStore } from 'pinia';
import { ref } from 'vue';
import {
  registerUser,
  loginUser,
  loginWithMicrosoft,
  logoutUser,
  onAuthChange,
  mapFirebaseUser
} from '@/services/auth';

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const token = ref<string | null>(null);
  const loading = ref(true);

  async function init() {
    loading.value = true;
    return new Promise<void>((resolve) => {
      onAuthChange(async (firebaseUser) => {
        if (firebaseUser) {
          user.value = firebaseUser;

          // Get token from Firebase SDK directly
          // IMPORTANT: You need the FirebaseUser instance to get token, so here we re-fetch from Firebase auth.currentUser
          const currentUser = (await import('firebase/auth')).getAuth().currentUser;
          token.value = currentUser ? await currentUser.getIdToken() : null;

          localStorage.setItem('user', JSON.stringify(user.value));
          localStorage.setItem('auth_token', token.value || '');
        } else {
          // Clear
          user.value = null;
          token.value = null;
          localStorage.removeItem('user');
          localStorage.removeItem('auth_token');
        }
        loading.value = false;
        resolve();
      });
    });
  }

  async function register(email: string, password: string, firstName: string, lastName: string) {
    loading.value = true;
    try {
      const { user: newUser, firebaseUser } = await registerUser(email, password, firstName, lastName);
      user.value = newUser;
      token.value = await firebaseUser.getIdToken();

      localStorage.setItem('user', JSON.stringify(user.value));
      localStorage.setItem('auth_token', token.value || '');

      return user.value;
    } finally {
      loading.value = false;
    }
  }

  async function login(email: string, password: string) {
    loading.value = true;
    try {
      const { user: loggedUser, firebaseUser } = await loginUser(email, password);
      user.value = loggedUser;
      token.value = await firebaseUser.getIdToken();

      localStorage.setItem('user', JSON.stringify(user.value));
      localStorage.setItem('auth_token', token.value || '');

      return user.value;
    } finally {
      loading.value = false;
    }
  }

  async function loginMicrosoft() {
    loading.value = true;
    try {
      const { user: msUser, firebaseUser } = await loginWithMicrosoft();
      user.value = msUser;
      token.value = await firebaseUser.getIdToken();

      localStorage.setItem('user', JSON.stringify(user.value));
      localStorage.setItem('auth_token', token.value || '');

      return user.value;
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    loading.value = true;
    try {
      await logoutUser();
      user.value = null;
      token.value = null;
      localStorage.removeItem('user');
      localStorage.removeItem('auth_token');
    } finally {
      loading.value = false;
    }
  }

  function isAuthenticated() {
    return !!user.value && !!token.value;
  }

  init();

  return {
    user,
    token,
    loading,
    init,
    register,
    login,
    loginMicrosoft,
    logout,
    isAuthenticated,
  };
});
