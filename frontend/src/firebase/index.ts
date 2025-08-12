import { initializeApp } from 'firebase/app';
import { getAuth } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';  // <--- import Firestore
import { getRuntimeConfig } from '@/config/runtime';

const runtimeConfig = getRuntimeConfig();

const firebaseConfig = {
  apiKey: "AIzaSyCdVR8DrCSdn0ihh-krJwTA0bBJXYN6UVQ",
  authDomain: "cpmfgoperations-bunkerm-prod.firebaseapp.com",
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

export { auth, db };
export const firestore = getFirestore(app);
