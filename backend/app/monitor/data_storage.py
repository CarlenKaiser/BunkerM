# data_storage.py
import sqlite3
from datetime import datetime, timedelta, timezone
import os
import json
import threading
from typing import Dict, List, Any
from contextlib import contextmanager

class HistoricalDataStorage:
    def __init__(self, db_path="/app/monitor/data/historical_data.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections with proper cleanup"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=30)
            # Enable WAL mode for better concurrency
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA synchronous=NORMAL;')
            conn.execute('PRAGMA cache_size=1000;')
            conn.execute('PRAGMA temp_store=memory;')
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()

    def _init_db(self):
        """Initialize database with proper schema validation"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. First create the stats table with all columns
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        data_type TEXT NOT NULL,
                        json_data TEXT NOT NULL,
                        timestamp TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 2. Verify the table has the created_at column
                cursor.execute("PRAGMA table_info(stats)")
                columns = [col[1] for col in cursor.fetchall()]
                
                # 3. Add column if it doesn't exist
                if 'created_at' not in columns:
                    print("Adding missing created_at column to stats table")
                    cursor.execute("ALTER TABLE stats ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                
                # 4. Now create indexes safely
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_type ON stats(data_type)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON stats(timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_type_timestamp ON stats(data_type, timestamp)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON stats(created_at)")
                
                # 5. Create daily_message_counts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS daily_message_counts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT UNIQUE NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_message_date ON daily_message_counts(date)")
                
                conn.commit()
    
    def _load_all_data(self) -> Dict[str, List]:
        """Load all data with better error handling and performance"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                data = {
                    "daily_messages": [],
                    "hourly": [],
                    "daily": []
                }
                
                try:
                    # Load daily messages from dedicated table first
                    cursor.execute("""
                        SELECT date, count FROM daily_message_counts 
                        WHERE date >= date('now', '-7 days')
                        ORDER BY date
                    """)
                    for row in cursor.fetchall():
                        data["daily_messages"].append({
                            "date": row[0],
                            "count": row[1]
                        })
                    
                    # If no data in dedicated table, try legacy format
                    if not data["daily_messages"]:
                        cursor.execute("SELECT json_data FROM stats WHERE data_type = 'daily_messages'")
                        for row in cursor.fetchall():
                            try:
                                item = json.loads(row[0])
                                data["daily_messages"].append(item)
                            except json.JSONDecodeError as e:
                                print(f"Error parsing daily_messages JSON: {e}")
                    
                    # Load hourly data
                    cursor.execute("""
                        SELECT json_data FROM stats 
                        WHERE data_type = 'hourly' 
                        AND timestamp >= datetime('now', '-24 hours')
                        ORDER BY timestamp
                    """)
                    for row in cursor.fetchall():
                        try:
                            item = json.loads(row[0])
                            data["hourly"].append(item)
                        except json.JSONDecodeError as e:
                            print(f"Error parsing hourly JSON: {e}")
                    
                except Exception as e:
                    print(f"Error loading data: {e}")
                
                return data
    
    def _save_data_item(self, data_type: str, item: Dict, timestamp: str = None):
        """Save a single data item with better error handling"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        "INSERT INTO stats (data_type, json_data, timestamp) VALUES (?, ?, ?)",
                        (data_type, json.dumps(item), timestamp)
                    )
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    raise e
    
    def _clean_old_data(self, data_type: str = None, hours: int = None, days: int = None):
        """Enhanced cleanup with flexible time ranges"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    if data_type == "hourly" and hours:
                        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
                        cursor.execute(
                            "DELETE FROM stats WHERE data_type = 'hourly' AND timestamp < ?", 
                            (cutoff.isoformat(),)
                        )
                    elif data_type == "daily_messages" and days:
                        cutoff_date = (datetime.now() - timedelta(days=days)).date().isoformat()
                        # Clean from both tables
                        cursor.execute(
                            "DELETE FROM daily_message_counts WHERE date < ?", 
                            (cutoff_date,)
                        )
                        cursor.execute(
                            """DELETE FROM stats 
                               WHERE data_type = 'daily_messages' 
                               AND json_extract(json_data, '$.date') < ?""", 
                            (cutoff_date,)
                        )
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Error cleaning old data: {e}")

    def ensure_file_exists(self):
        """Initialize the database - now handled in __init__"""
        pass  # Database is automatically initialized in __init__

    def load_data(self):
        """Load data with better error handling"""
        try:
            return self._load_all_data()
        except Exception as e:
            print(f"Error loading data: {e}")
            return {
                "daily_messages": [],
                "hourly": [],
                "daily": []
            }

    def save_data(self, data):
        """Bulk save data (used for migrations/full updates)"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # Clear existing data
                    cursor.execute("DELETE FROM stats")
                    cursor.execute("DELETE FROM daily_message_counts")
                    
                    # Save daily messages to dedicated table
                    for item in data.get("daily_messages", []):
                        cursor.execute(
                            """INSERT OR REPLACE INTO daily_message_counts (date, count) 
                               VALUES (?, ?)""",
                            (item["date"], item["count"])
                        )
                    
                    # Save hourly data
                    for item in data.get("hourly", []):
                        cursor.execute(
                            "INSERT INTO stats (data_type, json_data, timestamp) VALUES (?, ?, ?)",
                            ("hourly", json.dumps(item), item["timestamp"])
                        )
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Error saving data: {e}")
                    raise

    def update_daily_messages(self, message_count: int):
        """Update daily message count using dedicated table"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                    
                    # Use INSERT OR IGNORE then UPDATE for upsert behavior
                    cursor.execute(
                        """INSERT OR IGNORE INTO daily_message_counts (date, count) 
                           VALUES (?, 0)""",
                        (current_date,)
                    )
                    
                    cursor.execute(
                        """UPDATE daily_message_counts 
                           SET count = count + ?, updated_at = CURRENT_TIMESTAMP 
                           WHERE date = ?""",
                        (message_count, current_date)
                    )
                    
                    # Clean old data (keep 7 days)
                    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
                    cursor.execute("DELETE FROM daily_message_counts WHERE date < ?", (cutoff_date,))
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Error updating daily messages: {e}")

    def add_hourly_data(self, bytes_received: float, bytes_sent: float):
        """Add hourly data point with automatic cleanup"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    current_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
                    
                    data_item = {
                        'timestamp': current_time,
                        'bytes_received': bytes_received,
                        'bytes_sent': bytes_sent
                    }
                    
                    cursor.execute(
                        "INSERT INTO stats (data_type, json_data, timestamp) VALUES (?, ?, ?)",
                        ("hourly", json.dumps(data_item), current_time)
                    )
                    
                    # Clean data older than 24 hours
                    cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')
                    cursor.execute(
                        "DELETE FROM stats WHERE data_type = 'hourly' AND timestamp < ?",
                        (cutoff_time,)
                    )
                    
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    print(f"Error adding hourly data: {e}")
                except Exception as e:
                    conn.rollback()
                    print(f"Error adding hourly data: {e}")
    
    # Keep all remaining methods exactly the same
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Helper to parse timestamps consistently"""
        try:
            if timestamp_str.endswith('Z'):
                return datetime.fromisoformat(timestamp_str[:-1]).replace(tzinfo=timezone.utc)
            elif '+' in timestamp_str or timestamp_str.count(':') > 2:
                return datetime.fromisoformat(timestamp_str)
            else:
                return datetime.fromisoformat(timestamp_str).replace(tzinfo=timezone.utc)
        except:
            return datetime.fromisoformat(timestamp_str.replace('Z', '')).replace(tzinfo=timezone.utc)
    
    def get_hourly_data(self):
        """Get hourly byte rate data with better performance"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # Get data from last 24 hours, ordered by timestamp
                    cursor.execute("""
                        SELECT json_data FROM stats 
                        WHERE data_type = 'hourly' 
                        AND timestamp >= datetime('now', '-24 hours')
                        ORDER BY timestamp ASC
                    """)
                    
                    hourly_data = []
                    for row in cursor.fetchall():
                        try:
                            item = json.loads(row[0])
                            hourly_data.append(item)
                        except json.JSONDecodeError as e:
                            print(f"Error parsing hourly data JSON: {e}")
                    
                    return {
                        'timestamps': [entry['timestamp'] for entry in hourly_data],
                        'bytes_received': [entry['bytes_received'] for entry in hourly_data],
                        'bytes_sent': [entry['bytes_sent'] for entry in hourly_data]
                    }
                    
                except Exception as e:
                    print(f"Error getting hourly data: {e}")
                    return {
                        'timestamps': [],
                        'bytes_received': [],
                        'bytes_sent': []
                    }

    def get_daily_messages(self):
        """Get daily message counts for the last 7 days with better performance"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # Try dedicated table first
                    cursor.execute("""
                        SELECT date, count FROM daily_message_counts 
                        WHERE date >= date('now', '-7 days')
                        ORDER BY date ASC
                    """)
                    
                    rows = cursor.fetchall()
                    if rows:
                        return {
                            'dates': [row[0] for row in rows],
                            'counts': [row[1] for row in rows]
                        }
                    
                    # Fallback to legacy format
                    cursor.execute("SELECT json_data FROM stats WHERE data_type = 'daily_messages'")
                    daily_data = []
                    for row in cursor.fetchall():
                        try:
                            item = json.loads(row[0])
                            daily_data.append(item)
                        except json.JSONDecodeError as e:
                            print(f"Error parsing daily messages JSON: {e}")
                    
                    if not daily_data:
                        return {
                            'dates': [],
                            'counts': []
                        }
                    
                    # Sort and limit to last 7 days
                    daily_data = sorted(daily_data, key=lambda x: x['date'])[-7:]
                    
                    return {
                        'dates': [entry['date'] for entry in daily_data],
                        'counts': [entry['count'] for entry in daily_data]
                    }
                    
                except Exception as e:
                    print(f"Error getting daily messages: {e}")
                    return {
                        'dates': [],
                        'counts': []
                    }
    
    def get_stats_summary(self):
        """Get a summary of stored data for monitoring"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    # Count hourly records
                    cursor.execute("SELECT COUNT(*) FROM stats WHERE data_type = 'hourly'")
                    hourly_count = cursor.fetchone()[0]
                    
                    # Count daily message records
                    cursor.execute("SELECT COUNT(*) FROM daily_message_counts")
                    daily_count = cursor.fetchone()[0]
                    
                    # Get latest timestamps
                    cursor.execute("""
                        SELECT MAX(timestamp) FROM stats WHERE data_type = 'hourly'
                    """)
                    latest_hourly = cursor.fetchone()[0]
                    
                    cursor.execute("SELECT MAX(updated_at) FROM daily_message_counts")
                    latest_daily = cursor.fetchone()[0]
                    
                    return {
                        'hourly_records': hourly_count,
                        'daily_records': daily_count,
                        'latest_hourly_data': latest_hourly,
                        'latest_daily_data': latest_daily,
                        'database_size_mb': os.path.getsize(self.db_path) / (1024 * 1024) if os.path.exists(self.db_path) else 0
                    }
                    
                except Exception as e:
                    print(f"Error getting stats summary: {e}")
                    return {
                        'hourly_records': 0,
                        'daily_records': 0,
                        'latest_hourly_data': None,
                        'latest_daily_data': None,
                        'database_size_mb': 0
                    }