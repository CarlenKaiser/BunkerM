# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.

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
from datetime import datetime, timedelta
import json
import os
import logging
from logging.handlers import RotatingFileHandler
from data_storage import HistoricalDataStorage
import socket
import uvicorn
from contextlib import asynccontextmanager
import firebase_admin
from firebase_admin import credentials, auth

# Environment variable loading
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Warning: python-dotenv not installed. Using environment variables directly.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler(
    'api_activity.log',
    maxBytes=10000000,
    backupCount=5
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

# MQTT Settings
MOSQUITTO_ADMIN_USERNAME = os.getenv("MOSQUITTO_ADMIN_USERNAME")
MOSQUITTO_ADMIN_PASSWORD = os.getenv("MOSQUITTO_ADMIN_PASSWORD")
MOSQUITTO_IP = os.getenv("MOSQUITTO_IP", "127.0.0.1")
MOSQUITTO_PORT = int(os.getenv("MOSQUITTO_PORT", "1900"))

# Security settings
security = HTTPBearer()
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost").split(",")

# Monitored MQTT topics
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
        self.messages_sent = 0
        self.subscriptions = 0
        self.retained_messages = 0
        self.connected_clients = 0
        self.bytes_received_15min = 0.0
        self.bytes_sent_15min = 0.0
        self.message_counter = MessageCounter()
        self.data_storage = HistoricalDataStorage()
        self.last_storage_update = datetime.now()
        self.messages_history = deque(maxlen=15)
        self.published_history = deque(maxlen=15)
        self.last_messages_sent = 0
        self.last_update = datetime.now()
        
        for _ in range(15):
            self.messages_history.append(0)
            self.published_history.append(0)

    def format_number(self, number: int) -> str:
        if number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)

    def increment_user_messages(self):
        with self._lock:
            self.message_counter.increment_count()

    def update_storage(self):
        now = datetime.now()
        if (now - self.last_storage_update).total_seconds() >= 180:
            try:
                self.data_storage.add_hourly_data(
                    float(self.bytes_received_15min),
                    float(self.bytes_sent_15min)
                )
                self.last_storage_update = now
            except Exception as e:
                logger.error(f"Error updating storage: {e}")

    def update_message_rates(self):
        now = datetime.now()
        if (now - self.last_update).total_seconds() >= 60:
            with self._lock:
                published_rate = max(0, self.messages_sent - self.last_messages_sent)
                self.published_history.append(published_rate)
                self.last_messages_sent = self.messages_sent
                self.last_update = now

    def get_stats(self) -> Dict:
        self.update_message_rates()
        self.update_storage()
        
        with self._lock:
            actual_subscriptions = max(0, self.subscriptions - 2)
            actual_connected_clients = max(0, self.connected_clients - 1)
            total_messages = self.message_counter.get_total_count()
            hourly_data = self.data_storage.get_hourly_data()
            daily_messages = self.data_storage.get_daily_messages()
            
            return {
                "total_connected_clients": actual_connected_clients,
                "total_messages_received": self.format_number(total_messages),
                "total_subscriptions": actual_subscriptions,
                "retained_messages": self.retained_messages,
                "messages_history": list(self.messages_history),
                "published_history": list(self.published_history),
                "bytes_stats": hourly_data,
                "daily_message_stats": daily_messages
            }

class MessageCounter:
    def __init__(self, file_path="message_counts.json"):
        self.file_path = file_path
        self.daily_counts = self._load_counts()

    def _load_counts(self) -> Dict[str, int]:
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r') as f:
                    data = json.load(f)
                    return {item['timestamp'].split()[0]: item['message_counter'] 
                           for item in data}
            except json.JSONDecodeError:
                return {}
        return {}

    def _save_counts(self):
        data = [
            {"timestamp": f"{date} 00:00", "message_counter": count}
            for date, count in self.daily_counts.items()
        ]
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def increment_count(self):
        today = datetime.now().date().isoformat()
        self.daily_counts[today] = self.daily_counts.get(today, 0) + 1
        cutoff_date = (datetime.now() - timedelta(days=7)).date().isoformat()
        self.daily_counts = {
            date: count 
            for date, count in self.daily_counts.items() 
            if date >= cutoff_date
        }
        self._save_counts()

    def get_total_count(self) -> int:
        return sum(self.daily_counts.values())

# Initialize MQTT Stats
mqtt_stats = MQTTStats()
limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    client = connect_mqtt()
    client.loop_start()
    yield
    client.loop_stop()

app = FastAPI(
    title="MQTT Monitor API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

async def verify_firebase_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
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
            'is_moderator': user_role in ['admin', 'moderator'],
            'can_view_stats': user_role in ['admin', 'moderator', 'viewer']
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

async def require_admin(user: dict = Depends(verify_firebase_token)) -> dict:
    if not user.get('is_admin', False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

async def require_moderator(user: dict = Depends(verify_firebase_token)) -> dict:
    if not user.get('is_moderator', False):
        raise HTTPException(status_code=403, detail="Moderator or admin access required")
    return user

async def require_stats_access(user: dict = Depends(verify_firebase_token)) -> dict:
    logger.info(f"Checking stats access for user: {user}")
    if not user.get('can_view_stats', False):
        logger.warning(f"User {user.get('email')} denied stats access. Role: {user.get('role')}")
        raise HTTPException(status_code=403, detail="Insufficient permissions to view statistics")
    return user

async def log_request(request: Request):
    logger.info(
        f"Request: {request.method} {request.url} "
        f"Client: {request.client.host} "
        f"User-Agent: {request.headers.get('user-agent')}"
    )

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

def on_message(client, userdata, msg):
    if msg.topic in MONITORED_TOPICS:
        try:
            if msg.topic in ["$SYS/broker/load/bytes/received/15min", "$SYS/broker/load/bytes/sent/15min"]:
                value = float(msg.payload.decode())
            else:
                value = int(msg.payload.decode())
                
            attr_name = MONITORED_TOPICS[msg.topic]
            with mqtt_stats._lock:
                setattr(mqtt_stats, attr_name, value)
        except ValueError as e:
            logger.error(f"Error processing message from {msg.topic}: {e}")
    elif not msg.topic.startswith('$SYS/'):
        mqtt_stats.increment_user_messages()

def connect_mqtt():
    try:
        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                logger.info(f"Connected to MQTT Broker at {MOSQUITTO_IP}:{MOSQUITTO_PORT}!")
                client.subscribe([("$SYS/broker/#", 0), ("#", 0)])
            else:
                logger.error(f"Failed to connect to MQTT broker, return code {rc}")

        client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        client.username_pw_set(MOSQUITTO_ADMIN_USERNAME, MOSQUITTO_ADMIN_PASSWORD)
        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(MOSQUITTO_IP, MOSQUITTO_PORT, 60)
        return client
    
    except Exception as e:
        logger.error(f"Connection to MQTT broker failed: {e}")
        dummy_client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
        dummy_client.loop_start = lambda: None
        dummy_client.loop_stop = lambda: None
        return dummy_client

@app.get("/api/v1/stats")
@limiter.limit("30/minute")
async def get_mqtt_stats(
    request: Request,
    user: dict = Depends(require_stats_access)
):
    """Get MQTT statistics - requires stats viewing permission"""
    await log_request(request)
    
    try:
        stats = mqtt_stats.get_stats()
        stats["mqtt_connected"] = mqtt_stats.connected_clients > 0
        
        if not stats["mqtt_connected"]:
            stats["connection_error"] = f"MQTT broker connection failed. Check if Mosquitto is running on {MOSQUITTO_IP}:{MOSQUITTO_PORT}"
        
        response = JSONResponse(content=stats)
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
        
    except Exception as e:
        logger.error(f"Unexpected error in get_stats endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/v1/admin/users")
async def list_users(
    admin_user: dict = Depends(require_admin),
    limit: int = 100
):
    """List all users (Admin only)"""
    try:
        users = []
        for user in auth.list_users(max_results=limit).users:
            users.append({
                'uid': user.uid,
                'email': user.email,
                'role': (user.custom_claims or {}).get('role', 'user'),
                'created_at': user.user_metadata.creation_timestamp.isoformat() if user.user_metadata.creation_timestamp else None
            })
        
        return {"users": users, "total_count": len(users)}
        
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list users")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    try:
        port = int(os.getenv("APP_PORT", "1001"))
        host = os.getenv("APP_HOST", "0.0.0.0")
        
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.settimeout(1)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            test_socket.bind((host, port))
        except socket.error:
            port = 1002
        finally:
            test_socket.close()
        
        logging.basicConfig(level=logging.WARNING)
        logger.info(f"Starting MQTT Monitor API on {host}:{port}")
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except Exception as e:
        logger.critical(f"Failed to start application: {e}")