/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
// services/groupService.js
import { api } from './api';
import { getAuth, getIdToken } from 'firebase/auth';

export const groupService = {
  async getGroups() {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.get('/groups', {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
    return response.data.groups.split('\n').filter(Boolean).map(name => ({ name }));
  },

  async getGroup(name) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.get(`/groups/${name}`, {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
    return response.data;
  },

  async createGroup(name) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.post('/groups', 
      { name },
      {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      }
    );
    return response.data;
  },

  async deleteGroup(name) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.delete(`/groups/${name}`, {
      headers: {
        'Authorization': `Bearer ${idToken}`
      }
    });
    return response.data;
  },

  async addRoleToGroup(groupName, roleName) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.post(
      `/groups/${groupName}/roles`,
      { role_name: roleName },
      {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      }
    );
    return response.data;
  },

  async addClientToGroup(groupName, username, priority = null) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    // Validate inputs
    if (!groupName || !username) {
      throw new Error('Group name and username are required');
    }
  
    const data = { username };
    if (priority !== null && !isNaN(priority)) {
      data.priority = priority;
    }
  
    const idToken = await getIdToken(user);
  
    const response = await api.post(
      `/groups/${groupName}/clients`,
      data,
      {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      }
    );
  
    return response.data;
  },
  
  async removeClientFromGroup(groupName, username) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.delete(
      `/groups/${groupName}/clients/${username}`,
      {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      }
    );
    return response.data;
  },

  async removeRoleFromGroup(groupName, roleName) {
    const auth = getAuth();
    const user = auth.currentUser;
    if (!user) throw new Error('User not authenticated');
    
    const idToken = await getIdToken(user);
    
    const response = await api.delete(
      `/groups/${groupName}/roles/${roleName}`,
      {
        headers: {
          'Authorization': `Bearer ${idToken}`
        }
      }
    );
    return response.data;
  }
};