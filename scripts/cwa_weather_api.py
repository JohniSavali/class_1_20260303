#!/usr/bin/env python3
"""
中央氣象署自動氣象站觀測 API 串接腳本
API: O-A0003-001 (自動氣象站觀測資料)
獲取全台即時氣溫數據
"""

import os
import requests
import json
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv
import urllib3

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 載入環境變數
load_dotenv()

class CWAWeatherAPI:
    def __init__(self):
        self.api_key = os.getenv('CWA_API_KEY')
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"  # 自動氣象站觀測資料
        
        if not self.api_key:
            raise ValueError("CWA_API_KEY not found in environment variables")
    
    def fetch_weather_data(self):
        """獲取全台自動氣象站觀測資料"""
        url = f"{self.base_url}/{self.dataset_id}"
        params = {
            'Authorization': self.api_key,
            'format': 'JSON'
        }
        
        try:
            # 設置 SSL 驗證選項，忽略證書驗證問題
            response = requests.get(url, params=params, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 請求失敗: {e}")
            return None
    
    def parse_temperature_data(self, data):
        """解析氣溫數據"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        for record in records:
            try:
                station_info = {
                    'station_id': record['StationId'],
                    'station_name': record['StationName'],
                    'latitude': float(record['GeoInfo']['Coordinates'][1]['StationLatitude']),  # 使用 WGS84 座標
                    'longitude': float(record['GeoInfo']['Coordinates'][1]['StationLongitude']),
                    'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None,
                    'humidity': float(record['WeatherElement']['RelativeHumidity']) if record['WeatherElement']['RelativeHumidity'] else None,
                    'observation_time': record['ObsTime']['DateTime'],
                    'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                    'weather': record['WeatherElement'].get('Weather', ''),
                    'wind_speed': float(record['WeatherElement']['WindSpeed']) if record['WeatherElement']['WindSpeed'] else None,
                    'wind_direction': float(record['WeatherElement']['WindDirection']) if record['WeatherElement']['WindDirection'] else None,
                    'air_pressure': float(record['WeatherElement']['AirPressure']) if record['WeatherElement']['AirPressure'] else None
                }
                stations.append(station_info)
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def save_to_csv(self, stations_data, filename=None):
        """將資料儲存為 CSV 檔案"""
        if not stations_data:
            print("沒有資料可儲存")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"outputs/weather_stations_{timestamp}.csv"
        
        # 確保 outputs 目錄存在
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        df = pd.DataFrame(stations_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"資料已儲存至: {filename}")
        return filename
    
    def get_temperature_summary(self, stations_data):
        """獲取氣溫統計摘要"""
        if not stations_data:
            return None
        
        temperatures = [s['temperature'] for s in stations_data if s['temperature'] is not None]
        
        if not temperatures:
            return None
        
        summary = {
            'total_stations': len(stations_data),
            'valid_temperature_readings': len(temperatures),
            'max_temp': max(temperatures),
            'min_temp': min(temperatures),
            'avg_temp': sum(temperatures) / len(temperatures),
            'max_temp_station': next(s['station_name'] for s in stations_data if s['temperature'] == max(temperatures)),
            'min_temp_station': next(s['station_name'] for s in stations_data if s['temperature'] == min(temperatures))
        }
        
        return summary

def main():
    """主程式"""
    print("開始獲取中央氣象署自動氣象站資料...")
    
    try:
        # 初始化 API 客戶端
        cwa_api = CWAWeatherAPI()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = cwa_api.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析...")
            
            # 解析氣溫資料
            stations_data = cwa_api.parse_temperature_data(raw_data)
            
            if stations_data:
                print(f"成功解析 {len(stations_data)} 個測站資料")
                
                # 顯示統計摘要
                summary = cwa_api.get_temperature_summary(stations_data)
                if summary:
                    print("\n=== 氣溫統計摘要 ===")
                    print(f"總測站數: {summary['total_stations']}")
                    print(f"有效氣溫讀數: {summary['valid_temperature_readings']}")
                    print(f"最高溫: {summary['max_temp']:.1f}°C ({summary['max_temp_station']})")
                    print(f"最低溫: {summary['min_temp']:.1f}°C ({summary['min_temp_station']})")
                    print(f"平均溫度: {summary['avg_temp']:.1f}°C")
                
                # 儲存資料
                csv_file = cwa_api.save_to_csv(stations_data)
                
                # 顯示前5筆資料範例
                print("\n=== 前5筆測站資料 ===")
                for i, station in enumerate(stations_data[:5]):
                    print(f"{i+1}. {station['station_name']} ({station['location']})")
                    print(f"   溫度: {station['temperature']}°C, 濕度: {station['humidity']}%")
                    print(f"   天氣: {station['weather']}")
                    print(f"   風速: {station['wind_speed']} m/s, 風向: {station['wind_direction']}°")
                    print(f"   氣壓: {station['air_pressure']} hPa")
                    print(f"   座標: ({station['latitude']}, {station['longitude']})")
                    print(f"   觀測時間: {station['observation_time']}")
                    print()
                
            else:
                print("解析資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
