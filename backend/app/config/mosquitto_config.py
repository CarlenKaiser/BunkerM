# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

from logging.handlers import RotatingFileHandler
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Router setup
router = APIRouter(
    tags=["mosquitto_config"],
    dependencies=[Depends(verify_firebase_token)]  # Default auth for all routes
)

# Configure logging
logger = logging.getLogger(__name__)

# Environment variables
MOSQUITTO_CONF_PATH = os.getenv("MOSQUITTO_CONF_PATH", "/etc/mosquitto/mosquitto.conf")
BACKUP_DIR = os.getenv("MOSQUITTO_BACKUP_DIR", "/tmp/mosquitto_backups")

# Security
security = HTTPBearer()

# Create backup directory if it doesn't exist
os.makedirs(BACKUP_DIR, exist_ok=True)

async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify Firebase ID token and return user info with role"""
    try:
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        custom_claims = decoded_token.get('custom_claims', {})
        user_role = custom_claims.get('role', 'user')
        
        logger.info(f"Authenticated user: {decoded_token.get('email', 'unknown')}")
        
        return {
            'uid': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'role': user_role,
            'is_admin': user_role == 'admin',
            'is_moderator': user_role in ['admin', 'moderator']
        }
        
    except auth.InvalidIdTokenError:
        logger.error("Invalid Firebase ID token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except auth.ExpiredIdTokenError:
        logger.error("Expired Firebase ID token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired"
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )

async def require_admin(user: dict = Depends(verify_firebase_token)) -> dict:
    """Require admin role for sensitive operations"""
    if not user.get('is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

# Models for request validation
class Listener(BaseModel):
    port: int
    bind_address: Optional[str] = None
    per_listener_settings: Optional[bool] = False
    max_connections: Optional[int] = -1

class MosquittoConfig(BaseModel):
    config: Dict[str, Any]
    listeners: List[Listener] = []

# Default configuration
DEFAULT_CONFIG = """# MQTT listener on port 1900
listener 1900
per_listener_settings false
allow_anonymous false

# HTTP listener for Dynamic Security Plugin on port 8080
listener 8080
password_file /etc/mosquitto/mosquitto_passwd
# Dynamic Security Plugin configuration
plugin /usr/lib/mosquitto_dynamic_security.so
plugin_opt_config_file /var/lib/mosquitto/dynamic-security.json
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
log_timestamp true
persistence true
persistence_location /var/lib/mosquitto/
persistence_file mosquitto.db
"""

def parse_mosquitto_conf() -> Dict[str, Any]:
    """Parse the mosquitto.conf file into a dictionary"""
    config = {}
    listeners = []
    current_listener = None

    try:
        with open(MOSQUITTO_CONF_PATH, "r") as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if line.startswith("listener "):
                parts = line.split()
                if current_listener:
                    listeners.append(current_listener)
                current_listener = {
                    "port": int(parts[1]),
                    "bind_address": parts[2] if len(parts) > 2 else "",
                    "per_listener_settings": False,
                    "max_connections": -1,
                }
            elif current_listener and line.startswith(
                ("per_listener_settings ", "max_connections ")
            ):
                key, value = line.split(" ", 1)
                if key == "per_listener_settings":
                    current_listener[key] = value.lower() == "true"
                elif key == "max_connections":
                    current_listener[key] = int(value)
            else:
                if " " in line:
                    key, value = line.split(" ", 1)
                    config[key] = value

        if current_listener:
            listeners.append(current_listener)

        return {"config": config, "listeners": listeners}

    except Exception as e:
        logger.error(f"Error parsing mosquitto.conf: {str(e)}")
        return {"config": {}, "listeners": []}

def generate_mosquitto_conf(
    config_data: Dict[str, Any], listeners: List[Dict[str, Any]]
) -> str:
    """Generate mosquitto.conf content from configuration data"""
    lines = [
        "# Mosquitto Broker Configuration",
        "# Generated on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ""
    ]

    # Main configuration
    for key, value in config_data.items():
        if key in ["plugin", "plugin_opt_config_file"]:
            continue
        if isinstance(value, bool):
            value = str(value).lower()
        lines.append(f"{key} {value}")

    # Plugins configuration
    if "plugin" in config_data:
        lines.extend([
            "",
            "# Dynamic Security Plugin configuration",
            f"plugin {config_data['plugin']}"
        ])
        if "plugin_opt_config_file" in config_data:
            lines.append(f"plugin_opt_config_file {config_data['plugin_opt_config_file']}")

    # Listeners
    for listener in listeners:
        lines.extend([
            "",
            f"listener {listener['port']}{' ' + listener['bind_address'] if listener['bind_address'] else ''}"
        ])
        if "per_listener_settings" in listener:
            lines.append(f"per_listener_settings {str(listener['per_listener_settings']).lower()}")
        if "max_connections" in listener and listener["max_connections"] != -1:
            lines.append(f"max_connections {listener['max_connections']}")

    return "\n".join(lines)

@router.get("/mosquitto-config")
async def get_mosquitto_config(user: dict = Depends(verify_firebase_token)):
    """Get the current Mosquitto configuration"""
    try:
        config_data = parse_mosquitto_conf()
        if not config_data["config"]:
            return {
                "success": False,
                "message": "Failed to parse Mosquitto configuration",
            }

        return {
            "success": True,
            "config": config_data["config"],
            "listeners": config_data["listeners"],
        }

    except Exception as e:
        logger.error(f"Error getting Mosquitto configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Mosquitto configuration: {str(e)}",
        )

@router.post("/mosquitto-config")
async def save_mosquitto_config(
    config: MosquittoConfig, 
    user: dict = Depends(require_admin)  # Only admins can modify config
):
    try:
        listeners_list = []
        for listener in config.listeners:
            listeners_list.append({
                "port": listener.port,
                "bind_address": listener.bind_address or "",
                "per_listener_settings": listener.per_listener_settings,
                "max_connections": listener.max_connections,
            })

        current_config = parse_mosquitto_conf()
        is_valid, error_message = validate_listeners(current_config.get("listeners", []), listeners_list)
        
        if not is_valid:
            logger.error(f"Validation error: {error_message}")
            return {
                "success": False,
                "message": error_message
            }

        # Create backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"mosquitto.conf.bak.{timestamp}")
        if os.path.exists(MOSQUITTO_CONF_PATH):
            shutil.copy2(MOSQUITTO_CONF_PATH, backup_path)
            logger.info(f"Created backup at {backup_path}")

        # Write new config
        new_config_content = generate_mosquitto_conf(config.config, listeners_list)
        with open(MOSQUITTO_CONF_PATH, "w") as f:
            f.write(new_config_content)
        os.chmod(MOSQUITTO_CONF_PATH, 0o644)

        logger.info("Configuration saved successfully")
        return {
            "success": True,
            "message": "Mosquitto configuration saved successfully",
            "need_restart": True,
        }

    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save configuration: {str(e)}",
        )

@router.post("/reset-mosquitto-config")
async def reset_mosquitto_config(user: dict = Depends(require_admin)):
    """Reset to default configuration (Admin only)"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"mosquitto.conf.bak.{timestamp}")

        if os.path.exists(MOSQUITTO_CONF_PATH):
            shutil.copy2(MOSQUITTO_CONF_PATH, backup_path)
            logger.info(f"Created backup at {backup_path}")

        with open(MOSQUITTO_CONF_PATH, "w") as f:
            f.write(DEFAULT_CONFIG)
        os.chmod(MOSQUITTO_CONF_PATH, 0o644)

        logger.info("Configuration reset to default")
        return {
            "success": True,
            "message": "Configuration reset to default",
            "need_restart": True,
        }

    except Exception as e:
        logger.error(f"Error resetting configuration: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset configuration: {str(e)}",
        )

@router.post("/remove-mosquitto-listener")
async def remove_mosquitto_listener(
    listener_data: dict, 
    user: dict = Depends(require_admin)
):
    """Remove a listener (Admin only)"""
    try:
        port = listener_data.get("port")
        if not port:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Port is required",
            )

        config_data = parse_mosquitto_conf()
        listeners_list = config_data["listeners"]
        
        found = False
        for i, listener in enumerate(listeners_list):
            if listener.get("port") == port:
                listeners_list.pop(i)
                found = True
                break
        
        if not found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Listener on port {port} not found",
            )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"mosquitto.conf.bak.{timestamp}")
        if os.path.exists(MOSQUITTO_CONF_PATH):
            shutil.copy2(MOSQUITTO_CONF_PATH, backup_path)

        new_config_content = generate_mosquitto_conf(config_data["config"], listeners_list)
        with open(MOSQUITTO_CONF_PATH, "w") as f:
            f.write(new_config_content)
        os.chmod(MOSQUITTO_CONF_PATH, 0o644)

        logger.info(f"Removed listener on port {port}")
        return {
            "success": True,
            "message": f"Removed listener on port {port}",
            "need_restart": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing listener: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove listener: {str(e)}",
        )

def validate_listeners(current_listeners: List[Dict[str, Any]], new_listeners: List[Dict[str, Any]]) -> tuple[bool, str]:
    """Validate listener ports"""
    port_counts = {}
    for listener in new_listeners:
        port = listener.get('port')
        if port in port_counts:
            port_counts[port] += 1
        else:
            port_counts[port] = 1
    
    for port, count in port_counts.items():
        if count > 1:
            return False, f"Duplicate port {port}"
    
    default_ports = [1900, 8080]
    for port in port_counts:
        if port in default_ports and any(l.get('port') != port for l in new_listeners):
            return False, f"Port {port} is reserved"
    
    return True, ""