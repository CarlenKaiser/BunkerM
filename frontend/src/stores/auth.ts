// @/stores/auth.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { onIdTokenChanged } from 'firebase/auth';
import { auth } from '@/firebase';
import { loginWithMicrosoft, logoutUser, handleSSORedirect } from '@/services/auth';
import type { User } from '@/types/user';

export type { User } from '@/types/user';

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null);
  const token = ref<string | null>(null);
  const loading = ref(true);
  const error = ref<string | null>(null);

  /**
   * Initialize auth state and handle SSO redirects
   */
  async function init() {
    loading.value = true;
    error.value = null;

    try {
      // Handle any pending SSO redirect first
      await handleSSORedirect();
    } catch (err) {
      console.error('SSO redirect error:', err);
      error.value = 'Failed to process login redirect';
    }

    // Listen for auth state changes
    onIdTokenChanged(auth, async (firebaseUser) => {
      try {
        if (firebaseUser) {
          // User is signed in
          const idToken = await firebaseUser.getIdToken();
          
          // Validate required fields
          if (!firebaseUser.email) {
            throw new Error('User has no email address');
          }

          const authUser: User = {
            id: firebaseUser.uid,
            email: firebaseUser.email,
            firstName: firebaseUser.displayName?.split(' ')[0] || '',
            lastName: firebaseUser.displayName?.split(' ').slice(1).join(' ') || '',
            role: 'user', // Default role, you can fetch from custom claims
            createdAt: firebaseUser.metadata.creationTime || new Date().toISOString(),
          };

          // Get custom claims for role-based access
          const tokenResult = await firebaseUser.getIdTokenResult();
          if (tokenResult.claims.role) {
            authUser.role = tokenResult.claims.role as string;
          }

          setUser(authUser, idToken);
          error.value = null;
        } else {
          // User is signed out
          setUser(null, null);
        }
      } catch (err) {
        console.error('Auth state change error:', err);
        error.value = 'Authentication error occurred';
        setUser(null, null);
      }
      
      loading.value = false;
    });
  }

  /**
   * Login with Microsoft SSO
   */
  async function loginWithMicrosoftSSO() {
    try {
      error.value = null;
      await loginWithMicrosoft();
      // Redirect happens, user will be redirected back to app
    } catch (err) {
      console.error('Microsoft login error:', err);
      error.value = 'Failed to initiate Microsoft login';
      throw err;
    }
  }

  /**
   * Logout current user
   */
  async function logout() {
    try {
      error.value = null;
      await logoutUser();
      // Auth state change will be handled by onIdTokenChanged
    } catch (err) {
      console.error('Logout error:', err);
      error.value = 'Failed to logout';
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
    
    // Getters
    isAuthenticated,
    isAdmin,
    isModerator,
    
    // Actions
    init,
    loginWithMicrosoftSSO,
    logout,
    setUser,
    clearError,
  };
});