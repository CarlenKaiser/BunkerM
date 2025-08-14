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
import asyncio
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
from functools import lru_cache
import time

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

class MQTTStats:
    def __init__(self):
        # Initialize thread lock for thread-safe operations
        self._lock = threading.Lock()
        
        # Initialize all MQTT stats attributes with default values
        self.messages_sent = 0
        self.subscriptions = 0
        self.retained_messages = 0
        self.connected_clients = 0
        self.bytes_received_15min = 0.0
        self.bytes_sent_15min = 0.0
        
        # Initialize message counter and data storage
        self.message_counter = MessageCounter()
        try:
            self.data_storage = HistoricalDataStorage()
        except Exception as e:
            logger.warning(f"HistoricalDataStorage not available, using mock: {e}")
            self.data_storage = self._create_mock_storage()
        
        # Initialize timing variables
        self.last_storage_update = datetime.now()
        self.last_update = datetime.now()
        self.last_messages_sent = 0
        
        # Initialize deques for storing historical data
        self.messages_history = deque(maxlen=15)
        self.published_history = deque(maxlen=15)
        
        # Initialize timestamp deques for different metrics
        self.metrics_timestamps = deque(maxlen=100)
        self.messages_timestamps = deque(maxlen=100)
        self.subscriptions_timestamps = deque(maxlen=100)
        self.clients_timestamps = deque(maxlen=100)
        self.retained_timestamps = deque(maxlen=100)
        
        # Initialize caching attributes
        self._stats_cache = {}
        self._cache_ttl = 5  # Cache for 5 seconds
        self._last_cache_time = 0
        
        # Initialize history with zeros
        for _ in range(15):
            self.messages_history.append(0)
            self.published_history.append(0)
        
        logger.info("MQTTStats initialized successfully")

    def _create_mock_storage(self):
        """Create a mock storage object if the real one isn't available"""
        class MockStorage:
            def get_hourly_data(self):
                return {"timestamps": [], "bytes_received": [], "bytes_sent": []}
            
            def get_daily_messages(self):
                return {"dates": [], "counts": [], "timestamps": []}
            
            def add_hourly_data(self, bytes_received, bytes_sent):
                pass
                
            def store_data(self, *args, **kwargs):
                pass
        
        return MockStorage()

    def format_number(self, number: int) -> str:
        """Format large numbers with appropriate suffixes"""
        if number >= 1_000_000:
            return f"{number/1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number/1_000:.1f}K"
        return str(number)

    def increment_user_messages(self):
        """Increment the count of user messages"""
        with self._lock:
            self.message_counter.increment_count()
            # Record timestamp when messages are received
            now = datetime.now().isoformat()
            self.messages_timestamps.append(now)

    def update_metric_timestamp(self, metric_type: str):
        """Update timestamp for a specific metric type"""
        now = datetime.now().isoformat()
        with self._lock:
            if metric_type == "subscriptions":
                self.subscriptions_timestamps.append(now)
            elif metric_type == "clients":
                self.clients_timestamps.append(now)
            elif metric_type == "retained":
                self.retained_timestamps.append(now)
            
            # Always update general metrics timestamp
            self.metrics_timestamps.append(now)

    def update_storage(self):
        """Update the historical data storage"""
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
        """Update message rate tracking"""
        now = datetime.now()
        if (now - self.last_update).total_seconds() >= 60:
            with self._lock:
                published_rate = max(0, self.messages_sent - self.last_messages_sent)
                self.published_history.append(published_rate)
                self.last_messages_sent = self.messages_sent
                self.last_update = now

    @lru_cache(maxsize=10)
    def _get_cached_hourly_data(self, cache_key: str):
        """Cached version of hourly data retrieval"""
        return self.data_storage.get_hourly_data()
    
    @lru_cache(maxsize=10) 
    def _get_cached_daily_data(self, cache_key: str):
        """Cached version of daily data retrieval"""
        return self.data_storage.get_daily_messages()

    def get_stats(self, include_timestamps: bool = False) -> Dict:
        """Get comprehensive MQTT statistics with optional timestamps"""
        current_time = time.time()
        cache_key = f"stats_{include_timestamps}_{int(current_time // self._cache_ttl)}"
        
        # Return cached result if available and fresh
        if (cache_key in self._stats_cache and 
            current_time - self._last_cache_time < self._cache_ttl):
            return self._stats_cache[cache_key]
        
        # Generate fresh stats
        try:
            self.update_message_rates()
            self.update_storage()
            
            with self._lock:
                # Adjust for admin connections (subtract monitoring clients)
                actual_subscriptions = max(0, self.subscriptions - 2)
                actual_connected_clients = max(0, self.connected_clients - 1)
                total_messages = self.message_counter.get_total_count()
                
                # Use cached data retrieval with cache key based on time
                hourly_cache_key = f"hourly_{int(current_time // 60)}"  # Cache for 1 minute
                daily_cache_key = f"daily_{int(current_time // 300)}"   # Cache for 5 minutes
                
                hourly_data = self._get_cached_hourly_data(hourly_cache_key)
                daily_messages = self._get_cached_daily_data(daily_cache_key)
                
                stats = {
                    "total_connected_clients": actual_connected_clients,
                    "total_messages_received": self.format_number(total_messages),
                    "total_subscriptions": actual_subscriptions,
                    "retained_messages": self.retained_messages,
                    "messages_history": list(self.messages_history),
                    "published_history": list(self.published_history),
                    "bytes_stats": hourly_data,
                    "daily_message_stats": daily_messages
                }
                
                # Add timestamps if requested
                if include_timestamps:
                    current_timestamp = datetime.now().isoformat()
                    
                    # Limit timestamp arrays to prevent large payloads
                    max_timestamps = 50
                    
                    stats.update({
                        "stats_timestamp": current_timestamp,
                        "message_stats_timestamps": list(self.messages_timestamps)[-max_timestamps:],
                        "subscription_stats_timestamps": list(self.subscriptions_timestamps)[-max_timestamps:],
                        "client_stats_timestamps": list(self.clients_timestamps)[-max_timestamps:],
                        "retained_stats_timestamps": list(self.retained_timestamps)[-max_timestamps:]
                    })
                    
                    # Add timestamps to daily_message_stats if available
                    if isinstance(stats["daily_message_stats"], dict) and "dates" in stats["daily_message_stats"]:
                        dates = stats["daily_message_stats"]["dates"]
                        if len(dates) <= 20:  # Only add timestamps for reasonable number of dates
                            timestamps = []
                            for date_str in dates:
                                try:
                                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                                    timestamp = date_obj.replace(hour=23, minute=59, second=59).isoformat()
                                    timestamps.append(timestamp)
                                except ValueError:
                                    timestamps.append(current_timestamp)
                            stats["daily_message_stats"]["timestamps"] = timestamps
                
                # Cache the result
                self._stats_cache[cache_key] = stats
                self._last_cache_time = current_time
                
                # Clean old cache entries
                if len(self._stats_cache) > 20:
                    old_keys = [k for k in self._stats_cache.keys() if k != cache_key]
                    for old_key in old_keys[:10]:  # Remove 10 oldest entries
                        del self._stats_cache[old_key]
                
                return stats
                
        except Exception as e:
            logger.error(f"Error generating stats: {e}")
            # Return minimal stats on error
            return {
                "total_connected_clients": 0,
                "total_messages_received": "0",
                "total_subscriptions": 0,
                "retained_messages": 0,
                "messages_history": [],
                "published_history": [],
                "bytes_stats": {"timestamps": [], "bytes_received": [], "bytes_sent": []},
                "daily_message_stats": {"dates": [], "counts": [], "timestamps": []},
                "mqtt_connected": False,
                "connection_error": "Error retrieving stats"
            }

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
                old_value = getattr(mqtt_stats, attr_name, 0)
                setattr(mqtt_stats, attr_name, value)
                
                # Update timestamps when values change
                if old_value != value:
                    if attr_name == "subscriptions":
                        mqtt_stats.update_metric_timestamp("subscriptions")
                    elif attr_name == "connected_clients":
                        mqtt_stats.update_metric_timestamp("clients")
                    elif attr_name == "retained_messages":
                        mqtt_stats.update_metric_timestamp("retained")
                        
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
    include_timestamps: bool = False,
    user: dict = Depends(require_stats_access)
):
    """Get MQTT statistics - requires stats viewing permission"""
    await log_request(request)
    
    try:
        # Set a timeout for stats generation
        start_time = time.time()
        
        # Run stats generation in a separate thread to avoid blocking
        loop = asyncio.get_event_loop()
        stats = await asyncio.wait_for(
            loop.run_in_executor(None, mqtt_stats.get_stats, include_timestamps),
            timeout=10.0  # 10 second timeout
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Stats generated in {processing_time:.2f}s")
        
        stats["mqtt_connected"] = mqtt_stats.connected_clients > 0
        stats["processing_time"] = round(processing_time, 2)
        
        if not stats["mqtt_connected"]:
            stats["connection_error"] = f"MQTT broker connection failed. Check if Mosquitto is running on {MOSQUITTO_IP}:{MOSQUITTO_PORT}"
        
        response = JSONResponse(content=stats)
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response
        
    except asyncio.TimeoutError:
        logger.error("Stats generation timed out")
        raise HTTPException(status_code=504, detail="Request timed out while generating statistics")
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