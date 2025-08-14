# Copyright (c) 2025 BunkerM
#
# Licensed under the Apache License, Version 2.0 (the "License");
# You may not use this file except in compliance with the License.
# http://www.apache.org/licenses/LICENSE-2.0
# Distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND.
#
# app/monitor/data_storage.py
import json
from datetime import datetime, timedelta
import os

class HistoricalDataStorage:
    def __init__(self, filename="/app/monitor/data/historical_data.json"):
        self.filename = filename
        self.max_age_days = 7
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.filename), exist_ok=True)
        self.ensure_file_exists()

    def ensure_file_exists(self):
        """Initialize the JSON file with proper structure if it doesn't exist"""
        if not os.path.exists(self.filename):
            initial_data = {
                "daily_messages": [],  # For message counts
                "hourly": [],         # For bytes data
                "daily": []           # For bytes data
            }
            self.save_data(initial_data)

    def load_data(self):
        try:
            with open(self.filename, 'r') as f:
                data = json.load(f)
                # Ensure all required keys exist
                if 'daily_messages' not in data:
                    data['daily_messages'] = []
                if 'hourly' not in data:
                    data['hourly'] = []
                if 'daily' not in data:
                    data['daily'] = []
                return data
        except Exception as e:
            print(f"Error loading data: {e}")
            return {
                "daily_messages": [],
                "hourly": [],
                "daily": []
            }

    def save_data(self, data):
        try:
            with open(self.filename, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def update_daily_messages(self, message_count: int):
        """Update daily message count"""
        data = self.load_data()
        current_date = datetime.now().strftime('%Y-%m-%d')
        current_timestamp = datetime.now().isoformat()
        
        # Find today's entry
        found = False
        for entry in data['daily_messages']:
            if entry['date'] == current_date:
                entry['count'] += message_count
                entry['timestamp'] = current_timestamp  # Update timestamp
                found = True
                break

        # Add new entry if not found
        if not found:
            data['daily_messages'].append({
                'date': current_date,
                'count': message_count,
                'timestamp': current_timestamp
            })

        # Keep only last 7 days
        cutoff_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        data['daily_messages'] = [
            entry for entry in data['daily_messages']
            if entry['date'] >= cutoff_date
        ]

        self.save_data(data)

    def add_hourly_data(self, bytes_received: float, bytes_sent: float):
        """Add hourly byte rate data with ISO timestamp"""
        data = self.load_data()
        current_timestamp = datetime.now().isoformat()
        
        data['hourly'].append({
            'timestamp': current_timestamp,
            'bytes_received': bytes_received,
            'bytes_sent': bytes_sent
        })
        
        # Keep only last 24 hours of data
        cutoff_time = datetime.now() - timedelta(hours=24)
        data['hourly'] = [
            entry for entry in data['hourly']
            if datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00') if entry['timestamp'].endswith('Z') else entry['timestamp']) >= cutoff_time
        ]
        
        self.save_data(data)

    def get_hourly_data(self):
        """Get hourly byte rate data with proper timestamp format"""
        try:
            data = self.load_data()
            hourly_data = data.get('hourly', [])
            
            # Ensure timestamps are in ISO format
            timestamps = []
            bytes_received = []
            bytes_sent = []
            
            for entry in hourly_data:
                timestamp = entry.get('timestamp', '')
                
                # Convert old format timestamps to ISO if needed
                if timestamp and not timestamp.endswith('Z') and 'T' not in timestamp:
                    try:
                        # Handle old format: '2025-01-15 10:30'
                        dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M')
                        timestamp = dt.isoformat()
                    except ValueError:
                        # If parsing fails, use current time
                        timestamp = datetime.now().isoformat()
                
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

    def get_daily_messages(self):
        """Get daily message counts for the last 7 days with timestamps"""
        try:
            data = self.load_data()
            if not data['daily_messages']:  # If no data exists yet
                return {
                    'dates': [],
                    'counts': [],
                    'timestamps': []
                }
                
            # Sort by date and get last 7 days
            daily_data = sorted(data['daily_messages'], key=lambda x: x['date'])[-7:]
            
            dates = []
            counts = []
            timestamps = []
            
            for entry in daily_data:
                dates.append(entry['date'])
                counts.append(entry.get('count', 0))
                
                # Handle timestamp - create one if it doesn't exist
                if 'timestamp' in entry:
                    timestamps.append(entry['timestamp'])
                else:
                    # Create timestamp for end of day if not present
                    try:
                        date_obj = datetime.strptime(entry['date'], '%Y-%m-%d')
                        end_of_day = date_obj.replace(hour=23, minute=59, second=59)
                        timestamps.append(end_of_day.isoformat())
                    except ValueError:
                        timestamps.append(datetime.now().isoformat())
            
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

    def cleanup_old_data(self):
        """Remove data older than max_age_days"""
        try:
            data = self.load_data()
            cutoff_date = datetime.now() - timedelta(days=self.max_age_days)
            
            # Clean up hourly data
            data['hourly'] = [
                entry for entry in data['hourly']
                if datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00') if entry['timestamp'].endswith('Z') else entry['timestamp']) >= cutoff_date
            ]
            
            # Clean up daily messages
            cutoff_date_str = cutoff_date.strftime('%Y-%m-%d')
            data['daily_messages'] = [
                entry for entry in data['daily_messages']
                if entry['date'] >= cutoff_date_str
            ]
            
            self.save_data(data)
        except Exception as e:
            print(f"Error cleaning up old data: {e}")

    def get_stats_summary(self):
        """Get a summary of stored data for debugging"""
        try:
            data = self.load_data()
            return {
                'hourly_records': len(data.get('hourly', [])),
                'daily_message_records': len(data.get('daily_messages', [])),
                'oldest_hourly': data['hourly'][0]['timestamp'] if data.get('hourly') else None,
                'newest_hourly': data['hourly'][-1]['timestamp'] if data.get('hourly') else None,
                'oldest_daily': data['daily_messages'][0]['date'] if data.get('daily_messages') else None,
                'newest_daily': data['daily_messages'][-1]['date'] if data.get('daily_messages') else None
            }
        except Exception as e:
            print(f"Error getting stats summary: {e}")
            return {}