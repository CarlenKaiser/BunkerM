/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */

// services/clientService.js
import { api } from './api';
import { generateNonce } from '../utils/security';

// Helper function to get current timestamp in seconds
const getCurrentTimestamp = () => Math.floor(Date.now() / 1000);

// Enhanced error handling wrapper
const handleApiCall = async (apiCall, operation) => {
  try {
    const response = await apiCall();
    return response.data;
  } catch (error) {
    console.error(`Error in ${operation}:`, {
      message: error.message,
      status: error.response?.status,
      data: error.response?.data,
      operation
    });
    
    // Provide user-friendly error messages
    let userMessage = error.userMessage || error.message;
    if (error.response?.status === 500) {
      userMessage = `Server error during ${operation}. Please check server logs.`;
    } else if (error.response?.status === 401 || error.response?.status === 403) {
      userMessage = 'Authentication failed. Please check your login credentials.';
    }
    
    throw new Error(userMessage);
  }
};

export const clientService = {
  async getClients() {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      console.log('Fetching clients with params:', { nonce, timestamp });
      
      const response = await api.get('/clients', {
        params: { nonce, timestamp }
      });
      
      console.log('Raw clients response:', response.data);
      
      // Handle the response from your server
      const clientsData = response.data.clients;
      
      if (!clientsData) {
        console.warn('No clients data in response');
        return [];
      }
      
      // Handle both string (newline-separated) and array responses
      if (typeof clientsData === 'string') {
        const clientsList = clientsData.split('\n')
          .filter(Boolean)
          .map(username => ({ username: username.trim() }));
        console.log('Parsed clients from string:', clientsList);
        return clientsList;
      }
      
      if (Array.isArray(clientsData)) {
        console.log('Clients already in array format:', clientsData);
        return clientsData.map(item => 
          typeof item === 'string' ? { username: item } : item
        );
      }
      
      console.warn('Unexpected clients data format:', typeof clientsData, clientsData);
      return [];
    }, 'getClients');
  },

  async getClient(username) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.get(`/clients/${username}`, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `getClient(${username})`);
  },

  async createClient({ username, password }) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.post('/clients', 
        { username, password },
        { params: { nonce, timestamp } }
      );
      return response.data;
    }, `createClient(${username})`);
  },

  async updateClient({ username, password }) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.put(`/clients/${username}`, 
        { username, password },
        { params: { nonce, timestamp } }
      );
      return response.data;
    }, `updateClient(${username})`);
  },

  async deleteClient(username) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/clients/${username}`, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `deleteClient(${username})`);
  },

  async enableClient(username) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.put(`/clients/${username}/enable`, {}, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `enableClient(${username})`);
  },

  async disableClient(username) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.put(`/clients/${username}/disable`, {}, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `disableClient(${username})`);
  },

  // Role management methods
  async addRoleToClient(username, roleName) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.post(
        `/clients/${username}/roles`,
        { role_name: roleName },
        { params: { nonce, timestamp } }
      );
      return response.data;
    }, `addRoleToClient(${username}, ${roleName})`);
  },

  async removeRoleFromClient(username, roleName) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/clients/${username}/roles/${roleName}`, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `removeRoleFromClient(${username}, ${roleName})`);
  },

  // Group management methods
  async addClientToGroup(groupName, username, priority = null) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const data = priority ? { username, priority } : { username };
      const response = await api.post(`/groups/${groupName}/clients`, data, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `addClientToGroup(${groupName}, ${username})`);
  },

  async removeClientFromGroup(groupName, username) {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/groups/${groupName}/clients/${username}`, {
        params: { nonce, timestamp }
      });
      return response.data;
    }, `removeClientFromGroup(${groupName}, ${username})`);
  },

  // Connection testing
  async testConnection() {
    return handleApiCall(async () => {
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.get('/test-mosquitto', {
        params: { nonce, timestamp },
        timeout: 5000
      });
      return response.data;
    }, 'testConnection');
  },

  // Utility methods
  async getClientStats() {
    return handleApiCall(async () => {
      const clients = await this.getClients();
      return {
        total: clients.length,
        clients: clients
      };
    }, 'getClientStats');
  },

  // Batch operations
  async createMultipleClients(clientsData) {
    const results = [];
    const errors = [];

    for (const clientData of clientsData) {
      try {
        const result = await this.createClient(clientData);
        results.push({ ...clientData, success: true, result });
      } catch (error) {
        errors.push({ ...clientData, success: false, error: error.message });
      }
    }

    return {
      successful: results,
      failed: errors,
      summary: {
        total: clientsData.length,
        successful: results.length,
        failed: errors.length
      }
    };
  },

  // Validation helpers
  validateClientData(clientData) {
    const errors = [];
    
    if (!clientData.username || clientData.username.trim() === '') {
      errors.push('Username is required');
    }
    
    if (clientData.username && clientData.username.length < 3) {
      errors.push('Username must be at least 3 characters long');
    }
    
    if (!clientData.password || clientData.password.length < 6) {
      errors.push('Password must be at least 6 characters long');
    }
    
    // Check for invalid characters in username
    const invalidChars = /[^a-zA-Z0-9_-]/;
    if (clientData.username && invalidChars.test(clientData.username)) {
      errors.push('Username can only contain letters, numbers, underscores, and hyphens');
    }
    
    return {
      isValid: errors.length === 0,
      errors
    };
  }
};