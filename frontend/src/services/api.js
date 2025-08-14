/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */

// api.js
import axios from 'axios';
import { getAuth, onAuthStateChanged } from 'firebase/auth';

// Remove any trailing slashes from the base URL
const baseURL = import.meta.env.VITE_DYNSEC_API_URL?.replace(/\/+$/, '');

// Create axios instance
export const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  // timeout: 10000,
  validateStatus: status => status >= 200 && status < 500
});

// Request interceptor to add Firebase ID token
api.interceptors.request.use(
  async (config) => {
    try {
      const currentUser = getAuth().currentUser;
      if (currentUser) {
        // Get the Firebase ID token
        const idToken = await currentUser.getIdToken();
        config.headers.Authorization = `Bearer ${idToken}`;
      }
    } catch (error) {
      console.error('Error getting Firebase ID token:', error);
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle auth errors
api.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // If we get a 401 and haven't already retried
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const currentUser = getAuth().currentUser;
        if (currentUser) {
          // Force refresh the token
          const newToken = await currentUser.getIdToken(true);
          originalRequest.headers.Authorization = `Bearer ${newToken}`;
          
          // Retry the original request
          return api(originalRequest);
        }
      } catch (refreshError) {
        console.error('Error refreshing token:', refreshError);
        // Optionally redirect to login or dispatch logout action
        // window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

// Helper function to check if user is authenticated
export const isAuthenticated = () => {
  return getAuth().currentUser !== null;
};

// Helper function to get current user
export const getCurrentUser = () => {
  return getAuth().currentUser;
};

// Helper function to wait for auth state to be determined
export const waitForAuthState = () => {
  return new Promise((resolve) => {
    const unsubscribe = onAuthStateChanged(getAuth(), (user) => {
      unsubscribe();
      resolve(user);
    });
  });
};