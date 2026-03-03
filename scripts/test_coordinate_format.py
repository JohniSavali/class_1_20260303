#!/usr/bin/env python3
"""
測試 API 中的 TWD67 坐標格式
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

def test_coordinate_format():
    """測試坐標格式"""
    api_key = os.getenv('CWA_API_KEY')
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
    params = {
        'Authorization': api_key,
        'format': 'JSON'
    }
    
    try:
        response = requests.get(url, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        
        # 檢查前5個測站的坐標
        stations = data['records']['Station'][:5]
        
        print("=== 坐標格式分析 ===")
        for i, station in enumerate(stations, 1):
            print(f"\n{i}. {station['StationName']} ({station['StationId']})")
            coordinates = station['GeoInfo']['Coordinates']
            
            for coord in coordinates:
                print(f"  {coord['CoordinateName']}:")
                print(f"    緯度: {coord['StationLatitude']} ({float(coord['StationLatitude'])})")
                print(f"    經度: {coord['StationLongitude']} ({float(coord['StationLongitude'])})")
                print(f"    格式: {coord['CoordinateFormat']}")
                
                # 檢查是否為合理的度數範圍
                lat = float(coord['StationLatitude'])
                lon = float(coord['StationLongitude'])
                
                if 20 <= lat <= 26 and 118 <= lon <= 123:
                    print(f"    [OK] 合理的台灣度數坐標範圍")
                elif 0 <= lat <= 1000 and 0 <= lon <= 1000:
                    print(f"    [WARNING] 可能為投影坐標（公尺）")
                else:
                    print(f"    [WARNING] 未知坐標格式")
        
        print(f"\n=== 結論 ===")
        print("API 中的 TWD67 坐標已經是度數格式，不是投影坐標。")
        print("這意味著 API 提供的 TWD67 可能已經經過某種轉換，")
        print("或者標記為 TWD67 但實際上是另一種度數坐標系統。")
        
    except Exception as e:
        print(f"錯誤: {e}")

if __name__ == "__main__":
    test_coordinate_format()
