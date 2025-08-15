#!/bin/bash
set -e  # Exit on any error

# Colors for output (from Claude)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] SUCCESS:${NC} $1"
}

log "Starting enhanced MQTT Monitor with Background Data Collection..."

# Create necessary directories (merged from both scripts)
log "Creating directory structure..."
mkdir -p /var/log/supervisor
mkdir -p /var/log/nginx
mkdir -p /var/log/mosquitto
mkdir -p /data
mkdir -p /var/log/api
mkdir -p /app/monitor/data
mkdir -p /tmp/mosquitto_backups
mkdir -p /run/nginx

# Create log files if they don't exist (merged from both)
log "Setting up log files..."
touch /var/log/supervisor/auth-api.err.log
touch /var/log/supervisor/auth-api.out.log
touch /var/log/nginx/access.log
touch /var/log/nginx/error.log
touch /var/log/mosquitto/mosquitto.log
touch /var/log/mosquitto/mosquitto.err.log
touch /var/log/api/api_activity.log
touch /var/log/supervisor/nginx.out.log
touch /var/log/supervisor/nginx.err.log
touch /var/log/supervisor/supervisord.log

# Set permissions (merged with your original ownership settings)
log "Setting permissions..."
chown -R root:root /var/log/supervisor
chown -R nginx:nginx /var/log/nginx
chown -R mosquitto:mosquitto /var/log/mosquitto
chmod -R 755 /var/log/supervisor
chmod -R 755 /var/log/nginx
chmod -R 755 /var/log/mosquitto
chmod -R 755 /var/log/api
chmod -R 755 /usr/share/nginx/html
chmod 755 /data

# Ensure mosquitto_passwd file exists and has correct permissions (your original)
log "Configuring Mosquitto authentication..."
touch /etc/mosquitto/mosquitto_passwd
chown mosquitto:mosquitto /etc/mosquitto/mosquitto_passwd
chmod 600 /etc/mosquitto/mosquitto_passwd  # Your stricter permission

# Additional permissions from Claude (preserving your ownership)
chown -R mosquitto:mosquitto /var/lib/mosquitto
chmod -R 775 /var/lib/mosquitto
chown -R root:root /app
chmod -R 755 /app

# Initialize database if needed (from Claude)
log "Initializing database..."
if [ ! -f "/app/monitor/data/historical_data.db" ]; then
    log "Creating new SQLite database..."
    python3 -c "
import sys
sys.path.append('/app/monitor')
from data_storage import HistoricalDataStorage
storage = HistoricalDataStorage()
print('Database initialized successfully')
"
    success "Database created at /app/monitor/data/historical_data.db"
else
    log "Database already exists, checking integrity..."
    sqlite3 /app/monitor/data/historical_data.db "PRAGMA integrity_check;" > /dev/null
    success "Database integrity check passed"
fi

# Test MQTT connection parameters (from Claude)
log "Testing MQTT configuration..."
if [ -z "$MOSQUITTO_ADMIN_USERNAME" ] || [ -z "$MOSQUITTO_ADMIN_PASSWORD" ]; then
    warn "MQTT credentials not set, using defaults"
    export MOSQUITTO_ADMIN_USERNAME=${MOSQUITTO_ADMIN_USERNAME:-"bunker"}
    export MOSQUITTO_ADMIN_PASSWORD=${MOSQUITTO_ADMIN_PASSWORD:-"bunker"}
fi

# Kill any existing processes (from Claude)
log "Cleaning up existing processes..."
pkill nginx || true
pkill mosquitto || true
sleep 2

# Run configuration script (from Claude)
log "Setting up runtime configuration..."
if [ -f "/docker-entrypoint.d/config-env.sh" ]; then
    /docker-entrypoint.d/config-env.sh
    success "Runtime configuration applied"
else
    warn "Runtime configuration script not found"
fi

# Validate critical files exist (UPDATED with your config path)
log "Validating system files..."
REQUIRED_FILES=(
    "/etc/mosquitto/mosquitto.conf"
    "/app/monitor/main.py"
    "/app/monitor/data_storage.py"
    "/etc/supervisord.conf"  # YOUR ORIGINAL CONFIG PATH
    "/usr/share/nginx/html/index.html"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        error "Required file missing: $file"
        exit 1
    fi
done
success "All required files present"

# Test Python imports (from Claude)
log "Testing Python dependencies..."
python3 -c "
import sys
sys.path.append('/app/monitor')
try:
    import fastapi
    import paho.mqtt.client as mqtt_client
    import sqlite3
    from data_storage import HistoricalDataStorage
    print('All Python dependencies available')
except ImportError as e:
    print(f'Missing dependency: {e}')
    sys.exit(1)
" || {
    error "Python dependency check failed"
    exit 1
}
success "Python dependencies verified"

# Start supervisor with startup order info (from Claude)
log "Starting Supervisor to manage all services..."
log "Services will start in this order:"
log "  1. Mosquitto MQTT Broker"
log "  2. Wait for Mosquitto readiness"
log "  3. Monitor API (with background data collection)"
log "  4. Config API"
log "  5. Auth API"
log "  6. Nginx Web Server"
log "  7. Health Check Monitor"

success "All initialization complete. Starting services..."

# Start supervisor (YOUR ORIGINAL COMMAND AND PATH)
exec /usr/bin/supervisord -n -c /etc/supervisord.conf