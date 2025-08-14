/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */

import { api } from './api';
import { generateNonce } from '../utils/security';

// Helper function to get current timestamp in seconds
const getCurrentTimestamp = () => Math.floor(Date.now() / 1000);

// Helper function to parse ACL data from string format
const parseACLData = (aclString) => {
  console.log('[parseACLData] Raw ACL string:', aclString);
  
  if (!aclString || typeof aclString !== 'string') {
    console.log('[parseACLData] No ACL string or invalid format');
    return [];
  }

  const acls = [];
  const lines = aclString.split('\n').filter(line => line.trim());
  
  console.log('[parseACLData] Processing lines:', lines);
  
  for (const line of lines) {
    // Handle different ACL formats that might be returned
    // Example formats:
    // "publishClientSend topic/pattern allow"
    // "subscribePattern topic/+ deny"
    // "publish topic/test allow"
    
    const parts = line.trim().split(/\s+/);
    console.log('[parseACLData] Line parts:', parts);
    
    if (parts.length >= 3) {
      const aclType = parts[0];
      const topic = parts.slice(1, -1).join(' '); // Handle topics with spaces
      const permission = parts[parts.length - 1];
      
      const acl = {
        aclType: aclType,
        topic: topic,
        permission: permission.toLowerCase() === 'allow' ? 'allow' : 'deny'
      };
      
      console.log('[parseACLData] Parsed ACL:', acl);
      acls.push(acl);
    }
  }
  
  console.log('[parseACLData] Final parsed ACLs:', acls);
  return acls;
};

export const roleService = {
  async getRoles() {
    try {
      console.log('[getRoles] Fetching roles...');
      const response = await api.get('/roles');
      console.log('[getRoles] Raw response:', response);
      
      // Handle different response formats
      const roles = response.data.roles || response.data || [];
      console.log('[getRoles] Extracted roles data:', roles);
      
      // If it's already an array, return it mapped
      if (Array.isArray(roles)) {
        const mappedRoles = roles.map(role => typeof role === 'string' ? { name: role } : role);
        console.log('[getRoles] Mapped array roles:', mappedRoles);
        return mappedRoles;
      }
      
      // If it's a string, split it
      if (typeof roles === 'string') {
        const splitRoles = roles.split('\n').filter(Boolean).map(name => ({ name }));
        console.log('[getRoles] Split string roles:', splitRoles);
        return splitRoles;
      }
      
      // Fallback to empty array
      console.log('[getRoles] Fallback to empty array');
      return [];
    } catch (error) {
      console.error('[getRoles] Error:', error);
      throw error;
    }
  },

  async getRole(name) {
    try {
      console.log(`[getRole] Fetching role: ${name}`);
      const response = await api.get(`/roles/${name}`);
      console.log(`[getRole] Raw response for role ${name}:`, response);
      console.log(`[getRole] Response data:`, response.data);
      
      // Handle different response structures
      const roleData = response.data.role || response.data;
      console.log(`[getRole] Extracted role data:`, roleData);
      
      // If roleData is a string, it might contain ACL information
      if (typeof roleData === 'string') {
        console.log(`[getRole] Role data is string, parsing for ACLs...`);
        console.log(`[getRole] Raw role string content:\n${roleData}`);
        
        // Try to parse ACL information from the string
        const acls = parseACLData(roleData);
        
        return {
          name: name,
          acls: acls,
          rawData: roleData // Keep raw data for debugging
        };
      }
      
      // If roleData is an object, look for ACL properties
      if (typeof roleData === 'object' && roleData !== null) {
        console.log(`[getRole] Role data is object:`, roleData);
        console.log(`[getRole] Object keys:`, Object.keys(roleData));
        
        // Look for various ACL property names
        const possibleAclKeys = ['acls', 'ACLs', 'acl', 'permissions', 'rules'];
        let foundAcls = [];
        
        for (const key of possibleAclKeys) {
          if (roleData[key]) {
            console.log(`[getRole] Found ACLs under key '${key}':`, roleData[key]);
            
            if (Array.isArray(roleData[key])) {
              foundAcls = roleData[key];
            } else if (typeof roleData[key] === 'string') {
              foundAcls = parseACLData(roleData[key]);
            }
            break;
          }
        }
        
        return {
          name: name,
          acls: foundAcls,
          ...roleData // Include all original data
        };
      }
      
      // Fallback return
      console.log(`[getRole] Fallback return for role ${name}`);
      return {
        name: name,
        acls: [],
        rawData: roleData
      };
      
    } catch (error) {
      console.error(`[getRole] Error fetching role ${name}:`, error);
      console.error(`[getRole] Error response:`, error.response?.data);
      throw error;
    }
  },

  async createRole(name) {
    try {
      console.log(`[createRole] Creating role: ${name}`);
      const response = await api.post('/roles', { name });
      console.log(`[createRole] Response:`, response.data);
      return response.data;
    } catch (error) {
      console.error(`[createRole] Error creating role ${name}:`, error);
      throw error;
    }
  },

  async deleteRole(name) {
    try {
      console.log(`[deleteRole] Deleting role: ${name}`);
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/roles/${name}`, {
        params: { nonce, timestamp }
      });
      
      console.log(`[deleteRole] Response:`, response.data);
      return response.data;
    } catch (error) {
      console.error(`[deleteRole] Error deleting role ${name}:`, error);
      throw error;
    }
  },

  async addRoleACL(roleName, aclData) {
    try {
      console.log(`[addRoleACL] Adding ACL to role ${roleName}:`, aclData);
      
      const response = await api.post(`/roles/${roleName}/acls`, {
        topic: aclData.topic,
        aclType: aclData.aclType,
        permission: aclData.permission
      });
      
      console.log(`[addRoleACL] Response:`, response.data);
      
      // Verify the update by fetching the role again
      console.log(`[addRoleACL] Verifying ACL was added...`);
      const updatedRole = await this.getRole(roleName);
      console.log(`[addRoleACL] Updated role after adding ACL:`, updatedRole);
      
      return response.data;
    } catch (error) {
      console.error(`[addRoleACL] Error adding ACL to role ${roleName}:`, error);
      throw error;
    }
  },

  async removeRoleACL(roleName, aclType, topic) {
    try {
      console.log(`[removeRoleACL] Removing ACL from role ${roleName}:`, { aclType, topic });
      
      const timestamp = getCurrentTimestamp();
      const nonce = generateNonce();
      
      const response = await api.delete(`/roles/${roleName}/acls`, {
        params: { acl_type: aclType, topic, nonce, timestamp }
      });
      
      console.log(`[removeRoleACL] Response:`, response.data);
      
      // Verify the update by fetching the role again
      console.log(`[removeRoleACL] Verifying ACL was removed...`);
      const updatedRole = await this.getRole(roleName);
      console.log(`[removeRoleACL] Updated role after removing ACL:`, updatedRole);
      
      return response.data;
    } catch (error) {
      console.error(`[removeRoleACL] Error removing ACL from role ${roleName}:`, error);
      throw error;
    }
  },

  // Debug method to help troubleshoot API responses
  async debugRole(name) {
    try {
      console.log(`[debugRole] === DEBUGGING ROLE ${name} ===`);
      
      // Make raw API call
      const response = await api.get(`/roles/${name}`);
      
      console.log(`[debugRole] Full response object:`, response);
      console.log(`[debugRole] Response status:`, response.status);
      console.log(`[debugRole] Response headers:`, response.headers);
      console.log(`[debugRole] Response data:`, response.data);
      console.log(`[debugRole] Response data type:`, typeof response.data);
      
      if (response.data) {
        console.log(`[debugRole] Response data keys:`, Object.keys(response.data));
        
        if (response.data.role) {
          console.log(`[debugRole] Role property:`, response.data.role);
          console.log(`[debugRole] Role property type:`, typeof response.data.role);
          
          if (typeof response.data.role === 'object') {
            console.log(`[debugRole] Role object keys:`, Object.keys(response.data.role));
          }
        }
      }
      
      console.log(`[debugRole] === END DEBUG ${name} ===`);
      
      return response.data;
    } catch (error) {
      console.error(`[debugRole] Debug error for role ${name}:`, error);
      throw error;
    }
  }
};