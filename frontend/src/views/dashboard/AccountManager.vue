<script setup lang="ts">
import { ref, onMounted, computed } from 'vue';
import { useAuthStore } from '@/stores/auth';
import type { User } from '@/types/user';
import axios from 'axios';

// Define the Firebase user type from your API response
interface FirebaseUserRecord {
  uid: string;
  displayName?: string;
  email: string;
  customClaims?: {
    role?: string;
  };
  metadata: {
    creationTime: string;
  };
}

const authStore = useAuthStore();
const users = ref([]);
const showConfirmDialog = ref(false);
const showRoleDialog = ref(false);
const userToDelete = ref(null);
const userToEdit = ref(null);
const selectedRole = ref('');
const snackbar = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success');
const loadingUsers = ref(new Set<string>());

const currentUser = computed(() => authStore.user);

function getApiInstance() {
  return axios.create({
    baseURL: '/api/auth',
    headers: {
      Authorization: `Bearer ${authStore.token}`
    }
  });
}

async function loadUsers() {
  try {
    const api = getApiInstance();
    const res = await api.get<{ users: FirebaseUserRecord[] }>('/users');
    users.value = res.data.users.map((u: FirebaseUserRecord) => ({
      id: u.uid,
      firstName: u.displayName?.split(' ')[0] || '',
      lastName: u.displayName?.split(' ').slice(1).join(' ') || '',
      email: u.email || '',
      role: u.customClaims?.role || 'user',
      createdAt: u.metadata.creationTime || new Date().toISOString()
    }));
  } catch (error) {
    showSnackbar('Failed to load users', 'error');
    console.error('Load users error:', error);
  }
}

function showSnackbar(message: string, color: string = 'success') {
  snackbarText.value = message;
  snackbarColor.value = color;
  snackbar.value = true;
}

function confirmDeleteUser(user: User) {
  userToDelete.value = user;
  showConfirmDialog.value = true;
}

function openRoleDialog(user: User) {
  userToEdit.value = user;
  selectedRole.value = user.role;
  showRoleDialog.value = true;
}

function closeRoleDialog() {
  showRoleDialog.value = false;
  userToEdit.value = null;
  selectedRole.value = '';
}

async function saveUserRole() {
  if (!userToEdit.value || userToEdit.value.role === selectedRole.value) {
    closeRoleDialog();
    return;
  }

  // Add user to loading set
  loadingUsers.value.add(userToEdit.value.id);
  
  try {
    const api = getApiInstance();
    
    // Update the API
    const response = await api.put(`/users/${userToEdit.value.id}`, { 
      role: selectedRole.value 
    });
    
    console.log('Role update response:', response.data);
    
    // Update local state
    const idx = users.value.findIndex((u: User) => u.id === userToEdit.value?.id);
    if (idx !== -1) {
      users.value[idx].role = selectedRole.value;
    }
    
    showSnackbar(`Role updated for ${userToEdit.value.email} to ${selectedRole.value}`);
    closeRoleDialog();
  } catch (error: any) {
    console.error('Role update error:', error);
    
    const errorMessage = error.response?.data?.error || 'Failed to update role';
    showSnackbar(errorMessage, 'error');
  } finally {
    // Remove user from loading set
    loadingUsers.value.delete(userToEdit.value.id);
  }
}

async function deleteUser() {
  if (!userToDelete.value) return;

  if (currentUser.value?.id === userToDelete.value.id) {
    showSnackbar('Cannot delete the currently logged in user', 'error');
    showConfirmDialog.value = false;
    return;
  }

  try {
    const api = getApiInstance();
    await api.delete(`/users/${userToDelete.value.id}`);
    users.value = users.value.filter((u: User) => u.id !== userToDelete.value?.id);
    showSnackbar('User deleted successfully');
  } catch (error) {
    showSnackbar('Failed to delete user', 'error');
    console.error('Delete user error:', error);
  }

  showConfirmDialog.value = false;
}

async function resetAllData() {
  if (!confirm('Are you sure you want to reset all users except yourself? This will delete all other users.')) return;

  try {
    const api = getApiInstance();
    await api.delete('/reset');
    await loadUsers();
    showSnackbar('All users except current have been deleted.');
  } catch (error) {
    showSnackbar('Failed to reset users', 'error');
    console.error('Reset error:', error);
  }
}

onMounted(() => {
  loadUsers();
});
</script>

<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-card>
          <v-card-title class="text-h5">
            SSO Account Manager
            <v-spacer></v-spacer>
            <v-btn color="error" @click="resetAllData">Reset All Users Except Me</v-btn>
          </v-card-title>

          <v-card-subtitle>
            Manage your users and roles.
          </v-card-subtitle>

          <v-card-text>
            <v-alert type="info" class="mb-4">
              <strong>Note:</strong> You are currently logged in as {{ currentUser?.firstName }} {{ currentUser?.lastName }} ({{ currentUser?.email }})
            </v-alert>

            <v-table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Current Role</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="user in users"
                  :key="user.id"
                  :class="{ 'bg-grey-lighten-4': user.id === currentUser?.id }"
                >
                  <td>{{ user.firstName }} {{ user.lastName }}</td>
                  <td>{{ user.email }}</td>
                  <td>
                    <v-chip :color="user.role === 'admin' ? 'error' : user.role === 'moderator' ? 'warning' : 'primary'">
                      {{ user.role }}
                    </v-chip>
                  </td>
                  <td>{{ new Date(user.createdAt).toLocaleString() }}</td>
                  <td>
                    <v-btn
                      color="primary"
                      size="small"
                      @click="openRoleDialog(user)"
                      :disabled="user.id === currentUser?.id || loadingUsers.has(user.id)"
                      :loading="loadingUsers.has(user.id)"
                      class="mr-2"
                    >
                      Manage Role
                    </v-btn>
                    <v-btn
                      icon
                      color="error"
                      size="small"
                      @click="confirmDeleteUser(user)"
                      :disabled="user.id === currentUser?.id"
                    >
                      <v-icon>mdi-delete</v-icon>
                    </v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Delete Confirmation Dialog -->
    <v-dialog v-model="showConfirmDialog" max-width="500px">
      <v-card>
        <v-card-title class="text-h5">Confirm Delete</v-card-title>
        <v-card-text>
          Are you sure you want to delete the user
          {{ userToDelete?.firstName }} {{ userToDelete?.lastName }} ({{ userToDelete?.email }})? This
          action cannot be undone.
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="text" @click="showConfirmDialog = false">Cancel</v-btn>
          <v-btn color="error" variant="flat" @click="deleteUser">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Role Management Dialog -->
    <v-dialog v-model="showRoleDialog" max-width="500px">
      <v-card>
        <v-card-title class="text-h5">
          Manage Role for {{ userToEdit?.firstName }} {{ userToEdit?.lastName }}
        </v-card-title>
        <v-card-text>
          <v-select
            label="Select Role"
            :items="['admin', 'moderator', 'user']"
            v-model="selectedRole"
            outlined
            dense
            class="mt-4"
          ></v-select>
          <v-alert type="info" class="mt-4" v-if="userToEdit?.id === currentUser?.id">
            <strong>Note:</strong> You cannot change your own role.
          </v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer></v-spacer>
          <v-btn color="primary" variant="text" @click="closeRoleDialog">Cancel</v-btn>
          <v-btn 
            color="primary" 
            variant="flat" 
            @click="saveUserRole"
            :disabled="userToEdit?.id === currentUser?.id || selectedRole === userToEdit?.role"
            :loading="loadingUsers.has(userToEdit?.id || '')"
          >
            Save Role
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor">
      {{ snackbarText }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar = false">Close</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>