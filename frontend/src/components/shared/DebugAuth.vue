<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { auth } from '@/firebase';
import { onAuthStateChanged } from 'firebase/auth';
import { loginWithMicrosoft, loginWithOIDCPopup } from '@/services/auth';

const debugInfo = ref<any[]>([]);
const currentUser = ref<any>(null);
const isLoading = ref(false);

function addDebugInfo(message: string, data?: any) {
  debugInfo.value.push({
    timestamp: new Date().toISOString(),
    message,
    data: data ? JSON.stringify(data, null, 2) : null
  });
  console.log(message, data);
}

function clearDebugInfo() {
  debugInfo.value = [];
}

async function testPopupLogin() {
  isLoading.value = true;
  try {
    addDebugInfo('Starting OIDC popup login test...');
    const user = await loginWithMicrosoft();
    addDebugInfo('OIDC popup login successful', {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      emailVerified: user.emailVerified,
      providerData: user.providerData
    });
  } catch (error: any) {
    addDebugInfo('OIDC popup login failed', {
      code: error.code,
      message: error.message
    });
  } finally {
    isLoading.value = false;
  }
}

async function testAlternativePopupLogin() {
  isLoading.value = true;
  try {
    addDebugInfo('Starting alternative OIDC popup login test...');
    const user = await loginWithOIDCPopup();
    addDebugInfo('Alternative OIDC popup login successful', {
      uid: user.uid,
      email: user.email,
      displayName: user.displayName,
      emailVerified: user.emailVerified,
      providerData: user.providerData
    });
  } catch (error: any) {
    addDebugInfo('Alternative OIDC popup login failed', {
      code: error.code,
      message: error.message
    });
  } finally {
    isLoading.value = false;
  }
}

function checkEnvironment() {
  const env = {
    url: window.location.href,
    origin: window.location.origin,
    protocol: window.location.protocol,
    hostname: window.location.hostname,
    userAgent: navigator.userAgent,
    cookiesEnabled: navigator.cookieEnabled,
    localStorage: typeof localStorage !== 'undefined',
    sessionStorage: typeof sessionStorage !== 'undefined',
    popupBlocked: checkPopupBlocked(),
    firebaseConfig: {
      projectId: auth.app.options.projectId,
      authDomain: auth.app.options.authDomain,
      apiKey: auth.app.options.apiKey ? 'Present' : 'Missing'
    }
  };
  
  addDebugInfo('Environment check', env);
}

function checkPopupBlocked(): boolean {
  try {
    const popup = window.open('', '_blank', 'width=1,height=1');
    if (popup) {
      popup.close();
      return false;
    } else {
      return true;
    }
  } catch (e) {
    return true;
  }
}

onMounted(async () => {
  addDebugInfo('Debug component mounted');
  
  // Check environment
  checkEnvironment();
  
  // Listen for auth state changes
  onAuthStateChanged(auth, async (user) => {
    currentUser.value = user;
    if (user) {
      try {
        const idTokenResult = await user.getIdTokenResult();
        addDebugInfo('User signed in', {
          uid: user.uid,
          email: user.email,
          displayName: user.displayName,
          emailVerified: user.emailVerified,
          providerId: user.providerData[0]?.providerId,
          claims: idTokenResult.claims,
          authTime: idTokenResult.authTime,
          issuedAtTime: idTokenResult.issuedAtTime,
          expirationTime: idTokenResult.expirationTime
        });
      } catch (error) {
        addDebugInfo('Error getting ID token result', error);
      }
    } else {
      addDebugInfo('User signed out');
    }
  });
  
  // Check current URL for any parameters (shouldn't be needed for popup)
  const urlParams = new URLSearchParams(window.location.search);
  const urlFragment = new URLSearchParams(window.location.hash.substring(1));
  
  const allParams = {
    searchParams: Object.fromEntries(urlParams.entries()),
    hashParams: Object.fromEntries(urlFragment.entries())
  };
  
  if (Object.keys(allParams.searchParams).length > 0 || Object.keys(allParams.hashParams).length > 0) {
    addDebugInfo('URL contains parameters (unexpected for popup auth)', allParams);
  }
  
  // Check for specific error parameters (shouldn't occur with popup)
  const error = urlParams.get('error') || urlFragment.get('error');
  const errorDescription = urlParams.get('error_description') || urlFragment.get('error_description');
  
  if (error) {
    addDebugInfo('URL contains error parameters (unexpected for popup auth)', {
      error,
      errorDescription,
      errorUri: urlParams.get('error_uri') || urlFragment.get('error_uri'),
      state: urlParams.get('state') || urlFragment.get('state')
    });
  }
  
  // Check browser storage
  try {
    const keys = Object.keys(localStorage);
    const firebaseKeys = keys.filter(key => 
      key.startsWith('firebase:') || 
      key.startsWith('CognitoIdentityServiceProvider') ||
      key.startsWith('amplify-')
    );
    
    if (firebaseKeys.length > 0) {
      addDebugInfo('Found auth-related localStorage keys', firebaseKeys);
    }
  } catch (error) {
    addDebugInfo('Could not access localStorage', error);
  }
});
</script>

<template>
  <v-container>
    <v-card>
      <v-card-title class="d-flex justify-space-between align-center">
        <span>Auth Debug Information (OIDC Popup Mode)</span>
        <v-btn 
          variant="outlined" 
          size="small" 
          @click="clearDebugInfo"
        >
          Clear Log
        </v-btn>
      </v-card-title>
      
      <v-card-text>
        <!-- Test Buttons -->
        <div class="mb-4">
          <v-btn 
            color="primary" 
            class="mr-2"
            :loading="isLoading"
            @click="testPopupLogin"
          >
            Test OIDC Popup (Main)
          </v-btn>
          
          <v-btn 
            color="secondary" 
            class="mr-2"
            :loading="isLoading"
            @click="testAlternativePopupLogin"
          >
            Test Alternative OIDC Popup
          </v-btn>
          
          <v-btn 
            variant="outlined"
            @click="checkEnvironment"
          >
            Check Environment
          </v-btn>
        </div>
        
        <!-- Popup Status -->
        <v-alert 
          v-if="checkPopupBlocked()" 
          type="warning" 
          class="mb-4"
        >
          ⚠️ Popups appear to be blocked. Please allow popups for this site.
        </v-alert>
        
        <v-divider class="my-4"></v-divider>
        
        <!-- Current User -->
        <div class="mb-4">
          <strong>Current User:</strong>
          <v-card 
            v-if="currentUser" 
            variant="outlined"
            class="mt-2"
          >
            <v-card-text>
              <pre class="text-caption">{{ JSON.stringify(currentUser, null, 2) }}</pre>
            </v-card-text>
          </v-card>
          <v-chip v-else color="warning">Not signed in</v-chip>
        </div>
        
        <v-divider class="my-4"></v-divider>
        
        <!-- Debug Log -->
        <div>
          <strong>Debug Log ({{ debugInfo.length }} entries):</strong>
          <div class="mt-2" style="max-height: 500px; overflow-y: auto;">
            <v-card
              v-for="(info, index) in debugInfo.slice().reverse()" 
              :key="`debug-${debugInfo.length - index}`"
              variant="outlined"
              class="mb-2"
            >
              <v-card-text class="py-2">
                <div class="text-caption text-grey-darken-1">
                  {{ info.timestamp }}
                </div>
                <div class="font-weight-bold text-body-2 mt-1">
                  {{ info.message }}
                </div>
                <pre 
                  v-if="info.data" 
                  class="text-caption mt-2 pa-2 bg-grey-lighten-4"
                  style="white-space: pre-wrap; word-break: break-all;"
                >{{ info.data }}</pre>
              </v-card-text>
            </v-card>
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-container>
</template>