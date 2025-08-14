# Enhanced data storage with performance optimizations
import json
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
import threading
import time

class HistoricalDataStorage:
    def __init__(self, filename="/app/monitor/data/historical_data.json"):
        self.filename = filename
        self.max_age_days = 7
        self._data_cache = None
        self._cache_lock = threading.Lock()
        self._last_load_time = 0
        self._cache_ttl = 30  # Cache for 30 seconds
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self.ensure_file_exists()

    def _should_refresh_cache(self) -> bool:
        """Check if cache should be refreshed"""
        return (self._data_cache is None or 
                time.time() - self._last_load_time > self._cache_ttl)

    def load_data(self) -> Dict:
        """Load data with caching to improve performance"""
        with self._cache_lock:
            if not self._should_refresh_cache():
                return self._data_cache.copy()
            
            try:
                if not os.path.exists(self.filename):
                    self.ensure_file_exists()
                
                with open(self.filename, 'r') as f:
                    data = json.load(f)
                    
                # Ensure all required keys exist
                if 'daily_messages' not in data:
                    data['daily_messages'] = []
                if 'hourly' not in data:
                    data['hourly'] = []
                if 'daily' not in data:
                    data['daily'] = []
                
                # Limit data size to prevent memory issues
                data['hourly'] = data['hourly'][-1000:]  # Keep last 1000 entries
                data['daily_messages'] = data['daily_messages'][-100:]  # Keep last 100 entries
                
                self._data_cache = data
                self._last_load_time = time.time()
                return data.copy()
                
            except Exception as e:
                print(f"Error loading data: {e}")
                default_data = {
                    "daily_messages": [],
                    "hourly": [],
                    "daily": []
                }
                self._data_cache = default_data
                self._last_load_time = time.time()
                return default_data.copy()

    def save_data(self, data: Dict):
        """Save data and invalidate cache"""
        try:
            # Create backup before saving
            backup_file = f"{self.filename}.backup"
            if os.path.exists(self.filename):
                import shutil
                shutil.copy2(self.filename, backup_file)
            
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Update cache
            with self._cache_lock:
                self._data_cache = data.copy()
                self._last_load_time = time.time()
                
        except Exception as e:
            print(f"Error saving data: {e}")
            # Try to restore backup
            backup_file = f"{self.filename}.backup"
            if os.path.exists(backup_file):
                import shutil
                shutil.copy2(backup_file, self.filename)

    def get_hourly_data(self) -> Dict:
        """Get hourly byte rate data with performance optimization"""
        try:
            data = self.load_data()
            hourly_data = data.get('hourly', [])
            
            # Limit the amount of data returned
            max_entries = 500  # Limit to 500 entries
            if len(hourly_data) > max_entries:
                hourly_data = hourly_data[-max_entries:]
            
            timestamps = []
            bytes_received = []
            bytes_sent = []
            
            for entry in hourly_data:
                timestamp = entry.get('timestamp', '')
                
                # Quick timestamp validation
                if timestamp and len(timestamp) > 10:
                    timestamps.append(timestamp)
                    bytes_received.append(entry.get('bytes_received', 0))
                    bytes_sent.append(entry.get('bytes_sent', 0))
            
            return {
                'timestamps': timestamps,
                'bytes_received': bytes_received,
                'bytes_sent': bytes_sent
            }
        except Exception as e:
            print(f"Error getting hourly data: {e}")
            return {
                'timestamps': [],
                'bytes_received': [],
                'bytes_sent': []
            }

    def get_daily_messages(self) -> Dict:
        """Get daily message counts with performance optimization"""
        try:
            data = self.load_data()
            daily_messages = data.get('daily_messages', [])
            
            if not daily_messages:
                return {
                    'dates': [],
                    'counts': [],
                    'timestamps': []
                }
                
            # Sort and limit to last 30 days maximum
            daily_data = sorted(daily_messages, key=lambda x: x.get('date', ''))[-30:]
            
            dates = []
            counts = []
            timestamps = []
            current_time = datetime.now().isoformat()
            
            for entry in daily_data:
                dates.append(entry.get('date', ''))
                counts.append(entry.get('count', 0))
                
                # Handle timestamp efficiently
                if 'timestamp' in entry:
                    timestamps.append(entry['timestamp'])
                else:
                    # Create timestamp for end of day
                    try:
                        date_str = entry.get('date', '')
                        if date_str and len(date_str) == 10:  # YYYY-MM-DD format
                            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                            end_of_day = date_obj.replace(hour=23, minute=59, second=59)
                            timestamps.append(end_of_day.isoformat())
                        else:
                            timestamps.append(current_time)
                    except:
                        timestamps.append(current_time)
            
            return {
                'dates': dates,
                'counts': counts,
                'timestamps': timestamps
            }
        except Exception as e:
            print(f"Error getting daily messages: {e}")
            return {
                'dates': [],
                'counts': [],
                'timestamps': []
            }

    def add_hourly_data(self, bytes_received: float, bytes_sent: float):
        """Add hourly data with batching for performance"""
        try:
            data = self.load_data()
            current_timestamp = datetime.now().isoformat()
            
            data['hourly'].append({
                'timestamp': current_timestamp,
                'bytes_received': float(bytes_received),
                'bytes_sent': float(bytes_sent)
            })
            
            # Clean old data more efficiently
            cutoff_time = datetime.now() - timedelta(hours=24)
            cutoff_timestamp = cutoff_time.isoformat()
            
            # Remove old entries (keep only last 24 hours)
            data['hourly'] = [
                entry for entry in data['hourly']
                if entry.get('timestamp', '') >= cutoff_timestamp
            ]
            
            # Limit total entries as safety measure
            if len(data['hourly']) > 1000:
                data['hourly'] = data['hourly'][-1000:]
            
            self.save_data(data)
            
        except Exception as e:
            print(f"Error adding hourly data: {e}")