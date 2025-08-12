import { auth } from '@/firebase';
import {
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  onAuthStateChanged,
  updateProfile,
  User as FirebaseUser,
  OAuthProvider
} from 'firebase/auth';

/**
 * Your app User type
 */
export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}

/**
 * Map Firebase user to your User type
 */
export function mapFirebaseUser(user: FirebaseUser): User {
  return {
    id: user.uid,
    email: user.email || '',
    firstName: user.displayName?.split(' ')[0] || '',
    lastName: user.displayName?.split(' ').slice(1).join(' ') || '',
    createdAt: user.metadata.creationTime || ''
  };
}

/**
 * Hash a password using a secure hashing algorithm
 * @param password The plain text password to hash
 * @returns A promise that resolves to the hashed password
 */
export async function hashPassword(password: string): Promise<string> {
  try {
    // First try the standard Web Crypto API
    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(password);
      const hash = await crypto.subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(hash))
        .map(b => b.toString(16).padStart(2, '0'))
        .join('');
    } catch (cryptoError) {
      console.warn('Web Crypto API failed, falling back to simple hash:', cryptoError);

      // Simple fallback hash function for browsers with restricted Web Crypto API (like Safari)
      let hash = 0;
      for (let i = 0; i < password.length; i++) {
        const char = password.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
      }

      // Convert to hex string and add salt
      const salt = 'bunkerM' + new Date().getFullYear();
      const hashStr = Math.abs(hash).toString(16).padStart(8, '0');
      const saltedHash = hashStr + salt;

      // Double hash with a different algorithm to increase security
      let secondHash = 0;
      for (let i = 0; i < saltedHash.length; i++) {
        const char = saltedHash.charCodeAt(i);
        secondHash = ((secondHash >> 5) + secondHash) + char;
        secondHash = secondHash & secondHash;
      }

      return Math.abs(secondHash).toString(16).padStart(16, '0') + hashStr;
    }
  } catch (error) {
    console.error('Error hashing password:', error);
    throw new Error('Failed to hash password');
  }
}

/**
 * Verify a password against its hash
 * @param password The plain text password to verify
 * @param hash The hashed password to verify against
 * @returns A promise that resolves to true if the password matches, false otherwise
 */
export async function verifyPassword(password: string, hash: string): Promise<boolean> {
  try {
    const hashedPassword = await hashPassword(password);
    return hashedPassword === hash;
  } catch (error) {
    console.error('Error verifying password:', error);
    throw new Error('Failed to verify password');
  }
}

/**
 * Register a user, returns { user, firebaseUser }
 */
export async function registerUser(
  email: string,
  password: string,
  firstName?: string,
  lastName?: string
): Promise<{ user: User; firebaseUser: FirebaseUser }> {
  const cred = await createUserWithEmailAndPassword(auth, email, password);
  if (firstName || lastName) {
    await updateProfile(cred.user, {
      displayName: `${firstName || ''} ${lastName || ''}`.trim()
    });
  }
  return { user: mapFirebaseUser(cred.user), firebaseUser: cred.user };
}

/**
 * Login user, returns { user, firebaseUser }
 */
export async function loginUser(
  email: string,
  password: string
): Promise<{ user: User; firebaseUser: FirebaseUser }> {
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return { user: mapFirebaseUser(cred.user), firebaseUser: cred.user };
}

/**
 * Login with Microsoft SSO, returns { user, firebaseUser }
 */
export async function loginWithMicrosoft(): Promise<{ user: User; firebaseUser: FirebaseUser }> {
  const provider = new OAuthProvider('microsoft.com');
  provider.setCustomParameters({ prompt: 'select_account' });
  const cred = await signInWithPopup(auth, provider);
  return { user: mapFirebaseUser(cred.user), firebaseUser: cred.user };
}

/**
 * Logout user
 */
export async function logoutUser() {
  await signOut(auth);
}

/**
 * Subscribe to auth changes
 */
export function onAuthChange(
  callback: (user: User | null) => void
) {
  return onAuthStateChanged(auth, (firebaseUser) => {
    if (firebaseUser) callback(mapFirebaseUser(firebaseUser));
    else callback(null);
  });
}
