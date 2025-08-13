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
microsoftProvider.setCustomParameters({
  tenant: 'your-tenant-id', // Replace with your Microsoft tenant ID
});

// Optional: Set scopes for additional permissions
microsoftProvider.addScope('User.Read');
microsoftProvider.addScope('email');

/**
 * Redirects user to Microsoft SSO login
 */
export async function loginWithMicrosoft(): Promise<void> {
  try {
    await signInWithRedirect(auth, microsoftProvider);
  } catch (error) {
    console.error('Microsoft SSO login failed:', error);
    throw new Error('Failed to initiate Microsoft login');
  }
}

/**
 * Handles the redirect result from Microsoft SSO
 */
export async function handleSSORedirect() {
  try {
    const result = await getRedirectResult(auth);
    if (result) {
      // User successfully signed in
      const user = result.user;
      const credential = OAuthProvider.credentialFromResult(result);
      
      // You can access Microsoft-specific data here if needed
      console.log('SSO Login successful:', {
        user: user.displayName,
        email: user.email,
        provider: credential?.providerId
      });
      
      return result;
    }
    return null;
  } catch (error) {
    console.error('SSO redirect handling failed:', error);
    throw new Error('Failed to process SSO login');
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