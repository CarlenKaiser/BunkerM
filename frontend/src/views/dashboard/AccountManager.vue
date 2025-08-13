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
const users = ref<User[]>([]);
const showConfirmDialog = ref(false);
const userToDelete = ref<User | null>(null);
const snackbar = ref(false);
const snackbarText = ref('');
const snackbarColor = ref('success');

const currentUser = computed(() => authStore.user);

const api = axios.create({
  baseURL: '/api/auth',
  headers: {
    Authorization: `Bearer ${authStore.token}`
  }
});

async function loadUsers() {
  try {
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
    console.error(error);
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

async function deleteUser() {
  if (!userToDelete.value) return;

  if (currentUser.value?.id === userToDelete.value.id) {
    showSnackbar('Cannot delete the currently logged in user', 'error');
    showConfirmDialog.value = false;
    return;
  }

  try {
    await api.delete(`/users/${userToDelete.value.id}`);
    users.value = users.value.filter((u: User) => u.id !== userToDelete.value?.id);
    showSnackbar('User deleted successfully');
  } catch (error) {
    showSnackbar('Failed to delete user', 'error');
    console.error(error);
  }

  showConfirmDialog.value = false;
}

async function updateUserRole(user: User, newRole: string) {
  if (user.role === newRole) return;

  try {
    await api.put(`/users/${user.id}`, { role: newRole });

    const idx = users.value.findIndex((u: User) => u.id === user.id);
    if (idx !== -1) {
      users.value[idx].role = newRole;
    }
    showSnackbar(`Role updated for ${user.email} to ${newRole}`);
  } catch (error) {
    showSnackbar('Failed to update role', 'error');
    console.error(error);
  }
}

async function resetAllData() {
  if (!confirm('Are you sure you want to reset all users except yourself? This will delete all other users.')) return;

  try {
    await api.delete('/reset');
    await loadUsers();
    showSnackbar('All users except current have been deleted.');
  } catch (error) {
    showSnackbar('Failed to reset users', 'error');
    console.error(error);
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
                  <th>Role</th>
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
                    <v-select
                      :items="['admin', 'user', 'moderator']"
                      v-model="user.role"
                      dense
                      outlined
                      hide-details
                      :disabled="user.id === currentUser?.id"
                      @update:model-value="(newRole: string) => updateUserRole(user, newRole)"
                    ></v-select>
                  </td>
                  <td>{{ new Date(user.createdAt).toLocaleString() }}</td>
                  <td>
                    <v-btn
                      icon
                      color="error"
                      size="small"
                      @click="confirmDeleteUser(user)"
                      :disabled="user.id === currentUser?.id"
                    >
                      <TrashIcon stroke-width="1.5" size="22" />
                    </v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Confirmation Dialog -->
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

    <!-- Snackbar -->
    <v-snackbar v-model="snackbar" :color="snackbarColor">
      {{ snackbarText }}
      <template v-slot:actions>
        <v-btn variant="text" @click="snackbar = false">Close</v-btn>
      </template>
    </v-snackbar>
  </v-container>
</template>