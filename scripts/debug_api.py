#!/usr/bin/env python3
"""
調試 CWA API 回應格式
"""

import os
import requests
import json
from dotenv import load_dotenv
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 載入環境變數
load_dotenv()

def debug_api_response():
    """調試 API 回應格式"""
    api_key = os.getenv('CWA_API_KEY')
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
    params = {
        'Authorization': api_key,
        'format': 'JSON'
    }
    
    try:
        # 設置 SSL 驗證選項，忽略證書驗證問題
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        
        # 儲存原始回應到檔案
        with open('outputs/api_response_debug.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print("API 回應已儲存至 outputs/api_response_debug.json")
        
        # 檢查資料結構
        print("\n=== API 回應結構 ===")
        print(f"頂層鍵值: {list(data.keys())}")
        
        if 'records' in data:
            print(f"records 鍵值: {list(data['records'].keys())}")
            
            if 'Station' in data['records']:
                stations = data['records']['Station']
                print(f"Station 資料型態: {type(stations)}")
                
                if isinstance(stations, list) and len(stations) > 0:
                    print(f"第一個測站的鍵值: {list(stations[0].keys())}")
                    
                    # 檢查第一個測站的詳細結構
                    first_station = stations[0]
                    print(f"\n=== 第一個測站詳細資料 ===")
                    print(f"測站ID: {first_station.get('stationId', 'N/A')}")
                    print(f"測站名稱: {first_station.get('stationName', 'N/A')}")
                    
                    if 'geoInfo' in first_station:
                        print(f"geoInfo 鍵值: {list(first_station['geoInfo'].keys())}")
                    
                    if 'weatherElement' in first_station:
                        print(f"weatherElement 鍵值: {list(first_station['weatherElement'].keys())}")
                    
                    # 顯示完整的第一個測站資料
                    print(f"\n=== 完整第一個測站資料 ===")
                    print(json.dumps(first_station, ensure_ascii=False, indent=2))
        
    except Exception as e:
        print(f"錯誤: {e}")

if __name__ == "__main__":
    debug_api_response()
