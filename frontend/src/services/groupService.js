/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
// services/groupService.js
import { api } from './api';
import { generateNonce } from '../utils/security';

// Helper function to get current timestamp in seconds
const getCurrentTimestamp = () => Math.floor(Date.now() / 1000);

export const groupService = {
  async getGroups() {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.get('/groups', {
        params: {
          nonce,
          timestamp
        }
      });
      
      // Handle both array and string response formats
      let groupsList;
      if (Array.isArray(response.data)) {
        groupsList = response.data;
      } else if (typeof response.data === 'string') {
        groupsList = response.data.split('\n').filter(Boolean);
      } else {
        console.warn('Unexpected groups data format:', response.data);
        return [];
      }
      
      return groupsList.map(name => ({ name }));
    } catch (error) {
      console.error('Error fetching groups:', error);
      return [];
    }
  },

  async createGroup(name) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.post('/groups', 
        { name },
        {
          params: {
            nonce,
            timestamp
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error creating group:', error);
      throw error;
    }
  },

  async deleteGroup(name) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/groups/${name}`, {
        params: {
          nonce,
          timestamp
        }
      });
      return response.data;
    } catch (error) {
      console.error('Error deleting group:', error);
      throw error;
    }
  },

  async addRoleToGroup(groupName, roleName) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.post(
        `/groups/${groupName}/roles`,
        { role_name: roleName },
        {
          params: {
            nonce,
            timestamp
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error adding role to group:', error);
      throw error;
    }
  },

  async addClientToGroup(groupName, username, priority = null) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const data = { username };
      if (priority !== null) {
        data.priority = priority;
      }
      
      const response = await api.post(
        `/groups/${groupName}/clients`,
        data,
        {
          params: {
            nonce,
            timestamp
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error adding client to group:', error);
      throw error;
    }
  },
  
  async removeClientFromGroup(groupName, username) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(
        `/groups/${groupName}/clients/${username}`,
        {
          params: {
            nonce,
            timestamp
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error removing client from group:', error);
      throw error;
    }
  },

  async removeRoleFromGroup(groupName, roleName) {
    try {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(
        `/groups/${groupName}/roles/${roleName}`,
        {
          params: {
            nonce,
            timestamp
          }
        }
      );
      return response.data;
    } catch (error) {
      console.error('Error removing role from group:', error);
      throw error;
    }
  }
};