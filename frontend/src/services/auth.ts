// @/services/auth.ts
import { 
  signInWithRedirect, 
  signInWithPopup,
  signOut, 
  OAuthProvider,
  getRedirectResult,
  onAuthStateChanged,
  User as FirebaseUser
} from 'firebase/auth';
import { auth } from '@/firebase';
import type { User } from '@/types/user';

// Re-export for convenience
export type { User } from '@/types/user';

// Microsoft SSO provider
const microsoftProvider = new OAuthProvider('microsoft.com');

// IMPORTANT: Set these parameters for proper Microsoft integration
microsoftProvider.setCustomParameters({
  // For single tenant: use your tenant ID
  // For multi-tenant: use 'common'
  tenant: 'common', // Change to your tenant ID if single-tenant
  
  // Force account selection and consent
  prompt: 'select_account consent',
  
  // Optional: specify domain hint for faster login
  // domain_hint: 'yourdomain.com'
});

// Set required scopes - be specific about what you need
microsoftProvider.addScope('https://graph.microsoft.com/User.Read');
microsoftProvider.addScope('email');
microsoftProvider.addScope('openid');
microsoftProvider.addScope('profile');

/**
 * Redirects user to Microsoft SSO login
 */
export async function loginWithMicrosoft(): Promise<void> {
  try {
    console.log('Initiating Microsoft SSO login...');
    
    // Clear any existing auth state
    if (auth.currentUser) {
      await signOut(auth);
    }
    
    await signInWithRedirect(auth, microsoftProvider);
  } catch (error: any) {
    console.error('Microsoft SSO login failed:', error);
    
    // Log specific error details
    if (error.code) {
      console.error('Error code:', error.code);
    }
    if (error.message) {
      console.error('Error message:', error.message);
    }
    
    throw new Error(`Failed to initiate Microsoft login: ${error.message || error.code || 'Unknown error'}`);
  }
}

/**
 * Handles the redirect result from Microsoft SSO
 */
export async function handleSSORedirect() {
  try {
    console.log('Checking for SSO redirect result...');
    
    // Add a small delay to ensure Firebase is ready
    await new Promise(resolve => setTimeout(resolve, 100));
    
    const result = await getRedirectResult(auth);
    
    if (result) {
      // User successfully signed in
      const user = result.user;
      const credential = OAuthProvider.credentialFromResult(result);
      
      console.log('SSO Login successful:', {
        user: user.displayName,
        email: user.email,
        provider: credential?.providerId,
        uid: user.uid,
        accessToken: credential?.accessToken ? 'Present' : 'Missing'
      });
      
      // Verify the user has the required claims
      const idTokenResult = await user.getIdTokenResult();
      console.log('ID Token claims:', idTokenResult.claims);
      
      return result;
    } else {
      console.log('No redirect result found');
      
      // Check if we're in the middle of a redirect
      const urlParams = new URLSearchParams(window.location.search);
      const hasAuthParams = urlParams.has('code') || urlParams.has('error');
      
      if (hasAuthParams) {
        console.log('Found auth parameters in URL but no redirect result');
        console.log('URL params:', Object.fromEntries(urlParams.entries()));
      }
      
      return null;
    }
  } catch (error: any) {
    console.error('SSO redirect handling failed:', error);
    
    // Enhanced error handling
    const errorInfo = {
      code: error.code,
      message: error.message,
      stack: error.stack,
      customData: error.customData
    };
    
    console.error('Detailed error info:', errorInfo);
    
    // Handle specific Firebase auth errors
    switch (error.code) {
      case 'auth/account-exists-with-different-credential':
        throw new Error('An account already exists with the same email address but different sign-in credentials.');
      case 'auth/cancelled-popup-request':
      case 'auth/popup-cancelled-by-user':
        throw new Error('Sign-in was cancelled.');
      case 'auth/popup-blocked':
        throw new Error('Sign-in popup was blocked by the browser.');
      case 'auth/operation-not-allowed':
        throw new Error('Microsoft sign-in is not enabled. Please contact support.');
      case 'auth/invalid-credential':
        throw new Error('Invalid credentials. Please try again.');
      case 'auth/network-request-failed':
        throw new Error('Network error. Please check your connection and try again.');
      case 'auth/timeout':
        throw new Error('Request timed out. Please try again.');
      default:
        throw new Error(`Failed to process SSO login: ${error.message || 'Unknown error'}`);
    }
  }
}

/**
 * Initialize auth state monitoring - returns Firebase User
 */
export function initializeAuth(): Promise<FirebaseUser | null> {
  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      unsubscribe(); // Only listen for the first state change
      resolve(user);
    });
  });
}

/**
 * Convert Firebase User to your custom User type
 */
export function mapFirebaseUserToUser(firebaseUser: FirebaseUser | null): User | null {
  if (!firebaseUser) return null;
  
  return {
    id: firebaseUser.uid,
    firstName: firebaseUser.displayName?.split(' ')[0] || '',
    lastName: firebaseUser.displayName?.split(' ').slice(1).join(' ') || '',
    email: firebaseUser.email || '',
    createdAt: firebaseUser.metadata.creationTime 
      ? firebaseUser.metadata.creationTime 
      : new Date().toISOString(),
    // Add any other fields your User type requires based on your type definition
  };
}

/**
 * Initialize auth and return your custom User type
 */
export async function initializeAuthWithCustomUser(): Promise<User | null> {
  const firebaseUser = await initializeAuth();
  return mapFirebaseUserToUser(firebaseUser);
}

/**
 * Signs out the current user
 */
export async function logoutUser(): Promise<void> {
  try {
    await signOut(auth);
  } catch (error) {
    console.error('Logout failed:', error);
    throw new Error('Failed to logout');
  }
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return !!auth.currentUser;
}

/**
 * Get current user's Microsoft access token for Graph API calls
 */
export async function getMicrosoftAccessToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  
  try {
    const idTokenResult = await user.getIdTokenResult();
    
    // The Microsoft access token should be available in the token
    // This depends on your Firebase project configuration
    return idTokenResult.token;
  } catch (error) {
    console.error('Failed to get access token:', error);
    return null;
  }
}