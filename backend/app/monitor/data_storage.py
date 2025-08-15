# data_storage.py
import sqlite3
from datetime import datetime, timedelta, timezone
import os
import json
from typing import Dict, List, Any

class HistoricalDataStorage:
    def __init__(self, db_path="/app/monitor/data/historical_data.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = self._init_db()
    
    def _init_db(self):
        """Initialize database with JSON-compatible schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Single table that mimics the JSON structure
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_type TEXT NOT NULL,  # 'hourly', 'daily_messages', or 'daily'
            json_data TEXT NOT NULL,  # Stores exact JSON structure
            timestamp TEXT           # For hourly data only
        )
        """)
        
        # Indexes for faster lookups
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_type ON stats(data_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON stats(timestamp)")
        
        conn.commit()
        return conn
    
    def _load_all_data(self) -> Dict[str, List]:
        """Load all data exactly matching the original JSON structure"""
        cursor = self.conn.cursor()
        data = {
            "daily_messages": [],
            "hourly": [],
            "daily": []
        }
        
        # Load daily messages
        cursor.execute("SELECT json_data FROM stats WHERE data_type = 'daily_messages'")
        data["daily_messages"] = [json.loads(row[0]) for row in cursor.fetchall()]
        
        # Load hourly data
        cursor.execute("SELECT json_data FROM stats WHERE data_type = 'hourly' ORDER BY timestamp")
        data["hourly"] = [json.loads(row[0]) for row in cursor.fetchall()]
        
        return data
    
    def _save_data_item(self, data_type: str, item: Dict, timestamp: str = None):
        """Save a single data item"""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO stats (data_type, json_data, timestamp) VALUES (?, ?, ?)",
            (data_type, json.dumps(item), timestamp)
        )
        self.conn.commit()
    
    def _clean_old_data(self, data_type: str, cutoff: str):
        """Remove old data based on timestamp or date"""
        cursor = self.conn.cursor()
        if data_type == "hourly":
            cursor.execute("DELETE FROM stats WHERE data_type = 'hourly' AND timestamp < ?", (cutoff,))
        else:  # daily_messages
            cursor.execute("""
                DELETE FROM stats 
                WHERE data_type = 'daily_messages' 
                AND json_extract(json_data, '$.date') < ?
            """, (cutoff,))
        self.conn.commit()

    # Below this point, ALL methods remain EXACTLY THE SAME as your original version
    # Only the storage implementation changed
    
    def ensure_file_exists(self):
        """Initialize the database with empty structure"""
        if not os.path.exists(self.db_path):
            initial_data = {
                "daily_messages": [],
                "hourly": [],
                "daily": []
            }
            self.save_data(initial_data)

    def load_data(self):
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
        try:
            # Clear existing data
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM stats")
            self.conn.commit()
            
            # Save all daily messages
            for item in data["daily_messages"]:
                self._save_data_item("daily_messages", item)
            
            # Save all hourly data
            for item in data["hourly"]:
                self._save_data_item("hourly", item, item["timestamp"])
            
        except Exception as e:
            print(f"Error saving data: {e}")
            self.conn.rollback()

    def update_daily_messages(self, message_count: int):
        """Identical to original, just uses SQLite backend"""
        data = self.load_data()
        current_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        found = False
        for entry in data['daily_messages']:
            if entry['date'] == current_date:
                entry['count'] += message_count
                found = True
                break

        if not found:
            data['daily_messages'].append({
                'date': current_date,
                'count': message_count
            })

        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
        data['daily_messages'] = [
            entry for entry in data['daily_messages']
            if entry['date'] >= cutoff_date
        ]

        self.save_data(data)

    def add_hourly_data(self, bytes_received: float, bytes_sent: float):
        """Identical to original, just uses SQLite backend"""
        data = self.load_data()
        current_time = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        data['hourly'].append({
            'timestamp': current_time,
            'bytes_received': bytes_received,
            'bytes_sent': bytes_sent
        })
        
        cutoff_time = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')
        data['hourly'] = [
            entry for entry in data['hourly']
            if self._parse_timestamp(entry['timestamp']) >= self._parse_timestamp(cutoff_time)
        ]
        
        self.save_data(data)
    
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
        """Get hourly byte rate data"""
        data = self.load_data()
        hourly_data = data.get('hourly', [])
        
        return {
            'timestamps': [entry['timestamp'] for entry in hourly_data],
            'bytes_received': [entry['bytes_received'] for entry in hourly_data],
            'bytes_sent': [entry['bytes_sent'] for entry in hourly_data]
        }

    def get_daily_messages(self):
        """Get daily message counts for the last 7 days"""
        try:
            data = self.load_data()
            if not data['daily_messages']:
                return {
                    'dates': [],
                    'counts': []
                }
                
            daily_data = sorted(data['daily_messages'], key=lambda x: x['date'])[-7:]
            
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