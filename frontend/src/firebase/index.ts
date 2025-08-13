import { initializeApp } from 'firebase/app';
import { getAuth, OAuthProvider, signInWithRedirect, getRedirectResult } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getRuntimeConfig } from '@/config/runtime';

const runtimeConfig = getRuntimeConfig();

const firebaseConfig = {
  apiKey: "AIzaSyCdVR8DrCSdn0ihh-krJwTA0bBJXYN6UVQ",
  authDomain: "auth-temp.bunkerm.cpmfgoperations.com",
  projectId: "cpmfgoperations-bunkerm-prod",
  storageBucket: "cpmfgoperations-bunkerm-prod.appspot.com",
  messagingSenderId: "37053050602",
  appId: "1:37053050602:web:e2551606bc61e71ec07193",
  measurementId: "G-Y401HYVJRY"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);

// Initialize Firebase Auth
const auth = getAuth(app);

// Initialize Firestore database
const db = getFirestore(app);

const oidcProvider = new OAuthProvider('oidc.bunkerm-azuread-single-tenant');
oidcProvider.addScope('openid');
oidcProvider.addScope('profile');
oidcProvider.addScope('email');

/**
 * Starts the OIDC sign-in with redirect flow
 */
function signInWithOIDCRedirect() {
  signInWithRedirect(auth, oidcProvider);
}

/**
 * Checks for and processes the redirect result after coming back from OIDC provider
 */
async function handleRedirectResult() {
  try {
    const result = await getRedirectResult(auth);
    if (result) {
      const user = result.user;
      console.log('User signed in via OIDC redirect:', user);
      return user;
    } else {
      // No redirect result available (not returning from redirect)
      return null;
    }
  } catch (error) {
    console.error('Error handling OIDC redirect result:', error);
    throw error;
  }
}

export { auth, db, signInWithOIDCRedirect, handleRedirectResult };
export const firestore = db;
