# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
#
# app/dynsec/password_import.py
import logging
import os
import re
import shutil
import subprocess
import json
import random
import string
import time
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Security, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime
from typing import Optional, Dict, Any, List
import firebase_admin
from firebase_admin import auth, exceptions as firebase_exceptions

# Router setup
router = APIRouter(tags=["password_import"])

# Configure logging
logger = logging.getLogger(__name__)

# Environment variables
MOSQUITTO_PASSWD_PATH = "/etc/mosquitto/mosquitto_passwd"
DYNSEC_PATH = os.getenv("DYNSEC_PATH", "/var/lib/mosquitto/dynamic-security.json")
UPLOAD_DIR = "/tmp/mosquitto_uploads"

# Security
security = HTTPBearer()

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Authentication functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    request: Request = None
) -> dict:
    """Enhanced Firebase authentication with role support"""
    try:
        if not credentials.scheme == "Bearer":
            logger.warning(f"Invalid auth scheme from {request.client.host if request else 'unknown'}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid authentication scheme"
            )
        
        decoded_token = auth.verify_id_token(credentials.credentials)
        user_role = decoded_token.get('role', 'user')
        
        return {
            'uid': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'role': user_role,
            'is_admin': user_role == 'admin',
            'is_moderator': user_role in ['admin', 'moderator'],
            'can_manage': user_role in ['admin', 'moderator']
        }
        
    except firebase_exceptions.InvalidIdTokenError:
        logger.error("Invalid Firebase ID token provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid authentication token"
        )
    except firebase_exceptions.ExpiredIdTokenError:
        logger.error("Expired Firebase ID token provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication token has expired"
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authentication failed"
        )

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Require admin privileges"""
    if not user.get('is_admin', False):
        logger.warning(f"Unauthorized admin access attempt by {user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

async def require_management(user: dict = Depends(get_current_user)) -> dict:
    """Require management privileges (admin or moderator)"""
    if not user.get('can_manage', False):
        logger.warning(f"Unauthorized management attempt by {user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Management access required"
        )
    return user

def validate_mosquitto_passwd_file(file_path: str) -> tuple[bool, str, list]:
    """
    Validates if a file has the correct mosquitto_passwd format.
    Returns (success, message, users)
    """
    users = []
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        if not lines:
            return False, "File is empty", []
            
        valid_pattern = re.compile(r'^[^:]+:\$\d+\$[^:]+$')
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            if not valid_pattern.match(line):
                return False, f"Invalid format at line {i+1}: {line}", []
                
            username = line.split(':')[0]
            users.append(username)
            
        return True, f"Valid mosquitto_passwd file with {len(users)} users", users
    except Exception as e:
        logger.error(f"Error validating mosquitto_passwd file: {str(e)}")
        return False, f"Error reading file: {str(e)}", []

def generate_random_salt(length=16):
    """Generate a random salt for dynamic security users"""
    return ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(length))

def update_dynsec_with_passwd_users(usernames: List[str]) -> tuple[bool, str, int]:
    """
    Update dynamic-security.json file with users from mosquitto_passwd
    """
    try:
        # Check if dynsec file exists
        if not os.path.exists(DYNSEC_PATH):
            return False, f"Dynamic security file not found at {DYNSEC_PATH}", 0
            
        # Read the current dynsec file
        with open(DYNSEC_PATH, 'r') as f:
            dynsec_data = json.load(f)
            
        # Initialize clients array if it doesn't exist
        if 'clients' not in dynsec_data:
            dynsec_data['clients'] = []
            
        # Get the current list of clients
        current_clients = dynsec_data.get('clients', [])
        current_usernames = {client.get('username') for client in current_clients}
        
        # Track added users
        added_users = []
        
        # For each username from passwd file, add to dynsec if not exists
        for username in usernames:
            if username not in current_usernames:
                # Create a new client entry without password
                # Following the exact format seen in after.json
                new_client = {
                    "username": username,
                    "roles": [],  # Always include an empty roles array
                    "salt": generate_random_salt(),
                    "iterations": 101
                }
                
                # Add to clients list
                current_clients.append(new_client)
                current_usernames.add(username)
                added_users.append(username)
                
        # Only update the file if changes were made
        if added_users:
            # Make sure we maintain the exact structure of the file
            dynsec_data['clients'] = current_clients
            
            # Create a backup of the dynsec file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{DYNSEC_PATH}.bak.{timestamp}"
            shutil.copy2(DYNSEC_PATH, backup_path)
            logger.info(f"Created backup of dynamic security file at {backup_path}")
            
            # Write the updated dynsec file
            with open(DYNSEC_PATH, 'w') as f:
                json.dump(dynsec_data, f, indent="\t")
                
            logger.info(f"Updated dynamic security file with {len(added_users)} users: {', '.join(added_users)}")
            return True, f"Added {len(added_users)} users to dynamic security", len(added_users)
        else:
            return True, "No new users to add to dynamic security", 0
            
    except Exception as e:
        logger.error(f"Error updating dynamic security with passwd users: {str(e)}")
        return False, f"Error updating dynamic security: {str(e)}", 0

@router.post("/import-password-file")
async def import_password_file(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin)
):
    """
    Import a mosquitto_passwd file and update dynamic security
    Requires admin privileges
    """
    logger.info(f"Password file import requested by {user.get('email')}: {file.filename}")
    
    # Create a unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_file_path = os.path.join(UPLOAD_DIR, f"{timestamp}_{file.filename}")
    
    try:
        # Save uploaded file to temporary location
        with open(temp_file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Validate the file
        is_valid, message, users = validate_mosquitto_passwd_file(temp_file_path)
        
        if not is_valid:
            logger.warning(f"Invalid mosquitto_passwd file upload by {user.get('email')}: {message}")
            return {
                "success": False, 
                "message": message,
                "results": {
                    "total": 0,
                    "imported": 0,
                    "skipped": 0,
                    "failed": 0,
                    "details": []
                }
            }
        
        # Backup existing file if it exists
        if os.path.exists(MOSQUITTO_PASSWD_PATH):
            backup_path = f"{MOSQUITTO_PASSWD_PATH}.bak.{timestamp}"
            shutil.copy2(MOSQUITTO_PASSWD_PATH, backup_path)
            logger.info(f"Created backup of existing password file at {backup_path}")
        
        # Import the file to the destination
        shutil.copy2(temp_file_path, MOSQUITTO_PASSWD_PATH)
        
        # Ensure proper permissions - using 644 to match your Dockerfile configuration
        # This allows owner read/write and everyone else read access
        os.chmod(MOSQUITTO_PASSWD_PATH, 0o644)
        
        # Update dynamic security with users from the password file
        dynsec_success, dynsec_message, dynsec_count = update_dynsec_with_passwd_users(users)
        
        # Create results for the frontend
        details = []
        for username in users:
            details.append({
                "username": username,
                "status": "SUCCESS",
                "message": "User imported successfully"
            })
        
        # If dynsec update failed, add a warning message
        result_message = f"Successfully imported password file with {len(users)} users"
        if dynsec_success:
            if dynsec_count > 0:
                result_message += f" and added {dynsec_count} users to dynamic security"
        else:
            result_message += f" but failed to update dynamic security: {dynsec_message}"
            
        logger.info(f"Password file import completed by {user.get('email')}: {result_message}")
        
        return {
            "success": True, 
            "message": result_message,
            "results": {
                "total": len(users),
                "imported": len(users),
                "skipped": 0,
                "failed": 0,
                "details": details,
                "dynsec_updated": dynsec_success,
                "dynsec_added": dynsec_count
            }
        }
    
    except Exception as e:
        logger.error(f"Error importing password file for {user.get('email')}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import password file: {str(e)}"
        )
    finally:
        # Clean up temporary file
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

@router.post("/sync-passwd-to-dynsec")
async def sync_passwd_to_dynsec(
    request: Request,
    user: dict = Depends(require_admin)
):
    """
    Sync all users from mosquitto_passwd file to dynamic security
    Requires admin privileges
    """
    try:
        logger.info(f"Syncing mosquitto_passwd users to dynamic security requested by {user.get('email')}")
        
        # Check if password file exists
        if not os.path.exists(MOSQUITTO_PASSWD_PATH):
            return {
                "success": False,
                "message": "Password file not found"
            }
            
        # Extract users from the password file
        users = []
        with open(MOSQUITTO_PASSWD_PATH, 'r') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    username = line.split(':')[0]
                    users.append(username)
                    
        if not users:
            return {
                "success": True,
                "message": "No users found in password file to sync"
            }
                    
        # Update dynamic security with these users
        success, message, count = update_dynsec_with_passwd_users(users)
        
        if success:
            logger.info(f"Sync completed by {user.get('email')}: {message}")
            return {
                "success": True,
                "message": message,
                "count": count,
                "users": users[:10] + (["..."] if len(users) > 10 else [])  # Show first 10 users
            }
        else:
            logger.error(f"Sync failed for {user.get('email')}: {message}")
            return {
                "success": False,
                "message": message
            }
    
    except Exception as e:
        logger.error(f"Error syncing passwd to dynsec for {user.get('email')}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync password file to dynamic security: {str(e)}"
        )

@router.post("/restart-mosquitto")
async def restart_mosquitto(
    request: Request,
    user: dict = Depends(require_admin)
):
    """
    Restart the Mosquitto broker service
    Requires admin privileges
    """
    try:
        logger.info(f"Restart Mosquitto broker requested by {user.get('email')}")
        
        # Execute restart command
        restart_script = """#!/bin/bash
# Kill existing mosquitto process
pkill mosquitto

# Wait for process to terminate
sleep 1

# Start mosquitto with config file
/usr/sbin/mosquitto -c /etc/mosquitto/mosquitto.conf -d

# Check if mosquitto started successfully
sleep 2
if pgrep mosquitto > /dev/null; then
    echo "Mosquitto restarted successfully"
    exit 0
else
    echo "Failed to restart Mosquitto"
    exit 1
fi
"""
        
        # Write script to temp file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_path = os.path.join(UPLOAD_DIR, f"restart_script_{timestamp}.sh")
        with open(script_path, "w") as f:
            f.write(restart_script)
        
        # Make executable
        os.chmod(script_path, 0o755)
        
        # Execute script
        try:
            result = subprocess.run(
                ["/bin/bash", script_path],
                check=True,
                capture_output=True,
                text=True,
                timeout=10  # Set a timeout for the restart process
            )
            logger.info(f"Restart output for {user.get('email')}: {result.stdout}")
            
            if result.returncode == 0:
                return {"success": True, "message": "Mosquitto broker restarted successfully"}
            else:
                logger.error(f"Restart stderr for {user.get('email')}: {result.stderr}")
                return {"success": False, "message": f"Failed to restart Mosquitto: {result.stderr}"}
                
        except subprocess.CalledProcessError as e:
            logger.error(f"Restart failed for {user.get('email')}: {e.stderr}")
            return {"success": False, "message": f"Failed to restart Mosquitto: {e.stderr}"}
        except subprocess.TimeoutExpired:
            logger.error(f"Restart timeout expired for {user.get('email')}")
            return {"success": False, "message": "Timeout while restarting Mosquitto"}
        finally:
            # Clean up script
            if os.path.exists(script_path):
                os.remove(script_path)
    
    except Exception as e:
        logger.error(f"Error restarting Mosquitto for {user.get('email')}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart Mosquitto: {str(e)}"
        )

@router.get("/password-file-status")
async def check_password_file_status(
    request: Request,
    user: dict = Depends(require_management)
):
    """
    Check if the password file exists and get basic stats
    Requires management privileges (admin or moderator)
    """
    try:
        logger.info(f"Password file status check by {user.get('email')}")
        
        if not os.path.exists(MOSQUITTO_PASSWD_PATH):
            return {
                "exists": False,
                "message": "Password file does not exist"
            }
            
        # Get file stats and user count
        file_stats = os.stat(MOSQUITTO_PASSWD_PATH)
        file_size = file_stats.st_size
        modified_time = datetime.fromtimestamp(file_stats.st_mtime).isoformat()
        
        # Count users in the file
        user_count = 0
        try:
            with open(MOSQUITTO_PASSWD_PATH, 'r') as f:
                for line in f:
                    if line.strip():
                        user_count += 1
        except Exception as e:
            logger.warning(f"Error reading password file for {user.get('email')}: {str(e)}")
                
        return {
            "exists": True,
            "size_bytes": file_size,
            "modified": modified_time,
            "user_count": user_count
        }
    
    except Exception as e:
        logger.error(f"Error checking password file status for {user.get('email')}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check password file status: {str(e)}"
        )