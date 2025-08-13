# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
#
# app/monitor/main.py
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from paho.mqtt import client as mqtt_client
import threading
from typing import Dict, List, Optional
from collections import deque
import time
from datetime import datetime, timedelta
import json
import os
import jwt
import secrets
import logging
from logging.handlers import RotatingFileHandler
import ssl
from data_storage import HistoricalDataStorage
import socket
import uvicorn
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, auth

# Add this for environment variable loading
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not installed, just print a warning
    print("Warning: python-dotenv not installed. Using environment variables directly.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(
    'api_activity.log',
    maxBytes=10000000,  # 10MB
    backupCount=5
)
logger.addHandler(handler)

# Firebase Admin SDK initialization
try:
    # Option 1: Use service account key file
    firebase_credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
    if firebase_credentials_path and os.path.exists(firebase_credentials_path):
        cred = credentials.Certificate(firebase_credentials_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized with service account key file")
    else:
        # Option 2: Use environment variables for service account
        firebase_config = {
            "type": "service_account",
            "project_id": os.getenv("FIREBASE_PROJECT_ID"),
            "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.getenv("FIREBASE_PRIVATE_KEY", "").replace('\\n', '\n'),
            "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
            "client_id": os.getenv("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_CERT_URL")
        }
        
        # Check if all required fields are present
        required_fields = ["project_id", "private_key", "client_email"]
        if all(firebase_config.get(field) for field in required_fields):
            cred = credentials.Certificate(firebase_config)
            firebase_admin.initialize_app(cred)
            logger.info("Firebase initialized with environment variables")
        else:
            logger.error("Firebase configuration incomplete. Missing required environment variables.")
            logger.error("Required: FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, FIREBASE_CLIENT_EMAIL")
            raise ValueError("Firebase configuration incomplete")
            
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}")
    raise

# MQTT Settings - Convert port to integer
MOSQUITTO_ADMIN_USERNAME = os.getenv("MOSQUITTO_ADMIN_USERNAME")
MOSQUITTO_ADMIN_PASSWORD = os.getenv("MOSQUITTO_ADMIN_PASSWORD")
MOSQUITTO_IP = os.getenv("MOSQUITTO_IP", "127.0.0.1")
# Convert to int with a default value
MOSQUITTO_PORT = int(os.getenv("MOSQUITTO_PORT", "1900"))

# Security settings for Firebase
security = HTTPBearer()

# Define the topics we're interested in
MONITORED_TOPICS = {
    "$SYS/broker/messages/sent": "messages_sent",
    "$SYS/broker/subscriptions/count": "subscriptions",
    "$SYS/broker/retained messages/count": "retained_messages",
    "$SYS/broker/clients/connected": "connected_clients",
    "$SYS/broker/load/bytes/received/15min": "bytes_received_15min",
    "$SYS/broker/load/bytes/sent/15min": "bytes_sent_15min"
}

class MQTTStats:
    def __init__(self):
        self._lock = threading.Lock()
        # Direct values from $SYS topics
        self.messages_sent = 0
        self.subscriptions = 0
        self.retained_messages = 0
        self.connected_clients = 0
        self.bytes_received_15min = 0.0
        self.bytes_sent_15min = 0.0
        
        # Initialize message counter
        self.message_counter = MessageCounter()
        
        # Initialize data storage
        self.data_storage = HistoricalDataStorage()
        self.last_storage_update = datetime.now()
        
        # Message rate tracking
        self.messages_history = deque(maxlen=15)
        self.published_history = deque(maxlen=15)
        self.last_messages_sent = 0
        self.last_update = datetime.now()
        
        # Initialize history with zeros
        for _ in range(15):
            self.messages_history.append(0)
            self.published_history.append(0)

    def format_number(self, number: int) -> str:
        """Format large numbers with K/M suffix"""
        if number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)

    def increment_user_messages(self):
        """Increment the message counter for non-$SYS messages"""
        with self._lock:
            self.message_counter.increment_count()

    def update_storage(self):
        """Update storage every 30 minutes"""
        now = datetime.now()
        if (now - self.last_storage_update).total_seconds() >= 180:  # 3 minutes
            try:
                self.data_storage.add_hourly_data(
                    float(self.bytes_received_15min),
                    float(self.bytes_sent_15min)
                )
                self.last_storage_update = now
            except Exception as e:
                logger.error(f"Error updating storage: {e}")

    def update_message_rates(self):
        """Calculate message rates for the last minute"""
        now = datetime.now()
        if (now - self.last_update).total_seconds() >= 60:
            with self._lock:
                published_rate = max(0, self.messages_sent - self.last_messages_sent)
                self.published_history.append(published_rate)
                self.last_messages_sent = self.messages_sent
                self.last_update = now

    def get_stats(self) -> Dict:
        """Get current MQTT statistics"""
        self.update_message_rates()
        self.update_storage()
        
        with self._lock:
            actual_subscriptions = max(0, self.subscriptions - 2)
            actual_connected_clients = max(0, self.connected_clients - 1)
            
            # Get total messages from last 7 days
            total_messages = self.message_counter.get_total_count()
            
            # Get hourly data
            hourly_data = self.data_storage.get_hourly_data()
            daily_messages = self.data_storage.get_daily_messages()
            
            return {
                "total_connected_clients": actual_connected_clients,
                "total_messages_received": self.format_number(total_messages),
                "total_subscriptions": actual_subscriptions,
                "retained_messages": self.retained_messages,
                "messages_history": list(self.messages_history),
                "published_history": list(self.published_history),
                "bytes_stats": hourly_data,  # This contains timestamps, bytes_received, and bytes_sent
                "daily_message_stats": daily_messages  # This contains dates and counts
            }

class MessageCounter:
    def __init__(self, file_path="message_counts.json"):
        self.file_path = file_path
        self.daily_counts = self._load_counts()

    def _load_counts(self) -> Dict[str, int]:
        """Load existing counts from JSON file"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    # Convert to dict with date string keys
                    return {item['timestamp'].split()[0]: item['message_counter'] 
                           for item in data}
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_counts(self):
        """Save counts to JSON file"""
        # Convert to list of dicts with timestamps
        data = [
            {
                "timestamp": f"{date} 00:00",
                "message_counter": count
            }
            for date, count in self.daily_counts.items()
        ]
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def increment_count(self):
        """Increment today's count and maintain 7-day window"""
        today = datetime.now().date().isoformat()
        
        # Increment or initialize today's count
        self.daily_counts[today] = self.daily_counts.get(today, 0) + 1

        # Remove counts older than 7 days
        cutoff_date = (datetime.now() - timedelta(days=7)).date().isoformat()
        self.daily_counts = {
            date: count 
            for date, count in self.daily_counts.items() 
            if date >= cutoff_date
        }

        # Save updated counts
        self._save_counts()

    def get_total_count(self) -> int:
        """Get sum of messages over last 7 days"""
        return sum(self.daily_counts.values())

# Initialize MQTT Stats
mqtt_stats = MQTTStats()

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# Define the lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code (previously in @app.on_event("startup"))
    client = connect_mqtt()
    client.loop_start()
    yield
    # Shutdown code if needed
    client.loop_stop()

# Initialize FastAPI app with versioning (only do this once!)
app = FastAPI(
    title="MQTT Monitor API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan  # Use the lifespan context manager
)

# Add state for limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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

async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify Firebase ID token and return user info with role-based claims"""
    try:
        # Extract the token from the Authorization header
        token = credentials.credentials
        
        # Verify the ID token with Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        
        # Get custom claims which include role information
        custom_claims = decoded_token.get('custom_claims', {})
        
        # Extract role from custom claims, default to 'user'
        user_role = custom_claims.get('role', 'user')
        permissions = custom_claims.get('permissions', [])
        
        # Log successful authentication (without sensitive data)
        logger.info(f"Authenticated user: {decoded_token.get('email', 'unknown')} (UID: {decoded_token.get('uid', 'unknown')}, Role: {user_role})")
        
        # Return user info that can be used in your endpoints
        user_info = {
            'uid': decoded_token['uid'],
            'email': decoded_token.get('email'),
            'name': decoded_token.get('name'),
            'role': user_role,
            'permissions': permissions,
            'verified': decoded_token.get('email_verified', False),
            'is_admin': user_role == 'admin',
            'is_moderator': user_role in ['admin', 'moderator'],
            'can_view_stats': user_role in ['admin', 'moderator', 'viewer']
        }
        
        return user_info
        
    except auth.InvalidIdTokenError:
        logger.error("Invalid Firebase ID token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
    except auth.ExpiredIdTokenError:
        logger.error("Expired Firebase ID token provided")
        raise HTTPException(
            status_code=401,
            detail="Authentication token has expired"
        )
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed"
        )

# Role-based dependency functions
async def require_admin(user: dict = Depends(verify_firebase_token)) -> dict:
    """Require admin role"""
    if not user.get('is_admin', False):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )
    return user

async def require_moderator(user: dict = Depends(verify_firebase_token)) -> dict:
    """Require moderator or admin role"""
    if not user.get('is_moderator', False):
        raise HTTPException(
            status_code=403,
            detail="Moderator or admin access required"
        )
    return user

async def require_stats_access(user: dict = Depends(verify_firebase_token)) -> dict:
    """Require permission to view stats"""
    if not user.get('can_view_stats', False):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to view statistics"
        )
    return user

async def log_request(request: Request):
    """Log API request details"""
    logger.info(
        f"Request: {request.method} {request.url} "
        f"Client: {request.client.host} "
        f"User-Agent: {request.headers.get('user-agent')} "
        f"Time: {datetime.now().isoformat()}"
    )

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

def on_message(client, userdata, msg):
    """Handle messages from MQTT broker"""
    if msg.topic in MONITORED_TOPICS:
        try:
            # Handle byte rate topics differently (they return floats)
            if msg.topic in ["$SYS/broker/load/bytes/received/15min", "$SYS/broker/load/bytes/sent/15min"]:
                value = float(msg.payload.decode())
                attr_name = MONITORED_TOPICS[msg.topic]
                with mqtt_stats._lock:
                    setattr(mqtt_stats, attr_name, value)
            else:
                value = int(msg.payload.decode())
                attr_name = MONITORED_TOPICS[msg.topic]
                with mqtt_stats._lock:
                    setattr(mqtt_stats, attr_name, value)
        except ValueError as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
    # Count non-$SYS messages
    elif not msg.topic.startswith('$SYS/'):
        mqtt_stats.increment_user_messages()

def connect_mqtt():
    """Connect to MQTT broker"""
    try:
        # Using the v5 callback format
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info(f"Connected to MQTT Broker at {MOSQUITTO_IP}:{MOSQUITTO_PORT}!")
                client.subscribe([
                    ("$SYS/broker/#", 0),
                    ("#", 0)
                ])
                logger.info("Subscribed to topics")
            else:
                logger.error(f"Failed to connect to MQTT broker, return code {rc}")
                error_codes = {
                    1: "Incorrect protocol version",
                    2: "Invalid client identifier",
                    3: "Server unavailable",
                    4: "Bad username or password",
                    5: "Not authorized"
                }
                logger.error(f"Error details: {error_codes.get(rc, 'Unknown error')}")

        # Use MQTTv5 client
        try:
            client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        except AttributeError:
            # Fall back to older MQTT client if necessary
            client = mqtt_client.Client(client_id="mqtt-monitor", protocol=mqtt_client.MQTTv5)
        
        client.username_pw_set(MOSQUITTO_ADMIN_USERNAME, MOSQUITTO_ADMIN_PASSWORD)
        client.on_connect = on_connect
        client.on_message = on_message
        
        logger.info(f"Attempting to connect to MQTT broker at {MOSQUITTO_IP}:{MOSQUITTO_PORT}")
        
        # Verify parameters
        if not MOSQUITTO_IP:
            logger.error("MOSQUITTO_IP is not set or is None")
            raise ValueError("MOSQUITTO_IP must be set")
            
        # Connect with proper parameters
        client.connect(MOSQUITTO_IP, MOSQUITTO_PORT, 60)  # Fixed: use variable not string
        return client
    
    except (ConnectionRefusedError, socket.error) as e:
        logger.error(f"Connection to MQTT broker failed: {e}")
        logger.error(f"Check if Mosquitto is running on {MOSQUITTO_IP}:{MOSQUITTO_PORT}")
        # Return a dummy client that won't crash your app
        try:
            dummy_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        except AttributeError:
            dummy_client = mqtt_client.Client(client_id="dummy-client", protocol=mqtt_client.MQTTv5)
        # Override methods to do nothing
        dummy_client.loop_start = lambda: None
        dummy_client.loop_stop = lambda: None
        return dummy_client
    except Exception as e:
        logger.error(f"Unexpected error connecting to MQTT broker: {e}")
        logger.exception(e)
        # Return a dummy client that won't crash your app
        try:
            dummy_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        except AttributeError:
            dummy_client = mqtt_client.Client(client_id="dummy-client", protocol=mqtt_client.MQTTv5)
        # Override methods to do nothing
        dummy_client.loop_start = lambda: None
        dummy_client.loop_stop = lambda: None
        return dummy_client

# API endpoints with role-based access
@app.get("/api/v1/stats")
@limiter.limit("30/minute")  # Rate limiting
async def get_mqtt_stats(
    request: Request,
    user: dict = Depends(require_stats_access)  # Only users with stats viewing permission
):
    """Get MQTT statistics - requires stats viewing permission"""
    await log_request(request)
    logger.info(f"Stats requested by user: {user.get('email', 'unknown')} (Role: {user.get('role', 'unknown')})")
    
    try:        
        try:
            stats = mqtt_stats.get_stats()
            
            # Add MQTT connection status
            mqtt_connected = mqtt_stats.connected_clients > 0
            stats["mqtt_connected"] = mqtt_connected
            
            # Role-based data filtering
            if user.get('role') == 'viewer':
                # Viewers get limited data
                limited_stats = {
                    "total_connected_clients": stats["total_connected_clients"],
                    "total_messages_received": stats["total_messages_received"],
                    "mqtt_connected": stats["mqtt_connected"],
                    "user": {
                        "email": user.get('email'),
                        "role": user.get('role')
                    }
                }
                stats = limited_stats
            elif user.get('is_moderator'):
                # Moderators and admins get full data
                if not mqtt_connected:
                    stats["connection_error"] = f"MQTT broker connection failed. Check if Mosquitto is running on {MOSQUITTO_IP}:{MOSQUITTO_PORT}"
                    logger.warning(f"Serving stats with MQTT disconnected warning: {MOSQUITTO_IP}:{MOSQUITTO_PORT}")
                else:
                    logger.info("Successfully retrieved stats with active MQTT connection")
                    
                # Add user info to response
                stats["user"] = {
                    "email": user.get('email'),
                    "uid": user.get('uid'),
                    "role": user.get('role')
                }
            
        except Exception as stats_error:
            logger.error(f"Error in mqtt_stats.get_stats(): {str(stats_error)}")
            logger.exception(stats_error)
            
            # Return partial stats with error flag
            stats = {
                "mqtt_connected": False,
                "connection_error": f"Error getting MQTT stats: {str(stats_error)}",
                "total_connected_clients": 0,
                "total_messages_received": "0",
                "total_subscriptions": 0,
                "retained_messages": 0,
                "messages_history": [0] * 15,
                "published_history": [0] * 15,
                "bytes_stats": {
                    "timestamps": [],
                    "bytes_received": [],
                    "bytes_sent": []
                },
                "daily_message_stats": {
                    "dates": [],
                    "counts": []
                },
                "user": {
                    "email": user.get('email'),
                    "uid": user.get('uid'),
                    "role": user.get('role')
                }
            }
        
        response = JSONResponse(content=stats)
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, DELETE, PUT"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Origin"] = os.getenv("FRONTEND_URL", "http://localhost:2000")
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in get_stats endpoint: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Admin-only endpoints
@app.post("/api/v1/admin/users/{uid}/role")
async def set_user_role(
    uid: str,
    role_data: dict,
    admin_user: dict = Depends(require_admin)
):
    """Set custom claims for a user (Admin only)"""
    try:
        new_role = role_data.get('role', 'user')
        permissions = role_data.get('permissions', [])
        
        # Validate role
        valid_roles = ['user', 'viewer', 'moderator', 'admin']
        if new_role not in valid_roles:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid role. Must be one of: {valid_roles}"
            )
        
        # Set custom claims
        custom_claims = {
            'role': new_role,
            'permissions': permissions,
            'updated_by': admin_user.get('email'),
            'updated_at': datetime.now().isoformat()
        }
        
        auth.set_custom_user_claims(uid, custom_claims)
        
        logger.info(f"Admin {admin_user.get('email')} set role '{new_role}' for user {uid}")
        
        return {
            "success": True,
            "message": f"Role updated to '{new_role}' for user {uid}",
            "updated_by": admin_user.get('email')
        }
        
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    except Exception as e:
        logger.error(f"Error setting user role: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to update user role"
        )

@app.get("/api/v1/admin/users")
async def list_users(
    admin_user: dict = Depends(require_admin),
    limit: int = 100
):
    """List all users (Admin only)"""
    try:
        users = []
        page = auth.list_users(max_results=limit)
        
        for user in page.users:
            users.append({
                'uid': user.uid,
                'email': user.email,
                'display_name': user.display_name,
                'email_verified': user.email_verified,
                'disabled': user.disabled,
                'custom_claims': user.custom_claims or {},
                'role': (user.custom_claims or {}).get('role', 'user'),
                'created_at': user.user_metadata.creation_timestamp.isoformat() if user.user_metadata.creation_timestamp else None
            })
        
        return {
            "users": users,
            "total_count": len(users)
        }
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to list users"
        )

# Moderator endpoints
@app.get("/api/v1/moderator/system-status")
async def get_system_status(
    moderator_user: dict = Depends(require_moderator)
):
    """Get system status information (Moderator+ only)"""
    try:
        return {
            "mqtt_broker": {
                "host": MOSQUITTO_IP,
                "port": MOSQUITTO_PORT,
                "connected": mqtt_stats.connected_clients > 0
            },
            "api_status": "running",
            "user_count": len(list(auth.list_users(max_results=1000).users)),
            "requested_by": {
                "email": moderator_user.get('email'),
                "role": moderator_user.get('role')
            }
        }
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to get system status"
        )

# Keep test endpoints without authentication for debugging
@app.get("/api/v1/test/mqtt-stats")
async def test_mqtt_stats():
    """Test endpoint to verify MQTT stats functionality"""
    try:
        if not mqtt_stats:
            return JSONResponse(
                status_code=500,
                content={"error": "MQTT stats not initialized"}
            )
            
        # Test basic functionality
        basic_info = {
            "messages_sent": mqtt_stats.messages_sent,
            "subscriptions": mqtt_stats.subscriptions,
            "connected_clients": mqtt_stats.connected_clients,
            "data_storage_initialized": hasattr(mqtt_stats, 'data_storage')
        }
        
        return JSONResponse(content=basic_info)
        
    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}")
        logger.exception(e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Test failed: {str(e)}"}
        )

@app.get("/api/v1/test/storage")
async def test_storage():
    """Test endpoint to verify storage functionality"""
    try:
        if not hasattr(mqtt_stats, 'data_storage'):
            return JSONResponse(
                status_code=500,
                content={"error": "Data storage not initialized"}
            )
            
        # Test storage functionality
        storage_info = {
            "file_exists": os.path.exists(mqtt_stats.data_storage.filename),
            "data": mqtt_stats.data_storage.load_data()
        }
        
        return JSONResponse(content=storage_info)
        
    except Exception as e:
        logger.error(f"Error in storage test endpoint: {str(e)}")
        logger.exception(e)
        return JSONResponse(
            status_code=500,
            content={"error": f"Storage test failed: {str(e)}"}
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    try:
        # Check if the port is already in use
        port = int(os.getenv("APP_PORT", "1001"))
        host = os.getenv("APP_HOST", "0.0.0.0")
        
        # Try to bind to the port to check if it's available
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        
        # Set SO_REUSEADDR option to avoid "address already in use" errors
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            test_socket.bind((host, port))
            port_available = True
        except socket.error:
            port_available = False
        finally:
            test_socket.close()
        
        if not port_available:
            logger.warning(f"Port {port} is already in use, switching to port 1002")
            port = 1002
        
        # Update logging level
        logging.basicConfig(level=logging.WARNING)
        
        # Run the application
        logger.info(f"Starting MQTT Monitor API on {host}:{port}")
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="warning"
        )
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")
        logger.exception(e)