/* # Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
# */
// services/azureBridgeService.js
import { api } from './api';

export const azureBridgeService = {
  async configureBridge(formData) {

    try {
      const response = await api.post('/azure-bridge', formData);
      
      return response.data;
    } catch (error) {
      console.error('Error configuring Azure IoT Hub Bridge:', error.response?.data || error.message);
      throw error;
    }
  }
};