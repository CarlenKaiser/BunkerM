/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
// services/groupService.js
import { api } from './api';

export const groupService = {
  async getGroups() {
    
    const response = await api.get('/groups');
    return response.data.groups.split('\n').filter(Boolean).map(name => ({ name }));
  },

  async getGroup(name) {
    
    const response = await api.get(`/groups/${name}`);
    return response.data;
  },

  async createGroup(name) {
    
    const response = await api.post('/groups', 
      { name },
    );
    return response.data;
  },

  async deleteGroup(name) {
    
    const response = await api.delete(`/groups/${name}`);
    return response.data;
  },

  async addRoleToGroup(groupName, roleName) {
    
    const response = await api.post(
      `/groups/${groupName}/roles`,
      { role_name: roleName },
    );
    return response.data;
  },

  async addClientToGroup(groupName, username, priority = null) {
    
    // Validate inputs
    if (!groupName || !username) {
      throw new Error('Group name and username are required');
    }
  
    const data = { username };
    if (priority !== null && !isNaN(priority)) {
      data.priority = priority;
    }
  
    const response = await api.post(
      `/groups/${groupName}/clients`,
      data,
    );
  
    return response.data;
  },
  
  async removeClientFromGroup(groupName, username) {
    
    const response = await api.delete(
      `/groups/${groupName}/clients/${username}`,
    );
    return response.data;
  },

  async removeRoleFromGroup(groupName, roleName) {
    
    const response = await api.delete(
      `/groups/${groupName}/roles/${roleName}`,
    );
    return response.data;
  }
};