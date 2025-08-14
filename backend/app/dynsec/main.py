# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

import logging
from fastapi import FastAPI, HTTPException, Security, Depends, Request, status, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import subprocess
import os
import json
from dotenv import load_dotenv
from enum import Enum
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
import uvicorn
import firebase_admin
from firebase_admin import auth, credentials, exceptions as firebase_exceptions
from password_import import router as password_import_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(
    "dynsec_api_activity.log", 
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
logger.addHandler(handler)

# Initialize Firebase Admin SDK
try:
    firebase_config_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not firebase_config_path or not os.path.exists(firebase_config_path):
        raise ValueError("Firebase credentials file not found")
    
    cred = credentials.Certificate(firebase_config_path)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    raise

# Environment variables
MOSQUITTO_ADMIN_USERNAME = os.getenv("MOSQUITTO_ADMIN_USERNAME")
MOSQUITTO_ADMIN_PASSWORD = os.getenv("MOSQUITTO_ADMIN_PASSWORD")
MOSQUITTO_IP = os.getenv("MOSQUITTO_IP", "localhost")
MOSQUITTO_PORT = os.getenv("MOSQUITTO_PORT", "1883")
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# Base command for mosquitto_ctrl
DYNSEC_BASE_COMMAND = [
    "mosquitto_ctrl",
    "-h", MOSQUITTO_IP,
    "-p", MOSQUITTO_PORT,
    "-u", MOSQUITTO_ADMIN_USERNAME,
    "-P", MOSQUITTO_ADMIN_PASSWORD,
    "dynsec"
]

# Initialize FastAPI app
app = FastAPI(
    title="Mosquitto DynSec API",
    version="2.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=ALLOWED_HOSTS
)

# Security
security = HTTPBearer()

# Models
class ClientCreate(BaseModel):
    username: str
    password: str

class ClientResponse(BaseModel):
    username: str
    message: str
    success: bool

class RoleCreate(BaseModel):
    name: str
    textname: Optional[str] = None
    acls: Optional[List[Dict[str, Any]]] = None

class GroupCreate(BaseModel):
    name: str
    textname: Optional[str] = None

class RoleAssignment(BaseModel):
    role_name: str
    priority: Optional[int] = 1

class ACLRequest(BaseModel):
    topic: str
    aclType: str
    permission: str

class ACLType(str, Enum):
    PUBLISH = "publishClientSend"
    SUBSCRIBE = "subscribeLiteral"

class Permission(str, Enum):
    ALLOW = "allow"
    DENY = "deny"

# Authentication
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

# Utility functions
def execute_mosquitto_command(command: list, input_data: str = None) -> tuple[bool, str]:
    """Execute mosquitto_ctrl command with error handling"""
    try:
        full_command = DYNSEC_BASE_COMMAND + command
        logger.debug(f"Executing: {' '.join(full_command)}")
        
        process = subprocess.Popen(
            full_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate(input=input_data)

        if process.returncode == 0:
            logger.debug(f"Command succeeded: {stdout.strip()}")
            return True, stdout.strip()
        
        logger.error(f"Command failed: {stderr.strip()}")
        return False, stderr.strip()

    except Exception as e:
        logger.error(f"Command execution error: {str(e)}")
        return False, str(e)

async def log_request(request: Request):
    """Log request details"""
    logger.info(
        f"Request: {request.method} {request.url} "
        f"From: {request.client.host} "
        f"User-Agent: {request.headers.get('user-agent')}"
    )

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add security headers and log requests"""
    await log_request(request)
    response = await call_next(request)
    response.headers.update({
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block"
    })
    return response

# Include password import router
app.include_router(password_import_router, prefix="/api/v1")

# Client Management Endpoints
@app.post("/api/v1/clients", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    request: Request,
    user: dict = Depends(require_management)
):
    """Create new MQTT client"""
    await log_request(request)
    logger.info(f"Creating new client with username: {client.username}")

    try:
        # Create client
        success, result = execute_mosquitto_command(["createClient", client.username])
        if not success:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)

        # Set password
        success, result = execute_mosquitto_command(
            ["setClientPassword", client.username, client.password]
        )
        if not success:
            execute_mosquitto_command(["deleteClient", client.username])  # Cleanup
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)

        return ClientResponse(
            username=client.username,
            message="Client created successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Client creation error: {str(e)}")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@app.get("/api/v1/clients")
async def list_clients(
    request: Request,
    user: dict = Depends(require_management)
):
    """List all clients"""
    success, result = execute_mosquitto_command(["listClients"])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"clients": result.split('\n')}

@app.get("/api/v1/clients/{username}")
async def get_client(
    username: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Get client details"""
    success, result = execute_mosquitto_command(["getClient", username])
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Client not found")
    return {"client": result}

@app.put("/api/v1/clients/{username}/enable")
async def enable_client(
    username: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Enable a client"""
    success, result = execute_mosquitto_command(["enableClient", username])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Client {username} enabled"}

@app.put("/api/v1/clients/{username}/disable")
async def disable_client(
    username: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Disable a client"""
    success, result = execute_mosquitto_command(["disableClient", username])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Client {username} disabled"}

@app.delete("/api/v1/clients/{username}")
async def delete_client(
    username: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Delete a client"""
    success, result = execute_mosquitto_command(["deleteClient", username])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Client {username} deleted"}

# Role Management Endpoints
@app.post("/api/v1/roles")
async def create_role(
    role: RoleCreate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Create a new role"""
    success, result = execute_mosquitto_command(["createRole", role.name])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role.name} created"}

@app.get("/api/v1/roles")
async def list_roles(
    request: Request,
    user: dict = Depends(require_management)
):
    """List all roles"""
    success, result = execute_mosquitto_command(["listRoles"])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"roles": result.split('\n')}

@app.get("/api/v1/roles/{role_name}")
async def get_role(
    role_name: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Get role details"""
    success, result = execute_mosquitto_command(["getRole", role_name])
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Role not found")
    
    # Add logging to see the raw response
    logger.info(f"Raw role data for {role_name}: {result}")
    
    return {"role": result}

@app.delete("/api/v1/roles/{role_name}")
async def delete_role(
    role_name: str,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Delete a role"""
    success, result = execute_mosquitto_command(["deleteRole", role_name])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role_name} deleted"}

# Group Management Endpoints
@app.get("/api/v1/groups")
async def list_groups(request: Request, user: dict = Depends(require_management)):
    """List all groups"""
    success, result = execute_mosquitto_command(["listGroups"])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    # Return as direct array
    return result.split('\n')

@app.get("/api/v1/groups")
async def list_groups(
    request: Request,
    user: dict = Depends(require_management)
):
    """List all groups"""
    success, result = execute_mosquitto_command(["listGroups"])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"groups": result.split('\n')}

@app.get("/api/v1/groups/{group_name}")
async def get_group(
    group_name: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Get group details"""
    success, result = execute_mosquitto_command(["getGroup", group_name])
    if not success:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Group not found")
    return {"group": result}

@app.delete("/api/v1/groups/{group_name}")
async def delete_group(
    group_name: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Delete a group"""
    success, result = execute_mosquitto_command(["deleteGroup", group_name])
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Group {group_name} deleted"}

# Role Assignment Endpoints
@app.post("/api/v1/clients/{username}/roles")
async def add_client_role(
    username: str,
    role: RoleAssignment,
    request: Request,
    user: dict = Depends(require_management)
):
    """Add role to client"""
    success, result = execute_mosquitto_command(
        ["addClientRole", username, role.role_name, str(role.priority or 1)]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role.role_name} added to client {username}"}

@app.delete("/api/v1/clients/{username}/roles/{role_name}")
async def remove_client_role(
    username: str,
    role_name: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Remove role from client"""
    success, result = execute_mosquitto_command(
        ["removeClientRole", username, role_name]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role_name} removed from client {username}"}

@app.post("/api/v1/groups/{group_name}/roles")
async def add_group_role(
    group_name: str,
    role: RoleAssignment,
    request: Request,
    user: dict = Depends(require_management)
):
    """Add role to group"""
    success, result = execute_mosquitto_command(
        ["addGroupRole", group_name, role.role_name, str(role.priority or 1)]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role.role_name} added to group {group_name}"}

@app.delete("/api/v1/groups/{group_name}/roles/{role_name}")
async def remove_group_role(
    group_name: str,
    role_name: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Remove role from group"""
    success, result = execute_mosquitto_command(
        ["removeGroupRole", group_name, role_name]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Role {role_name} removed from group {group_name}"}

# Group Client Management Endpoints
@app.post("/api/v1/groups/{group_name}/clients")
async def add_client_to_group(
    group_name: str,
    data: dict,
    request: Request,
    user: dict = Depends(require_management)
):
    """Add client to group"""
    username = data.get("username")
    priority = data.get("priority")
    
    if not username:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Username required")
    
    cmd = ["addGroupClient", group_name, username]
    if priority:
        cmd.extend(["--priority", str(priority)])
    
    success, result = execute_mosquitto_command(cmd)
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Client {username} added to group {group_name}"}

@app.delete("/api/v1/groups/{group_name}/clients/{username}")
async def remove_client_from_group(
    group_name: str,
    username: str,
    request: Request,
    user: dict = Depends(require_management)
):
    """Remove client from group"""
    success, result = execute_mosquitto_command(
        ["removeGroupClient", group_name, username]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"Client {username} removed from group {group_name}"}

# ACL Management Endpoints
@app.post("/api/v1/roles/{role_name}/acls")
async def add_role_acl(
    role_name: str,
    acl: ACLRequest,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Add ACL to role"""
    if acl.aclType not in ["publishClientSend", "subscribeLiteral"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid ACL type")
    if acl.permission not in ["allow", "deny"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid permission")
    
    success, result = execute_mosquitto_command(
        ["addRoleACL", role_name, acl.aclType, acl.topic, acl.permission]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"ACL added to role {role_name}"}

@app.delete("/api/v1/roles/{role_name}/acls")
async def remove_role_acl(
    role_name: str,
    acl_type: ACLType,
    topic: str,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Remove ACL from role"""
    success, result = execute_mosquitto_command(
        ["removeRoleACL", role_name, str(acl_type.value), topic]
    )
    if not success:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=result)
    return {"message": f"ACL removed from role {role_name}"}

# Health Check
@app.get("/api/v1/health")
async def health_check(request: Request):
    """Service health check"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

if __name__ == "__main__":
    logger.info("Starting DynSec API")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("APP_PORT", "1000")),
        log_level="info"
    )