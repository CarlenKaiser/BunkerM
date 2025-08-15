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

// Create axios instance
const api = axios.create({
    baseURL: config.DYNSEC_API_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    validateStatus: status => status >= 200 && status < 500,
    timeout: 10000
});

// Add Firebase token interceptor
api.interceptors.request.use(
    async (config) => {
        const auth = getAuth();
        const user = auth.currentUser;
        
        if (user) {
            const token = await user.getIdToken();
            config.headers.Authorization = `Bearer ${token}`;
        }
        
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// Add response interceptor
api.interceptors.response.use(
    response => response,
    error => {
        console.error('API Error:', {
            message: error.message,
            config: error.config,
            status: error.response?.status,
            data: error.response?.data
        });
        
        // Handle 401 Unauthorized (token expired)
        if (error.response?.status === 401) {
            // Add your token refresh logic here
            console.error("Authentication expired, please re-login");
        }
        
        return Promise.reject(error);
    }
);

export const mqttService = {

  async getClients() {
    const response = await api.get('/clients');
    return response.data.clients.split('\n').filter(Boolean).map(username => ({ username }));
  },

  async getClient(username) {
    const response = await api.get(`/clients/${username}`);
    //console.log('Get client details response:', response);
    return response.data;
  },


  //############## Client management service #########################//
  async createClient({ username, password }) {
    const response = await api.post('/clients', {
      username: username,
      password: password
    });
    //console.log(response);
    return response.data;
  },


  async deleteClient(username) {
    const response = await api.delete(`/clients/${username}`);
    //console.log(response);
    return response.data;
  },



  async updateClient({ username, password }) {
    const response = await api.put(`/clients/${username}`, {
      username: username,
      password: password
    });
    //console.log(response);
    return response.data;
  },


  async addClientToGroup(groupName, username, priority = null) {
    const data = priority ? { username, priority } : { username };
    const response = await api.post(`/groups/${groupName}/clients`, data);
    //console.log('Add client to group response:', response);
    return response.data;
  },

  async removeClientFromGroup(groupName, username) {
    const response = await api.delete(`/groups/${groupName}/clients/${username}`);
    //console.log('Remove client from group response:', response);
    return response.data;
  },

  //############## Role management service #########################//

  // Create Role
  async createRole(name) {
    const response = await api.post('/roles', {
      name: name
    });
    //console.log('Create role response:', response);
    return response.data;
  },

  // List Roles
  async getRoles() {
    const response = await api.get('/roles');
    //console.log('Get roles response:', response);
    // Split the string into array and map to objects
    return response.data.roles.split('\n').filter(Boolean).map(name => ({ name }));
  },

  // Get Role Details
  async getRole(name) {
    const response = await api.get(`/roles/${name}`);
    //console.log('Get role details response:', response);
    return response.data;
  },

  // Delete Role
  async deleteRole(name) {
    const response = await api.delete(`/roles/${name}`);
    //console.log('Delete role response:', response);
    return response.data;
  },

  //############## Group management service #########################//

  // Create Group
  async createGroup(name) {
    const response = await api.post('api/groups', {
      name: name
    });
    //console.log('Create group response:', response);
    return response.data;
  },

  // List Groups
  async getGroups() {
    const response = await api.get('api/groups');
    //console.log('Get groups response:', response);
    return response.data;
  },



  // Get Group Details
  async getGroup(name) {
    const response = await api.get(`api/groups/${name}`);
    //console.log('Get group details response:', response);
    return response.data;
  },

  // Delete Group
  async deleteGroup(name) {
    const response = await api.delete(`api/groups/${name}`);
    //console.log('Delete group response:', response);
    return response.data;
  },

  //############## Role assigements management service #########################//

  // Role Assignment Methods
  async addRoleToClient(username, roleName) {
    const response = await api.post(`/clients/${username}/roles`, {
      role_name: roleName
    });
    //console.log('Add role to client response:', response);
    return response.data;
  },

  async removeRoleFromClient(username, roleName) {
    const response = await api.delete(`/clients/${username}/roles/${roleName}`);
    //console.log('Remove role from client response:', response);
    return response.data;
  },

  async addRoleToGroup(groupName, roleName) {
    const response = await api.post(`api/groups/${groupName}/roles`, {
      role_name: roleName
    });
    //console.log('Add role to group response:', response);
    return response.data;
  },

  async removeRoleFromGroup(groupName, roleName) {
    const response = await api.delete(`api/groups/${groupName}/roles/${roleName}`);
    //console.log('Remove role from group response:', response);
    return response.data;
  },


  //############## ACL MQTT Topic to Role assigements management service #########################//

  // In mqtt.service.js
  async addRoleACL(roleName, aclData) {
    //console.log('Adding ACL:', { roleName, aclData }); // Debug log
    const response = await api.post(`/roles/${roleName}/acls`, {
      topic: aclData.topic,
      aclType: aclData.aclType,
      permission: aclData.permission
    });
    //console.log('ACL response:', response); // Debug log
    return response.data;
  },

  /* async removeRoleACL(roleName, aclType, topic) {
    const response = await api.delete(`/roles/${roleName}/acls`, {
      params: {
        acl_type: aclType,
        topic
      });
    //console.log('Remove role ACL response:', response);
    return response.data;
  },
   */

  async removeRoleACL(roleName, aclType, topic) {
    const encodedTopic = encodeURIComponent(topic);
    const response = await api.delete(
      `/roles/${roleName}/acls?acl_type=${aclType}&topic=${encodedTopic}`);
    //console.log('Remove role ACL response:', response);
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
  // Restarting Mosquitto
async restartMosquitto() {
  try {
    const response = await api.post('/dynsec/restart-mosquitto', {});
    return response.data;
  } catch (error) {
    console.error('Error restarting Mosquitto broker:', error);
    throw error;
  }
},


  // Get Mosquitto configuration
async getMosquittoConfig() {
  try {
    const response = await api.get('/config/mosquitto-config');
    return response.data;
  } catch (error) {
    console.error('Error fetching Mosquitto configuration:', error);
    throw error;
  }
},

  // Save Mosquitto configuration
async saveMosquittoConfig(configData) {
  try {
    const response = await api.post('/config/mosquitto-config', configData);
    return response.data;
  } catch (error) {
    console.error('Error saving Mosquitto configuration:', error);
    throw error;
  }
},

  // Reset Mosquitto configuration to default
async resetMosquittoConfig() {
  try {
    const response = await api.post('/config/reset-mosquitto-config', {});
    return response.data;
  } catch (error) {
    console.error('Error resetting Mosquitto configuration:', error);
    throw error;
  }
},

  // Remove a listener from Mosquitto configuration
async removeMosquittoListener(port) {
  try {
    const response = await api.post('/config/remove-mosquitto-listener', 
      { port: port });
    return response.data;
  } catch (error) {
    console.error('Error removing Mosquitto listener:', error);
    throw error;
  }
},

// Get the dynamic security JSON configuration
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

// Import a dynamic security JSON file
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

// Reset dynamic security JSON to default
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
    // Make the request with responseType blob to handle binary data
    const response = await api.get('/config/export-dynsec-json', {
      responseType: 'blob' // Important for file downloads
    });
    
    console.log("Export response received:", response.status, response.headers);
    
    // Check if we got successful response
    if (response.status !== 200) {
      throw new Error(`Export failed with status: ${response.status}`);
    }
    
    // Validate the blob type - should be application/json
    const contentType = response.headers['content-type'];
    if (contentType && !contentType.includes('application/json')) {
      console.warn(`Unexpected content type: ${contentType}`);
    }
    
    // Create a URL for the blob
    const url = window.URL.createObjectURL(new Blob([response.data]));
    
    // Extract filename from Content-Disposition header if available
    let filename = 'dynamic-security-export.json';
    const contentDisposition = response.headers['content-disposition'];
    console.log("Content-Disposition:", contentDisposition);
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      if (filenameMatch && filenameMatch.length > 1) {
        filename = filenameMatch[1];
      }
    } else {
      // Use a timestamp if no filename provided
      filename = `dynamic-security-export-${new Date().toISOString().replace(/[:.]/g, '-')}.json`;
    }
    
    console.log("Using filename:", filename);
    
    // Create a link element and trigger download
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    
    // Clean up
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
    
    return { success: true, message: 'Dynamic security configuration exported successfully' };
  } catch (error) {
    console.error('Error exporting dynamic security JSON:', error);
    // Better error reporting
    let errorMessage = 'Failed to export dynamic security configuration';
    
    if (error.response) {
      // Server responded with an error
      errorMessage = `Server error: ${error.response.status} - ${error.response.statusText}`;
      console.error('Error response:', error.response);
    } else if (error.request) {
      // Request made but no response received
      errorMessage = 'No response received from server. Please check your network connection.';
    }
    
    return { 
      success: false, 
      message: errorMessage
    };
  }
}


};