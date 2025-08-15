# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
#
# app/dynsec/main.py
import logging
from fastapi import FastAPI, HTTPException, Security, Depends, Request, status, UploadFile, File, Form
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import firebase_admin
from firebase_admin import credentials, auth

""" from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi.responses import JSONResponse """
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import subprocess
import os
import json
import ssl
from dotenv import load_dotenv
from enum import Enum
from datetime import datetime, timedelta
import secrets
from logging.handlers import RotatingFileHandler
from pydantic import BaseModel, Field
from password_import import router as password_import_router
import uvicorn
# Load environment variables from .env file
load_dotenv()
security = HTTPBearer()

class RequestParams(BaseModel):
    nonce: Optional[str] = None
    timestamp: Optional[int] = None


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(
    "dynsec_api_activity.log", maxBytes=10000000, backupCount=5  # 10MB
)
logger.addHandler(handler)

# Firebase Admin SDK initialization
try:
    firebase_config_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if not firebase_config_path or not os.path.exists(firebase_config_path):
        raise ValueError("Firebase credentials file not found at specified path")
    
    cred = credentials.Certificate(firebase_config_path)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    raise

# Environment variables
MOSQUITTO_ADMIN_USERNAME = os.getenv("MOSQUITTO_ADMIN_USERNAME")
MOSQUITTO_ADMIN_PASSWORD = os.getenv("MOSQUITTO_ADMIN_PASSWORD")
MOSQUITTO_IP = os.getenv("MOSQUITTO_IP")
MOSQUITTO_PORT = os.getenv("MOSQUITTO_PORT")
API_KEY = os.getenv("API_KEY")

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# Base command for mosquitto_ctrl
DYNSEC_BASE_COMMAND = [
    "mosquitto_ctrl",
    "-h", os.getenv("MOSQUITTO_IP"),
    "-p", os.getenv("MOSQUITTO_PORT"),
    "-u", os.getenv("MOSQUITTO_ADMIN_USERNAME"),
    "-P", os.getenv("MOSQUITTO_ADMIN_PASSWORD"),
    "dynsec"
]

# Initialize FastAPI app with versioning
app = FastAPI(
    title="Mosquitto Management API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted Host middleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Import mosquitto password file
app.include_router(password_import_router, prefix="/api/v1")

async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    try:
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        user_role = decoded_token.get('role', 'user')
        
        logger.info(f"Authenticated user: {decoded_token.get('email', 'unknown')}")
        
        return {
            'uid': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'name': decoded_token.get('name'),
            'role': user_role,
            'verified': decoded_token.get('email_verified', False),
            'is_admin': user_role == 'admin',
            'is_moderator': user_role in ['admin', 'moderator']
        }
    except auth.InvalidIdTokenError:
        logger.error("Invalid Firebase ID token provided")
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    except auth.ExpiredIdTokenError:
        logger.error("Expired Firebase ID token provided")
        raise HTTPException(status_code=401, detail="Authentication token has expired")
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")

# Authorization dependencies
async def require_admin(user: dict = Depends(verify_firebase_token)) -> dict:
    if not user.get('is_admin', False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_moderator(user: dict = Depends(verify_firebase_token)) -> dict:
    if not user.get('is_moderator', False):
        raise HTTPException(status_code=403, detail="Moderator or admin access required")
    return user


async def log_request(request: Request):
    """Log API request details"""
    logger.info(
        f"Request: {request.method} {request.url} "
        f"Client: {request.client.host} "
        f"User-Agent: {request.headers.get('user-agent')} "
        f"Time: {datetime.now().isoformat()}"
    )


@app.middleware("https")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


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
    nonce: Optional[str] = None
    timestamp: Optional[int] = None


class GroupCreate(BaseModel):
    name: str
    textname: Optional[str] = None
    roles: Optional[List[str]] = None


class RoleAssignment(BaseModel):
    role_name: str
    priority: Optional[int] = 1


class GroupClientAssignment(BaseModel):
    client_username: str


# Define enums for ACL types and permissions
class ACLType(str, Enum):
    PUBLISH = "publishClientSend"
    SUBSCRIBE = "subscribeLiteral"


class Permission(str, Enum):
    ALLOW = "allow"
    DENY = "deny"


# Model for ACL request
class ACLRequest(BaseModel):
    topic: str = Field(..., description="MQTT topic")
    aclType: str = Field(
        ..., description="ACL type (publishClientSend or subscribeLiteral)"
    )
    permission: str = Field(..., description="Permission (allow or deny)")


# Mosquitto command execution with logging
def execute_mosquitto_command(command: list, input_data: str = None) -> tuple[bool, str]:
    try:
        full_command = DYNSEC_BASE_COMMAND + command
        logger.debug(f"Executing command: {' '.join(full_command)}")
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
        else:
            logger.error(f"Command failed: {stderr.strip()}")
            return False, stderr.strip()

    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        return False, str(e)

# Client management endpoints
@app.post("/api/v1/clients", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    request: Request,
    user: dict = Depends(require_admin) 
):
    await log_request(request)
    logger.info(f"Creating new client with username: {client.username}")

    try:
        # Command to create the client
        command = ["createClient", client.username]

        # Execute the createClient command
        success, result = execute_mosquitto_command(command)

        if not success:
            logger.error(f"Error creating client {client.username}: {result}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating client: {result}",
            )

        # Command to set the client password
        set_password_command = ["setClientPassword", client.username, client.password]

        # Execute the setClientPassword command
        success, result = execute_mosquitto_command(set_password_command)

        if not success:
            logger.error(
                f"Error setting password for client {client.username}: {result}"
            )
            # Try to cleanup the created client if password setting fails
            cleanup_command = ["deleteClient", client.username]
            execute_mosquitto_command(cleanup_command)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error setting password: {result}",
            )

        logger.info(f"Successfully created client: {client.username}")
        return ClientResponse(
            username=client.username,
            message="Client created and password set successfully",
            success=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating client {client.username}: {str(e)}")
        # Attempt cleanup on unexpected error
        try:
            cleanup_command = ["deleteClient", client.username]
            execute_mosquitto_command(cleanup_command)
        except:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# List Clients Endpoint
@app.get("/api/v1/clients")
async def list_clients(
    request: Request,
    user: dict = Depends(require_admin) 
):
    """List all clients"""
    await log_request(request)
    logger.info(f"Listing clients. Nonce: {nonce}, Timestamp: {timestamp}")

    try:
        command = ["listClients"]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to list clients: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info("Successfully retrieved client list")
        return {"clients": result}

    except Exception as e:
        logger.error(f"Unexpected error listing clients: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Get Single Client Endpoint
@app.get("/api/v1/clients/{username}")
async def get_client(
    username: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Get details for a specific client"""
    await log_request(request)
    logger.info(f"Fetching details for client: {username}")

    try:
        command = ["getClient", username]
        success, result = execute_mosquitto_command(command)

        if not success:
            logger.error(f"Client not found: {username}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client {username} not found",
            )

        # Parse the output
        try:
            lines = result.split("\n")
            client_info = {"username": "", "clientid": "", "roles": [], "groups": []}

            for line in lines:
                line = line.strip()
                if line.startswith("Username:"):
                    client_info["username"] = line.split("Username:")[1].strip()
                elif line.startswith("Clientid:"):
                    client_info["clientid"] = line.split("Clientid:")[1].strip()
                elif line.startswith("Roles:"):
                    role_info = line.split("Roles:")[1].strip()
                    if role_info:
                        role_parts = role_info.split("(")
                        role_name = role_parts[0].strip()
                        priority = (
                            role_parts[1].split(")")[0].replace("priority:", "").strip()
                        )
                        client_info["roles"].append(
                            {"name": role_name, "priority": priority}
                        )
                elif "priority:" in line:
                    if "(" in line and ")" in line:
                        parts = line.strip().split("(")
                        name = parts[0].strip()
                        priority = (
                            parts[1].split(")")[0].replace("priority:", "").strip()
                        )
                        if name:
                            if "Groups:" in line:
                                client_info["groups"] = []
                            client_info["groups"].append(
                                {"name": name, "priority": priority}
                            )

            logger.info(f"Successfully retrieved details for client: {username}")
            return {"client": client_info}

        except Exception as parse_error:
            logger.error(f"Error parsing client details: {str(parse_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing client details: {str(parse_error)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting client {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Enable Client Endpoint
@app.put("/api/v1/clients/{username}/enable")
async def enable_client(
    username: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Enable a specific MQTT client"""
    await log_request(request)
    logger.info(f"Enabling client: {username}")

    try:
        command = ["enableClient", username]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to enable client {username}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully enabled client: {username}")
        return {"message": f"Client {username} enabled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error enabling client {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Disable Client Endpoint
@app.put("/api/v1/clients/{username}/disable")
async def disable_client(
    username: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Disable a specific MQTT client"""
    await log_request(request)
    logger.info(f"Disabling client: {username}")

    try:
        command = ["disableClient", username]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to disable client {username}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully disabled client: {username}")
        return {"message": f"Client {username} disabled successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error disabling client {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Remove Client Endpoint
@app.delete("/api/v1/clients/{username}")
async def remove_client(
    username: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Remove a specific MQTT client"""
    await log_request(request)
    logger.info(f"Removing client: {username}")

    try:
        command = ["deleteClient", username]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to remove client {username}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully removed client: {username}")
        return {"message": f"Client {username} removed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing client {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Role Management Endpoints
@app.post("/api/v1/roles")
async def create_role(
    role: RoleCreate,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Create a new role"""
    await log_request(request)
    logger.info(f"Creating new role: {role.name}")

    try:
        command = ["createRole", role.name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to create role {role.name}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully created role: {role.name}")
        return {"message": f"Role {role.name} created successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating role {role.name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# List Roles Endpoint
@app.get("/api/v1/roles")
async def list_roles(
    request: Request,
    user: dict = Depends(require_admin) 
):
    """List all clients"""
    await log_request(request)
    logger.info(f"Listing clients. Nonce: {nonce}, Timestamp: {timestamp}")

    try:
        command = ["listRoles"]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to list roles: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info("Successfully retrieved role list")
        return {"roles": result}

    except Exception as e:
        logger.error(f"Unexpected error listing roles: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Get Role Details Endpoint
@app.get("/api/v1/roles/{role_name}")
async def get_role(
    role_name: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Get details for a specific role"""
    await log_request(request)
    logger.info(f"Fetching details for role: {role_name}")

    try:
        command = ["getRole", role_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Role not found: {role_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Role {role_name} not found",
            )

        try:
            lines = result.split("\n")
            acls = []

            for line in lines:
                line = line.strip()
                if "ACLs:" in line or any(
                    acl_type in line
                    for acl_type in ["publishClientSend", "subscribeLiteral"]
                ):
                    acl_info = (
                        line.split("ACLs:")[1].strip()
                        if "ACLs:" in line
                        else line.strip()
                    )

                    parts = [p.strip() for p in acl_info.split(":")]
                    if len(parts) >= 3:
                        acl_type = parts[0].strip()
                        permission = parts[1].strip()
                        topic_and_priority = parts[2].strip()

                        topic = topic_and_priority.split("(")[0].strip()
                        priority = "0"
                        if "(priority:" in topic_and_priority:
                            priority = (
                                topic_and_priority.split("priority:")[1]
                                .strip(")")
                                .strip()
                            )

                        acls.append(
                            {
                                "topic": topic,
                                "aclType": acl_type,
                                "permission": permission,
                                "priority": int(priority),
                            }
                        )

            logger.info(f"Successfully retrieved details for role: {role_name}")
            return {"role": role_name, "acls": acls}

        except Exception as parse_error:
            logger.error(f"Error parsing role details: {str(parse_error)}")
            return {
                "role": role_name,
                "acls": [],
                "raw_output": result,
                "error": str(parse_error),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting role {role_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Role Assignment Endpoints
@app.post("/api/v1/clients/{username}/roles")
async def add_client_role(
    username: str,
    role: RoleAssignment,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Assign a role to a client"""
    await log_request(request)
    logger.info(f"Assigning role {role.role_name} to client {username}")

    try:
        command = ["addClientRole", username, role.role_name, "1"]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to assign role {role.role_name} to client {username}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully assigned role {role.role_name} to client {username}")
        return {"message": f"Role {role.role_name} assigned to client {username}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error assigning role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Remove Role from Client
@app.delete("/api/v1/clients/{username}/roles/{role_name}")
async def remove_client_role(
    username: str,
    role_name: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Remove a role from a client"""
    await log_request(request)
    logger.info(f"Removing role {role_name} from client {username}")

    try:
        command = ["removeClientRole", username, role_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to remove role {role_name} from client {username}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully removed role {role_name} from client {username}")
        return {"message": f"Role {role_name} removed from client {username}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Add Role to Group
@app.post("/api/v1/groups/{group_name}/roles")
async def add_group_role(
    group_name: str,
    role: RoleAssignment,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Assign a role to a group"""
    await log_request(request)
    logger.info(f"Assigning role {role.role_name} to group {group_name}")

    try:
        command = ["addGroupRole", group_name, role.role_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to assign role {role.role_name} to group {group_name}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(
            f"Successfully assigned role {role.role_name} to group {group_name}"
        )
        return {"message": f"Role {role.role_name} assigned to group {group_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error assigning group role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Remove Role from Group
@app.delete("/api/v1/groups/{group_name}/roles/{role_name}")
async def remove_group_role(
    group_name: str,
    role_name: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Remove a role from a group"""
    await log_request(request)
    logger.info(f"Removing role {role_name} from group {group_name}")

    try:
        command = ["removeGroupRole", group_name, role_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to remove role {role_name} from group {group_name}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully removed role {role_name} from group {group_name}")
        return {"message": f"Role {role_name} removed from group {group_name}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing group role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Group Management Endpoints
@app.post("/api/v1/groups")
async def create_group(
    group: GroupCreate,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Create a new group"""
    await log_request(request)
    logger.info(f"Creating new group: {group.name}")

    try:
        command = ["createGroup", group.name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to create group {group.name}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully created group: {group.name}")
        return {"message": f"Group {group.name} created successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/api/v1/groups")
async def list_groups(
    request: Request,
    user: dict = Depends(require_admin) 
):
    """List all groups"""
    await log_request(request)
    logger.info("Fetching list of all groups")

    try:
        command = ["listGroups"]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to list groups: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info("Successfully retrieved group list")
        return {"groups": result}

    except Exception as e:
        logger.error(f"Unexpected error listing groups: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.get("/api/v1/groups/{group_name}")
async def get_group(
    group_name: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Get details for a specific group"""
    await log_request(request)
    logger.info(f"Fetching details for group: {group_name}")

    try:
        command = ["getGroup", group_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Group not found: {group_name}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group {group_name} not found",
            )

        try:
            # Parse the output
            lines = result.split("\n")
            group_info = {"name": "", "roles": [], "clients": []}

            for line in lines:
                line = line.strip()
                if line.startswith("Groupname:"):
                    group_info["name"] = line.split("Groupname:")[1].strip()
                elif line.startswith("Roles:"):
                    role_info = line.split("Roles:")[1].strip()
                    if role_info:
                        role_parts = role_info.split("(")
                        role_name = role_parts[0].strip()
                        priority = (
                            role_parts[1].split(")")[0].replace("priority:", "").strip()
                        )
                        group_info["roles"].append(
                            {"name": role_name, "priority": priority}
                        )
                elif (
                    line
                    and not line.startswith("Groupname:")
                    and not line.startswith("Roles:")
                ):
                    if line.startswith("Clients:"):
                        client = line.split("Clients:")[1].strip()
                        if client:
                            group_info["clients"].append(client)
                    else:
                        group_info["clients"].append(line.strip())

            logger.info(f"Successfully retrieved details for group: {group_name}")
            return {"group": group_info}

        except Exception as parse_error:
            logger.error(f"Error parsing group details: {str(parse_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error parsing group details: {str(parse_error)}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting group {group_name}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.delete("/api/v1/groups/{group_name}")
async def delete_group(
    group_name: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Delete a specific group"""
    await log_request(request)
    logger.info(f"Deleting group: {group_name}")

    try:
        command = ["deleteGroup", group_name]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to delete group {group_name}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully deleted group: {group_name}")
        return {"message": f"Group {group_name} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# Group Client Management Endpoints
@app.post("/api/v1/groups/{group_name}/clients")
async def add_client_to_group(
    group_name: str,
    data: dict,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Add a client to a group"""
    await log_request(request)

    username = data.get("username")
    priority = data.get("priority")

    if not username:
        logger.error("Username not provided in request")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required"
        )

    logger.info(f"Adding client {username} to group {group_name}")

    try:
        command = ["addGroupClient", group_name, username]

        if priority:
            command.extend(["--priority", str(priority)])

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to add client {username} to group {group_name}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully added client {username} to group {group_name}")
        return {
            "message": f"Client {username} added to group {group_name} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding client to group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


@app.delete("/api/v1/groups/{group_name}/clients/{username}")
async def remove_client_from_group(
    group_name: str,
    username: str,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Remove a client from a group"""
    await log_request(request)
    logger.info(f"Removing client {username} from group {group_name}")

    try:
        command = ["removeGroupClient", group_name, username]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(
                f"Failed to remove client {username} from group {group_name}: {result}"
            )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully removed client {username} from group {group_name}")
        return {
            "message": f"Client {username} removed from group {group_name} successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error removing client from group: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# ACL Management Endpoints
@app.post("/api/v1/roles/{role_name}/acls")
async def add_role_acl(
    role_name: str,
    acl: ACLRequest,
    request: Request,
    user: dict = Depends(require_admin) 
):
    """Add an ACL to a role"""
    await log_request(request)
    logger.info(f"Adding ACL to role {role_name}: {acl.dict()}")

    try:
        # Validate ACL type
        if acl.aclType not in ["publishClientSend", "subscribeLiteral"]:
            logger.error(f"Invalid ACL type: {acl.aclType}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid aclType. Must be 'publishClientSend' or 'subscribeLiteral'",
            )

        # Validate permission
        if acl.permission not in ["allow", "deny"]:
            logger.error(f"Invalid permission: {acl.permission}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid permission. Must be 'allow' or 'deny'",
            )

        command = ["addRoleACL", role_name, acl.aclType, acl.topic, acl.permission]

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Failed to add ACL to role {role_name}: {result}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result)

        logger.info(f"Successfully added ACL to role {role_name}")
        return {
            "message": f"ACL added successfully to role {role_name}",
            "details": {
                "role": role_name,
                "topic": acl.topic,
                "aclType": acl.aclType,
                "permission": acl.permission,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error adding ACL: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# remove role
@app.delete("/api/v1/roles/{role_name}")
async def delete_role(
    role_name: str,
    user: dict = Depends(require_admin) 
):
    command = ["deleteRole", role_name]
    success, result = execute_mosquitto_command(command)
    if not success:
        raise HTTPException(status_code=400, detail=result)
    return {"message": f"Role {role_name} deleted successfully"}


@app.delete("/api/v1/roles/{role_name}/acls")
async def remove_role_acl(
    role_name: str,
    acl_type: ACLType,
    topic: str,
    user: dict = Depends(require_admin) 
):
    try:
        logger.debug(f"Removing ACL from role {role_name}: {acl_type=}, {topic=}")

        command = ["removeRoleACL", role_name, str(acl_type.value), topic]

        logger.debug(f"Executing command: {' '.join(command)}")

        success, result = execute_mosquitto_command(command)
        if not success:
            logger.error(f"Command failed: {result}")
            raise HTTPException(status_code=400, detail=result)

        return {"message": f"ACL removed from role {role_name} successfully"}

    except Exception as e:
        logger.error(f"Error removing ACL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove ACL: {str(e)}")


# Add a health check endpoint
@app.get("/api/v1/health")
async def health_check(request: Request):
    """Health check endpoint"""
    await log_request(request)
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    }


if __name__ == "__main__":
    # Run the application
    logger.info(f"Starting DynSec API")
    uvicorn.run(app, host="0.0.0.0", port=1000)