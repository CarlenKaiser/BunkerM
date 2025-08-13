# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

import logging
import os
from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv
from datetime import datetime
import uvicorn
import firebase_admin
from firebase_admin import credentials, auth

# Import routers
from mosquitto_config import router as mosquitto_config_router
from dynsec_config import router as dynsec_config_router

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = logging.handlers.RotatingFileHandler(
    "config_api_activity.log", 
    maxBytes=10000000,  # 10MB
    backupCount=5
)
logger.addHandler(handler)

# Environment variables
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")

# Initialize Firebase Admin SDK
try:
    cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    raise

# Initialize FastAPI app
app = FastAPI(
    title="Mosquitto Management API",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Security scheme
security = HTTPBearer()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

# Include routers with Firebase auth
app.include_router(
    mosquitto_config_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_firebase_token)]
)

app.include_router(
    dynsec_config_router,
    prefix="/api/v1",
    dependencies=[Depends(verify_firebase_token)]
)

async def verify_firebase_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Verify Firebase ID token and return user info"""
    try:
        token = credentials.credentials
        decoded_token = auth.verify_id_token(token)
        
        # Get custom claims (roles/permissions)
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
        logger.warning("Invalid Firebase ID token provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )
    except auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase ID token provided")
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
    """Require admin role"""
    if not user.get('is_admin', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

async def require_moderator(user: dict = Depends(verify_firebase_token)) -> dict:
    """Require moderator or admin role"""
    if not user.get('is_moderator', False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Moderator or admin access required"
        )
    return user

async def log_request(request: Request):
    """Log API request details"""
    logger.info(
        f"Request: {request.method} {request.url} "
        f"Client: {request.client.host} "
        f"User-Agent: {request.headers.get('user-agent')}"
    )

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

@app.get("/api/v1/health")
async def health_check(request: Request):
    """Health check endpoint"""
    await log_request(request)
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "service": "mosquitto-config-api"
    }

if __name__ == "__main__":
    PORT = int(os.getenv("CONFIG_API_PORT", "1005"))
    logger.info(f"Starting Config API on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)