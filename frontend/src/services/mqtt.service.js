/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
import axios from 'axios';
import { getRuntimeConfig } from '@/config/runtime';
import { getAuth, getIdToken } from 'firebase/auth';

const config = getRuntimeConfig();

// Create axios instance with the custom configuration
const api = axios.create({
    baseURL: config.DYNSEC_API_URL,
    headers: {
        'Content-Type': 'application/json'
    },
    // Additional axios config for better error handling
    validateStatus: status => status >= 200 && status < 500,
    timeout: 10000
});

// Add request interceptor to inject Firebase ID token
api.interceptors.request.use(async (config) => {
    const auth = getAuth();
    const user = auth.currentUser;
    
    if (user) {
        const token = await getIdToken(user);
        config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
}, (error) => {
    return Promise.reject(error);
});

// Add response interceptor for better error handling
api.interceptors.response.use(
    response => response,
    error => {
        console.error('API Error:', {
            message: error.message,
            config: error.config,
            status: error.response?.status,
            data: error.response?.data
        });
        return Promise.reject(error);
    }
);

export const mqttService = {

  async getClients() {
    try {
      const response = await api.get('/clients');
      
      // Debug logging - check what we're actually getting
      console.log('Raw API response:', response);
      console.log('Response data:', response.data);
      console.log('Response data type:', typeof response.data);
      console.log('Response data keys:', Object.keys(response.data || {}));
      
      // Check if clients property exists
      if (!response.data.clients) {
        console.warn('No clients property in response data');
        return [];
      }
      
      console.log('Clients string:', response.data.clients);
      console.log('Clients string type:', typeof response.data.clients);
      
      // Original parsing logic
      const clientsList = response.data.clients.split('\n').filter(Boolean).map(username => ({ username }));
      console.log('Parsed clients list:', clientsList);
      
      return clientsList;
    } catch (error) {
      console.error('Error in getClients:', error);
      return [];
    }
  },

  async getClient(username) {
    const response = await api.get(`/clients/${username}`);
    return response.data;
  },

  //############## Client management service #########################//
  async createClient({ username, password }) {
    const response = await api.post('/clients', {
      username: username,
      password: password
    });
    return response.data;
  },

  async deleteClient(username) {
    const response = await api.delete(`/clients/${username}`);
    return response.data;
  },

  async updateClient({ username, password }) {
    const response = await api.put(`/clients/${username}`, {
      username: username,
      password: password
    });
    return response.data;
  },

  async addClientToGroup(groupName, username, priority = null) {
    const data = priority ? { username, priority } : { username };
    const response = await api.post(`/groups/${groupName}/clients`, data);
    return response.data;
  },

  async removeClientFromGroup(groupName, username) {
    const response = await api.delete(`/groups/${groupName}/clients/${username}`);
    return response.data;
  },

  //############## Role management service #########################//
  async createRole(name) {
    const response = await api.post('/roles', {
      name: name
    });
    return response.data;
  },

  async getRoles() {
    const response = await api.get('/roles');
    return response.data.roles.split('\n').filter(Boolean).map(name => ({ name }));
  },

  async getRole(name) {
    const response = await api.get(`/roles/${name}`);
    return response.data;
  },

  async deleteRole(name) {
    const response = await api.delete(`/roles/${name}`);
    return response.data;
  },

  //############## Group management service #########################//
  async createGroup(name) {
    const response = await api.post('/groups', {
      name: name
    });
    return response.data;
  },

  async getGroups() {
    const response = await api.get('/groups');
    return response.data.groups.split('\n').filter(Boolean).map(name => ({ name }));
  },

  async getGroup(name) {
    const response = await api.get(`/groups/${name}`);
    return response.data;
  },

  async deleteGroup(name) {
    const response = await api.delete(`/groups/${name}`);
    return response.data;
  },

  //############## Role assigements management service #########################//
  async addRoleToClient(username, roleName) {
    const response = await api.post(`/clients/${username}/roles`, {
      role_name: roleName
    });
    return response.data;
  },

  async removeRoleFromClient(username, roleName) {
    const response = await api.delete(`/clients/${username}/roles/${roleName}`);
    return response.data;
  },

  async addRoleToGroup(groupName, roleName) {
    const response = await api.post(`/groups/${groupName}/roles`, {
      role_name: roleName
    });
    return response.data;
  },

  async removeRoleFromGroup(groupName, roleName) {
    const response = await api.delete(`/groups/${groupName}/roles/${roleName}`);
    return response.data;
  },

  //############## ACL MQTT Topic to Role assigements management service #########################//
  async addRoleACL(roleName, aclData) {
    const response = await api.post(`/roles/${roleName}/acls`, {
      topic: aclData.topic,
      aclType: aclData.aclType,
      permission: aclData.permission
    });
    return response.data;
  },

  async removeRoleACL(roleName, aclType, topic) {
    const encodedTopic = encodeURIComponent(topic);
    const response = await api.delete(
      `/roles/${roleName}/acls?acl_type=${aclType}&topic=${encodedTopic}`
    );
    return response.data;
  },

  async importPasswordFile(formData) {
    try {
      const response = await api.post('/dynsec/import-password-file', formData);
      return response.data;
    } catch (error) {
      console.error('Error importing password file:', error);
      throw error;
    }
  },

  async getPasswordFileStatus() {
    try {
      const response = await api.get('/dynsec/password-file-status');
      return response.data;
    } catch (error) {
      console.error('Error fetching password file status:', error);
      throw error;
    }
  },
  
  async restartMosquitto() {
    try {
      const response = await api.post('/dynsec/restart-mosquitto', {});
      return response.data;
    } catch (error) {
      console.error('Error restarting Mosquitto broker:', error);
      throw error;
    }
  },

  async getMosquittoConfig() {
    try {
      const response = await api.get('/config/mosquitto-config');
      return response.data;
    } catch (error) {
      console.error('Error fetching Mosquitto configuration:', error);
      throw error;
    }
  },

  async saveMosquittoConfig(configData) {
    try {
      const response = await api.post('/config/mosquitto-config', configData);
      return response.data;
    } catch (error) {
      console.error('Error saving Mosquitto configuration:', error);
      throw error;
    }
  },

  async resetMosquittoConfig() {
    try {
      const response = await api.post('/config/reset-mosquitto-config', {});
      return response.data;
    } catch (error) {
      console.error('Error resetting Mosquitto configuration:', error);
      throw error;
    }
  },

  async removeMosquittoListener(port) {
    try {
      const response = await api.post('/config/remove-mosquitto-listener', { port: port });
      return response.data;
    } catch (error) {
      console.error('Error removing Mosquitto listener:', error);
      throw error;
    }
  },

  async getDynSecJson() {
    try {
      const response = await api.get('/config/dynsec-json');
      return response.data;
    } catch (error) {
      console.error('Error getting dynamic security JSON:', error);
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to get dynamic security configuration' 
      };
    }
  },

  async importDynSecJson(formData) {
    try {
      const response = await api.post('/config/import-dynsec-json', formData);
      return response.data;
    } catch (error) {
      console.error('Error importing dynamic security JSON:', error);
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to import dynamic security configuration' 
      };
    }
  },

  async resetDynSecJson() {
    try {
      const response = await api.post('/config/reset-dynsec-json', {});
      return response.data;
    } catch (error) {
      console.error('Error resetting dynamic security JSON:', error);
      return { 
        success: false, 
        message: error.response?.data?.detail || 'Failed to reset dynamic security configuration' 
      };
    }
  },

  async exportDynSecJson() {
    try {
      console.log("Starting export process...");
      const response = await api.get('/config/export-dynsec-json', {
        responseType: 'blob'
      });
      
      console.log("Export response received:", response.status, response.headers);
      
      if (response.status !== 200) {
        throw new Error(`Export failed with status: ${response.status}`);
      }
      
      const contentType = response.headers['content-type'];
      if (contentType && !contentType.includes('application/json')) {
        console.warn(`Unexpected content type: ${contentType}`);
      }
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      
      let filename = 'dynamic-security-export.json';
      const contentDisposition = response.headers['content-disposition'];
      console.log("Content-Disposition:", contentDisposition);
      
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
        if (filenameMatch && filenameMatch.length > 1) {
          filename = filenameMatch[1];
        }
      } else {
        filename = `dynamic-security-export-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
      }
      
      console.log("Using filename:", filename);
      
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      return { success: true, message: 'Dynamic security configuration exported successfully' };
    } catch (error) {
      console.error('Error exporting dynamic security JSON:', error);
      let errorMessage = 'Failed to export dynamic security configuration';
      
      if (error.response) {
        errorMessage = `Server error: ${error.response.status} - ${error.response.statusText}`;
        console.error('Error response:', error.response);
      } else if (error.request) {
        errorMessage = 'No response received from server. Please check your network connection.';
      }
      
      return { 
        success: false, 
        message: errorMessage
      };
    }
  }
};