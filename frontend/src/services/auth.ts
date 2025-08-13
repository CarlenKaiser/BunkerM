// @/services/auth.ts
import { 
  signInWithRedirect, 
  signOut, 
  OAuthProvider,
  getRedirectResult 
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
  tenant: 'common', // or your specific tenant ID like 'your-tenant-id'
  
  // Optional: Force account selection
  prompt: 'select_account'
});

// Set required scopes
microsoftProvider.addScope('User.Read');
microsoftProvider.addScope('email');
microsoftProvider.addScope('openid');
microsoftProvider.addScope('profile');

/**
 * Redirects user to Microsoft SSO login
 */
export async function loginWithMicrosoft(): Promise<void> {
  try {
    console.log('Initiating Microsoft SSO login...');
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
    const result = await getRedirectResult(auth);
    
    if (result) {
      // User successfully signed in
      const user = result.user;
      const credential = OAuthProvider.credentialFromResult(result);
      
      console.log('SSO Login successful:', {
        user: user.displayName,
        email: user.email,
        provider: credential?.providerId,
        uid: user.uid
      });
      
      return result;
    } else {
      console.log('No redirect result found');
      return null;
    }
  } catch (error: any) {
    console.error('SSO redirect handling failed:', error);
    
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
      default:
        throw new Error(`Failed to process SSO login: ${error.message || 'Unknown error'}`);
    }
  }
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