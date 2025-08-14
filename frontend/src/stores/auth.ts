// @/stores/auth.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { onIdTokenChanged } from 'firebase/auth';
import type { User as FirebaseUser } from 'firebase/auth'; // Import FirebaseUser type
import { auth } from '@/firebase';
import { loginWithMicrosoft, logoutUser } from '@/services/auth';
import type { User } from '@/types/user';
export type { User } from '@/types/user';

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null);
  const token = ref<string | null>(null);
  const loading = ref(true);
  const error = ref<string | null>(null);
  const initialized = ref(false); // Declare initialized ref

  // Helper function to handle signed in user
  async function handleSignedInUser(firebaseUser: FirebaseUser) {
    const idToken = await firebaseUser.getIdToken();
    
    if (!firebaseUser.email) {
      throw new Error('User has no email address');
    }

    const authUser: User = {
      id: firebaseUser.uid,
      email: firebaseUser.email,
      firstName: firebaseUser.displayName?.split(' ')[0] || '',
      lastName: firebaseUser.displayName?.split(' ').slice(1).join(' ') || '',
      role: 'user',
      createdAt: firebaseUser.metadata.creationTime || new Date().toISOString(),
    };

    // Get custom claims
    try {
      const tokenResult = await firebaseUser.getIdTokenResult(true);
      if (tokenResult.claims.role) {
        authUser.role = tokenResult.claims.role as string;
      }
    } catch (claimsError) {
      console.warn('Could not get custom claims:', claimsError);
    }

    localStorage.setItem('firebaseToken', idToken);
    setUser(authUser, idToken);
  }

  /**
   * Initialize auth state
   */
  async function init(): Promise<void> {
    return new Promise((resolve) => {
      loading.value = true;
      error.value = null;

      const unsubscribe = onIdTokenChanged(auth, async (firebaseUser) => {
        try {
          if (firebaseUser) {
            await handleSignedInUser(firebaseUser);
          } else {
            setUser(null, null);
          }
        } catch (err) {
          console.error('Auth state change error:', err);
          error.value = 'Authentication error occurred';
          setUser(null, null);
        } finally {
          if (!initialized.value) {
            initialized.value = true;
            resolve();
          }
          loading.value = false;
        }
      });

      // Cleanup function
      return () => unsubscribe();
    });
  }

  /**
   * Login with Microsoft SSO
   */
  async function loginWithMicrosoftSSO() {
    try {
      loading.value = true;
      error.value = null;
      const firebaseUser = await loginWithMicrosoft();
      
      // Wait for the auth state to fully update
      await new Promise(resolve => setTimeout(resolve, 100));
      return firebaseUser;
    } catch (err: any) {
      console.error('Microsoft login error:', err);
      error.value = err.message || 'Failed to sign in with Microsoft';
      throw err;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Logout current user
   */
  async function logout() {
    try {
      error.value = null;
      await logoutUser();
      // Clear local storage and reset state
      localStorage.removeItem('firebaseToken');
      setUser(null, null);
    } catch (err: any) {
      console.error('Logout error:', err);
      error.value = err.message || 'Failed to logout';
      throw err;
    }
  }

  /**
   * Set user and token
   */
  function setUser(newUser: User | null, authToken: string | null = null) {
    user.value = newUser;
    token.value = authToken;
  }

  /**
   * Clear any errors
   */
  function clearError() {
    error.value = null;
  }

  /**
   * Check authentication status
   */
  async function checkAuth() {
    if (!initialized.value) {
      await init();
    }
    return isAuthenticated.value;
  }

  // Computed properties
  const isAuthenticated = computed(() => !!user.value && !!token.value);
  const isAdmin = computed(() => user.value?.role === 'admin');
  const isModerator = computed(() => user.value?.role === 'moderator' || isAdmin.value);

  return {
    // State
    user,
    token,
    loading,
    error,
    initialized,
    
    // Getters
    isAuthenticated,
    isAdmin,
    isModerator,
    
    // Actions
    init,
    checkAuth,
    loginWithMicrosoftSSO,
    logout,
    setUser,
    clearError,
  };
});