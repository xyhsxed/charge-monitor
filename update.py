import requests, json, os, time, datetime, csv

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DEVICE_LIST = [423297, 417598, 418297, 418351]
HISTORY_FILE = os.path.join(DATA_DIR, 'history.csv')
STATUS_FILE = os.path.join(DATA_DIR, 'status.json')
DAYS_TO_KEEP = 3

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def fetch_device_data(device_id):
    """Fetch data from the external API for a single device."""
    url = 'https://api.power.powerliber.com/client/1/device/port-list'
    params = {'device_id': device_id}
    try:
        response = requests.get(url, params=params, timeout=20)
        return response.json()
    except Exception as e:
        print(f"Request failed for {device_id}: {e}")
        return None

def clean_history_csv():
    """Keep only the last DAYS_TO_KEEP days of data in the CSV."""
    if not os.path.exists(HISTORY_FILE):
        return

    now = datetime.datetime.now()
    cutoff_time = now - datetime.timedelta(days=DAYS_TO_KEEP)
    
    new_rows = []
    header = None
    
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8', newline='') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return # Empty file
                
            for row in reader:
                try:
                    # Assuming timestamp is the first column [0]
                    row_time_str = row[0]
                    row_time = datetime.datetime.strptime(row_time_str, '%Y-%m-%d %H:%M:%S')
                    
                    if row_time > cutoff_time:
                        new_rows.append(row)
                except ValueError:
                    continue # Skip bad rows

        # Write back filtered data
        with open(HISTORY_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(new_rows)
            
        print(f"Cleaned history.csv. Kept {len(new_rows)} rows from the last {DAYS_TO_KEEP} days.")
        
    except Exception as e:
        print(f"Error cleaning history csv: {e}")

def main():
    now = datetime.datetime.now()
    timestamp = now.strftime('%Y-%m-%d %H:%M:%S')
    # Add 8 hours for CSV timestamp as requested
    csv_timestamp = (now + datetime.timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
    
    print(f"[{timestamp}] Starting data fetch...")
    
    frontend_data = [] # Data structure for frontend status.json
    history_records = [] # Data to append to history.csv

    for i, device_id in enumerate(DEVICE_LIST):
        raw_data = fetch_device_data(device_id)
        
        device_info = {
            "id": device_id,
            "name": f"桩{i+1}",
            "updated_at": timestamp,
            "ports": []
        }

        if raw_data:
            # Check for API error code inside json
            if raw_data.get('code') != 0:
                print(f"API Error for {device_id}: {raw_data}")
                device_info['error'] = f"API Error: {raw_data.get('msg', 'Unknown')}"
            
            response_list = raw_data.get('data', {}).get('list', [])
            
            # Normalize to 12 ports
            for p_idx in range(12): 
                if p_idx < len(response_list):
                    item = response_list[p_idx]
                    status = item.get('charge_status', 0)
                    online = item.get('online', 0)
                    current = item.get('current', 0)
                    
                    # For frontend
                    port_info = {
                        "port_number": p_idx + 1,
                        "current": current,
                        "voltage": item.get('voltage', 0),
                        "power": item.get('power', 0),
                        "status": status,
                        "online": online
                    }
                    device_info['ports'].append(port_info)
                    
                    # For history: Log if charging (status=1) or if online with current > 0
                    # To save space, maybe we only log when current > 0 or status == 1?
                    # User requested "history data record", usually implies all valid data points.
                    # But to save space, let's log everything for now, relying on the cleaner.
                    history_records.append([
                        csv_timestamp,
                        device_id,
                        p_idx + 1,
                        current,
                        item.get('voltage', 0),
                        item.get('power', 0),
                        status
                    ])
                else:
                    device_info['ports'].append({
                        "port_number": p_idx + 1,
                        "current": 0, "voltage": 0, "power": 0, "status": 0, "online": 0
                    })
        else:
             device_info['error'] = "Fetch failed"

        frontend_data.append(device_info)
        # Sleep briefly to be nice to the API
        time.sleep(1)

    # 1. Save Frontend Status JSON
    try:
        with open(STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(frontend_data, f, ensure_ascii=False)
        print("Updated status.json")
    except Exception as e:
        print(f"Error saving status.json: {e}")

    # 2. Append to History CSV
    try:
        file_exists = os.path.exists(HISTORY_FILE)
        with open(HISTORY_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "device_id", "port", "current", "voltage", "power", "charge_status"])
            writer.writerows(history_records)
        print(f"Appended {len(history_records)} records to history.csv")
    except Exception as e:
        print(f"Error appending to history.csv: {e}")

    # 3. Clean Old History
    clean_history_csv()

if __name__ == '__main__':
    main()
