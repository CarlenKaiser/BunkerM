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
    try {
      const response = await api.get('/groups');
      
      // Log the complete response for debugging
      console.log('=== GROUPS API DEBUG RESPONSE ===');
      console.log('Response status:', response.status);
      console.log('Response data:', response.data);
      console.log('Response data type:', typeof response.data);
      console.log('Groups property type:', typeof response.data?.groups);
      console.log('Is groups an array?', Array.isArray(response.data?.groups));
      console.log('=================================');
      
      // Check if response is successful
      if (response.status !== 200) {
        throw new Error(`API returned status ${response.status}`);
      }
      
      // Handle different response formats
      if (response.data) {
        const data = response.data;
        
        // Check if groups is already an array (direct array response)
        if (Array.isArray(data.groups)) {
          console.log('Groups is an array with length:', data.groups.length);
          return data.groups.map(name => ({ 
            name: typeof name === 'string' ? name.trim() : name 
          }));
        }
        
        // Check if it's a string that needs splitting
        if (typeof data.groups === 'string') {
          console.log('Groups is a string, splitting...');
          return data.groups.split('\n')
            .filter(Boolean)
            .map(name => ({ name: name.trim() }));
        }
        
        // Handle debug response format (if you update the API)
        if (data.groups_array && Array.isArray(data.groups_array)) {
          console.log('Using groups_array from debug response');
          return data.groups_array.map(name => ({ name: name.trim() }));
        }
        
        // Check if the entire response data is an array
        if (Array.isArray(data)) {
          console.log('Response data itself is an array');
          return data.map(name => ({ 
            name: typeof name === 'string' ? name.trim() : name 
          }));
        }
        
        // Handle case where groups is null, undefined, or empty
        if (data.groups === null || data.groups === undefined || data.groups === '') {
          console.log('Groups is null, undefined, or empty');
          return [];
        }
        
        console.warn('Unexpected groups data format:', data.groups);
        return [];
      }
      
      // Check if the entire response is an array
      if (Array.isArray(response.data)) {
        console.log('Entire response is an array');
        return response.data.map(name => ({ 
          name: typeof name === 'string' ? name.trim() : name 
        }));
      }
      
      console.warn('Unexpected response format, returning empty array');
      return [];
      
    } catch (error) {
      console.error('Error in getGroups:', error);
      
      // Enhanced error logging
      if (error.response) {
        console.error('Server error details:');
        console.error('Status:', error.response.status);
        console.error('Data:', error.response.data);
        console.error('Headers:', error.response.headers);
        
        // If server returned debug info, log it
        if (error.response.data?.command_executed) {
          console.error('Failed command:', error.response.data.command_executed);
          console.error('Command error:', error.response.data.error);
        }
        
        throw new Error(`Server error: ${error.response.status} - ${error.response.data?.detail || error.response.data?.error || error.response.statusText}`);
      } else if (error.request) {
        console.error('No response received:', error.request);
        throw new Error('Network error: No response received from server');
      } else {
        console.error('Request setup error:', error.message);
        throw error;
      }
    }
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