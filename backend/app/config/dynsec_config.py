# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

import json
import logging
import os
import shutil
from datetime import datetime
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import firebase_admin
from firebase_admin import auth

# Router setup with default Firebase auth
router = APIRouter(
    tags=["dynsec_config"],
    dependencies=[Depends(verify_firebase_token)]  # Default auth for all routes
)

# Configure logging
logger = logging.getLogger(__name__)

# Environment variables
DYNSEC_JSON_PATH = os.getenv("DYNSEC_JSON_PATH", "/var/lib/mosquitto/dynamic-security.json")
BACKUP_DIR = os.getenv("DYNSEC_BACKUP_DIR", "/tmp/dynsec_backups")

# Security
security = HTTPBearer()

# Create backup directory if it doesn't exist
os.makedirs(BACKUP_DIR, exist_ok=True)

# Default configuration that must be preserved
DEFAULT_CONFIG = {
    "defaultACLAccess": {
        "publishClientSend": True,
        "publishClientReceive": True,
        "subscribe": True,
        "unsubscribe": True
    },
    "clients": [{
        "username": "bunker",
        "textname": "Dynsec admin user",
        "roles": [{
            "rolename": "admin"
        }],
        "password": "bZDAuypZzNug9z7yoB3vmEwGIx1COCRaN8m16bEbnAoVJxBYxz1x9fMR7cB7ToC2Kj+txYEq2bWrl1H3GtnRlg==",
        "salt": "MfMHo5wStiQVCpnt",
        "iterations": 101
    }],
    "groups": [],
    "roles": [{
        "rolename": "admin",
        "acls": [{
            "acltype": "publishClientSend",
            "topic": "$CONTROL/dynamic-security/#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "publishClientReceive",
            "topic": "$CONTROL/dynamic-security/#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "publishClientReceive",
            "topic": "$SYS/#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "publishClientReceive",
            "topic": "#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "subscribePattern",
            "topic": "#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "subscribePattern",
            "topic": "$CONTROL/dynamic-security/#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "subscribePattern",
            "topic": "$SYS/#",
            "priority": 0,
            "allow": True
        }, {
            "acltype": "unsubscribePattern",
            "topic": "#",
            "priority": 0,
            "allow": True
        }]
    }]
}

async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify Firebase ID token and return user info"""
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

def read_dynsec_json() -> Dict[str, Any]:
    """Read the dynamic security JSON file"""
    try:
        with open(DYNSEC_JSON_PATH, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading dynamic security JSON: {str(e)}")
        return {}

def write_dynsec_json(data: Dict[str, Any]) -> bool:
    """Write to the dynamic security JSON file"""
    try:
        with open(DYNSEC_JSON_PATH, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error writing dynamic security JSON: {str(e)}")
        return False

def validate_dynsec_json(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the dynamic security JSON structure"""
    required_keys = ["defaultACLAccess", "clients", "groups", "roles"]
    
    for key in required_keys:
        if key not in data:
            raise ValueError(f"Missing required key: {key}")
    
    required_acl_fields = ["publishClientSend", "publishClientReceive", "subscribe", "unsubscribe"]
    for field in required_acl_fields:
        if field not in data["defaultACLAccess"]:
            raise ValueError(f"Missing required field in defaultACLAccess: {field}")
    
    if not isinstance(data["clients"], list):
        raise ValueError("'clients' must be a list")
    if not isinstance(data["groups"], list):
        raise ValueError("'groups' must be a list")
    if not isinstance(data["roles"], list):
        raise ValueError("'roles' must be a list")
    
    return data

def merge_dynsec_configs(imported_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge imported config with default config to preserve critical components"""
    merged_config = DEFAULT_CONFIG.copy()
    
    admin_user = DEFAULT_CONFIG["clients"][0]
    non_admin_users = [user for user in imported_config.get("clients", []) 
                     if "username" in user and user["username"] != "bunker"]
    merged_config["clients"] = [admin_user] + non_admin_users
    
    admin_role = DEFAULT_CONFIG["roles"][0]
    non_admin_roles = [role for role in imported_config.get("roles", []) 
                     if "rolename" in role and role["rolename"] != "admin"]
    merged_config["roles"] = [admin_role] + non_admin_roles
    
    merged_config["groups"] = imported_config.get("groups", [])
    
    return merged_config

def create_backup() -> str:
    """Create a backup of the current dynamic security JSON file"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"dynamic-security.json.bak.{timestamp}")
        
        if os.path.exists(DYNSEC_JSON_PATH):
            shutil.copy2(DYNSEC_JSON_PATH, backup_path)
            logger.info(f"Created backup at {backup_path}")
            return backup_path
        return ""
    except Exception as e:
        logger.error(f"Error creating backup: {str(e)}")
        return ""

@router.get("/dynsec-json")
async def get_dynsec_json(user: dict = Depends(verify_firebase_token)):
    """Get the current dynamic security JSON configuration"""
    try:
        data = read_dynsec_json()
        if not data:
            return {
                "success": False,
                "message": "Failed to read dynamic security JSON"
            }
        return {
            "success": True,
            "data": data
        }
    except Exception as e:
        logger.error(f"Error getting dynamic security JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get dynamic security JSON: {str(e)}"
        )

@router.get("/export-dynsec-json")
async def export_dynsec_json(user: dict = Depends(require_admin)):  # Admin only
    """Export the dynamic security JSON file for download"""
    try:
        data = read_dynsec_json()
        if not data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to read dynamic security JSON"
            )
        
        export_data = data.copy()
        if "clients" in export_data:
            export_data["clients"] = [
                client for client in export_data["clients"] 
                if "username" not in client or client["username"] != "bunker"
            ]
        if "roles" in export_data:
            export_data["roles"] = [
                role for role in export_data["roles"] 
                if "rolename" not in role or role["rolename"] != "admin"
            ]
        
        content = json.dumps(export_data, indent=4)
        filename = f"dynamic-security-export-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "application/json",
                "Content-Length": str(len(content))
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting dynamic security JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export dynamic security JSON: {str(e)}"
        )

@router.post("/import-dynsec-json")
async def import_dynsec_json(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin)  # Admin only
):
    """Import a dynamic security JSON file"""
    try:
        content = await file.read()
        try:
            imported_data = json.loads(content)
        except json.JSONDecodeError:
            return {
                "success": False,
                "message": "The uploaded file is not valid JSON"
            }
        
        try:
            imported_data = validate_dynsec_json(imported_data)
        except ValueError as e:
            return {
                "success": False,
                "message": f"Invalid dynamic security JSON format: {str(e)}"
            }
        
        backup_path = create_backup()
        merged_config = merge_dynsec_configs(imported_data)
        
        if write_dynsec_json(merged_config):
            user_count = len(merged_config["clients"]) - 1
            group_count = len(merged_config["groups"])
            role_count = len(merged_config["roles"]) - 1
            
            return {
                "success": True,
                "message": "Successfully imported dynamic security configuration",
                "backup_path": backup_path,
                "stats": {
                    "users": user_count,
                    "groups": group_count,
                    "roles": role_count
                },
                "need_restart": True
            }
        return {
            "success": False,
            "message": "Failed to write dynamic security configuration"
        }
    except Exception as e:
        logger.error(f"Error importing dynamic security JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import dynamic security JSON: {str(e)}"
        )

@router.post("/reset-dynsec-json")
async def reset_dynsec_json(user: dict = Depends(require_admin)):  # Admin only
    """Reset dynamic security JSON to default configuration"""
    try:
        backup_path = create_backup()
        if write_dynsec_json(DEFAULT_CONFIG):
            return {
                "success": True,
                "message": "Successfully reset dynamic security configuration to default",
                "backup_path": backup_path,
                "need_restart": True
            }
        return {
            "success": False,
            "message": "Failed to write default dynamic security configuration"
        }
    except Exception as e:
        logger.error(f"Error resetting dynamic security JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset dynamic security JSON: {str(e)}"
        )