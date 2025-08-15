#!/usr/bin/env python3
"""
MQTT Monitor Background Data Collection Verification Script
This script helps verify that background data collection is working properly
"""

import sys
import os
import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Add the monitor path
sys.path.append('/app/monitor')

try:
    from data_storage import HistoricalDataStorage
except ImportError:
    print("Error: Cannot import data_storage module")
    sys.exit(1)

class DataCollectionMonitor:
    """Monitor and verify background data collection"""
    
    def __init__(self, db_path="/app/monitor/data/historical_data.db"):
        self.db_path = db_path
        self.storage = HistoricalDataStorage(db_path)
    
    def check_database_exists(self) -> bool:
        """Check if database file exists"""
        exists = os.path.exists(self.db_path)
        print(f"Database exists: {exists}")
        if exists:
            size_mb = os.path.getsize(self.db_path) / (1024 * 1024)
            print(f"Database size: {size_mb:.2f} MB")
        return exists
    
    def check_database_structure(self) -> bool:
        """Verify database has correct structure"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check for required tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['stats', 'daily_message_counts']
            missing_tables = [table for table in required_tables if table not in tables]
            
            print(f"Database tables: {tables}")
            
            if missing_tables:
                print(f"Missing tables: {missing_tables}")
                return False
            
            # Check table structures
            cursor.execute("PRAGMA table_info(stats)")
            stats_columns = [col[1] for col in cursor.fetchall()]
            print(f"Stats table columns: {stats_columns}")
            
            cursor.execute("PRAGMA table_info(daily_message_counts)")
            daily_columns = [col[1] for col in cursor.fetchall()]
            print(f"Daily message counts columns: {daily_columns}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Error checking database structure: {e}")
            return False
    
    def check_recent_data(self) -> Dict[str, Any]:
        """Check for recently collected data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            results = {}
            
            # Check hourly data from last 24 hours
            cursor.execute("""
                SELECT COUNT(*) FROM stats 
                WHERE data_type = 'hourly' 
                AND timestamp >= datetime('now', '-24 hours')
            """)
            hourly_count = cursor.fetchone()[0]
            results['hourly_records_24h'] = hourly_count
            
            # Get latest hourly record
            cursor.execute("""
                SELECT timestamp, json_data FROM stats 
                WHERE data_type = 'hourly' 
                ORDER BY timestamp DESC LIMIT 1
            """)
            latest_hourly = cursor.fetchone()
            if latest_hourly:
                results['latest_hourly_timestamp'] = latest_hourly[0]
                try:
                    data = json.loads(latest_hourly[1])
                    results['latest_hourly_data'] = data
                except:
                    results['latest_hourly_data'] = "Error parsing JSON"
            
            # Check daily message data
            cursor.execute("SELECT COUNT(*) FROM daily_message_counts")
            daily_count = cursor.fetchone()[0]
            results['daily_records_total'] = daily_count
            
            # Get latest daily record
            cursor.execute("""
                SELECT date, count, updated_at FROM daily_message_counts 
                ORDER BY date DESC LIMIT 1
            """)
            latest_daily = cursor.fetchone()
            if latest_daily:
                results['latest_daily_date'] = latest_daily[0]
                results['latest_daily_count'] = latest_daily[1]
                results['latest_daily_updated'] = latest_daily[2]
            
            conn.close()
            return results
            
        except Exception as e:
            return {'error': str(e)}
    
    def simulate_data_collection(self, iterations=3):
        """Simulate background data collection to test functionality"""
        print(f"\nSimulating {iterations} data collection cycles...")
        
        for i in range(iterations):
            print(f"\nIteration {i+1}/{iterations}")
            
            # Simulate adding hourly data
            bytes_received = 1000 + (i * 100)
            bytes_sent = 800 + (i * 80)
            
            print(f"Adding hourly data: RX={bytes_received}, TX={bytes_sent}")
            self.storage.add_hourly_data(bytes_received, bytes_sent)
            
            # Simulate updating daily messages
            message_count = 10 + i
            print(f"Adding {message_count} to daily message count")
            self.storage.update_daily_messages(message_count)
            
            # Check what was added
            recent_data = self.check_recent_data()
            print(f"Total hourly records: {recent_data.get('hourly_records_24h', 'N/A')}")
            print(f"Total daily records: {recent_data.get('daily_records_total', 'N/A')}")
            
            time.sleep(1)  # Small delay between iterations
    
    def verify_api_health(self):
        """Check if the API is running and healthy"""
        try:
            import requests
            response = requests.get('http://localhost:1001/health', timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print("API Health Check:")
                for key, value in health_data.items():
                    print(f"  {key}: {value}")
                return True
            else:
                print(f"API health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"Cannot reach API: {e}")
            return False
    
    def run_full_check(self):
        """Run complete monitoring check"""
        print("=" * 60)
        print("MQTT Monitor Background Data Collection Check")
        print("=" * 60)
        
        print("\n1. Checking database file...")
        if not self.check_database_exists():
            print("❌ Database file does not exist!")
            return False
        
        print("\n2. Checking database structure...")
        if not self.check_database_structure():
            print("❌ Database structure is incorrect!")
            return False
        
        print("\n3. Checking recent data...")
        recent_data = self.check_recent_data()
        if 'error' in recent_data:
            print(f"❌ Error checking recent data: {recent_data['error']}")
            return False
        
        print("Recent data summary:")
        for key, value in recent_data.items():
            print(f"  {key}: {value}")
        
        # Determine if background collection seems to be working
        hourly_count = recent_data.get('hourly_records_24h', 0)
        has_recent_hourly = recent_data.get('latest_hourly_timestamp') is not None
        
        if hourly_count > 0 and has_recent_hourly:
            print("✅ Background data collection appears to be working!")
        else:
            print("⚠️  No recent data found. Background collection may not be running.")
            print("   This could be normal if the system just started.")
        
        print("\n4. Checking API health...")
        api_healthy = self.verify_api_health()
        
        print("\n5. Getting storage statistics...")
        try:
            stats = self.storage.get_stats_summary()
            print("Storage statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value}")
        except Exception as e:
            print(f"Could not get storage statistics: {e}")
        
        return True

def main():
    """Main function"""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        monitor = DataCollectionMonitor()
        
        if command == "check":
            monitor.run_full_check()
        elif command == "simulate":
            iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 3
            monitor.simulate_data_collection(iterations)
        elif command == "recent":
            data = monitor.check_recent_data()
            print(json.dumps(data, indent=2))
        else:
            print("Usage: python3 monitor_background.py [check|simulate|recent] [iterations]")
    else:
        monitor = DataCollectionMonitor()
        monitor.run_full_check()

if __name__ == "__main__":
    main()