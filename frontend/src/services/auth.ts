import { auth } from '@/services/firebase';
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

// Your app User type
export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  createdAt: string;
}

// Map Firebase user to your User type
export function mapFirebaseUser(user: FirebaseUser): User {
  return {
    id: user.uid,
    email: user.email || '',
    firstName: user.displayName?.split(' ')[0] || '',
    lastName: user.displayName?.split(' ').slice(1).join(' ') || '',
    createdAt: user.metadata.creationTime || ''
  };
}

// Register a user, returns { user, firebaseUser }
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

// Login user, returns { user, firebaseUser }
export async function loginUser(
  email: string,
  password: string
): Promise<{ user: User; firebaseUser: FirebaseUser }> {
  const cred = await signInWithEmailAndPassword(auth, email, password);
  return { user: mapFirebaseUser(cred.user), firebaseUser: cred.user };
}

// Login with Microsoft SSO, returns { user, firebaseUser }
export async function loginWithMicrosoft(): Promise<{ user: User; firebaseUser: FirebaseUser }> {
  const provider = new OAuthProvider('microsoft.com');
  provider.setCustomParameters({ prompt: 'select_account' });
  const cred = await signInWithPopup(auth, provider);
  return { user: mapFirebaseUser(cred.user), firebaseUser: cred.user };
}

// Logout user
export async function logoutUser() {
  await signOut(auth);
}

// Subscribe to auth changes
export function onAuthChange(
  callback: (user: User | null) => void
) {
  return onAuthStateChanged(auth, (firebaseUser) => {
    if (firebaseUser) callback(mapFirebaseUser(firebaseUser));
    else callback(null);
  });
}
