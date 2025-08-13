// @/services/auth.ts
import { 
  signInWithPopup,
  signOut, 
  OAuthProvider,
  onAuthStateChanged
} from 'firebase/auth';
import type { User as FirebaseUser } from 'firebase/auth';
import { auth } from '@/firebase';
import type { User } from '@/types/user';

// Re-export for convenience
export type { User } from '@/types/user';

// OIDC provider for single tenant Azure AD
const oidcProvider = new OAuthProvider('oidc.bunkerm-azuread-single-tenant');

// Set required scopes for your OIDC provider
oidcProvider.addScope('openid');
oidcProvider.addScope('profile');
oidcProvider.addScope('email');

// Optional: Add custom parameters if needed for your Azure AD setup
// oidcProvider.setCustomParameters({
//   prompt: 'select_account'
// });

/**
 * Signs in user with OIDC provider using popup
 */
export async function loginWithMicrosoft(): Promise<FirebaseUser> {
  try {
    console.log('Initiating OIDC popup login...');
    
    // Clear any existing auth state
    if (auth.currentUser) {
      await signOut(auth);
    }
    
    // Use popup instead of redirect
    const result = await signInWithPopup(auth, oidcProvider);
    
    if (!result || !result.user) {
      throw new Error('No user returned from popup sign-in');
    }

    const user = result.user;
    const credential = OAuthProvider.credentialFromResult(result);
    
    console.log('OIDC Login successful:', {
      user: user.displayName,
      email: user.email,
      provider: credential?.providerId,
      uid: user.uid,
      accessToken: credential?.accessToken ? 'Present' : 'Missing'
    });
    
    // Verify the user has the required claims
    try {
      const idTokenResult = await user.getIdTokenResult();
      console.log('ID Token claims:', idTokenResult.claims);
    } catch (tokenError) {
      console.warn('Could not get ID token result:', tokenError);
    }
    
    return user;
  } catch (error: any) {
    console.error('OIDC popup login failed:', error);
    
    // Log specific error details
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
        throw new Error('Sign-in was cancelled by the user.');
      case 'auth/popup-blocked':
        throw new Error('Sign-in popup was blocked by the browser. Please allow popups and try again.');
      case 'auth/operation-not-allowed':
        throw new Error('OIDC sign-in is not enabled. Please contact support.');
      case 'auth/invalid-credential':
        throw new Error('Invalid credentials. Please try again.');
      case 'auth/network-request-failed':
        throw new Error('Network error. Please check your connection and try again.');
      case 'auth/timeout':
        throw new Error('Request timed out. Please try again.');
      case 'auth/popup-closed-by-user':
        throw new Error('Sign-in popup was closed before completing authentication.');
      case 'auth/configuration-not-found':
        throw new Error('OIDC configuration not found. Please check your Firebase project setup.');
      default:
        throw new Error(`Failed to sign in with OIDC: ${error.message || 'Unknown error'}`);
    }
  }
}

/**
 * Alternative OIDC popup login with different configuration
 */
export async function loginWithOIDCPopup(): Promise<FirebaseUser> {
  try {
    console.log('Starting OIDC popup authentication...');
    
    // Create a fresh provider instance
    const provider = new OAuthProvider('oidc.bunkerm-azuread-single-tenant');
    
    // Add scopes
    provider.addScope('openid');
    provider.addScope('profile'); 
    provider.addScope('email');
    
    // Optional: Set custom parameters for Azure AD
    // provider.setCustomParameters({
    //   prompt: 'select_account',
    //   // Add other Azure AD parameters as needed
    // });
    
    const result = await signInWithPopup(auth, provider);
    
    if (!result?.user) {
      throw new Error('Authentication failed - no user data received');
    }
    
    console.log('OIDC popup authentication successful:', {
      uid: result.user.uid,
      email: result.user.email,
      displayName: result.user.displayName,
      providerId: result.providerId
    });
    
    return result.user;
    
  } catch (error: any) {
    console.error('OIDC popup authentication error:', error);
    
    // More specific error handling for popup issues
    if (error.code === 'auth/popup-blocked') {
      throw new Error('Popup was blocked by your browser. Please allow popups for this site and try again.');
    } else if (error.code === 'auth/popup-closed-by-user') {
      throw new Error('Authentication was cancelled. Please try again.');
    } else if (error.code === 'auth/cancelled-popup-request') {
      throw new Error('Another authentication popup is already open. Please close it and try again.');
    } else if (error.code === 'auth/configuration-not-found') {
      throw new Error('OIDC provider configuration not found. Please verify your Firebase project setup.');
    }
    
    throw error;
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
 * Get current user's access token
 */
export async function getAccessToken(): Promise<string | null> {
  const user = auth.currentUser;
  if (!user) return null;
  
  try {
    const idTokenResult = await user.getIdTokenResult();
    return idTokenResult.token;
  } catch (error) {
    console.error('Failed to get access token:', error);
    return null;
  }
}