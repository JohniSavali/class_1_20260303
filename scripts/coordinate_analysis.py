#!/usr/bin/env python3
"""
分析氣象站不同坐標系統的差異
比較 TWD67 和 WGS84 坐標的差距
"""

import os
import requests
import json
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from dotenv import load_dotenv
import urllib3
from math import radians, cos, sin, asin, sqrt

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 載入環境變數
load_dotenv()

class CoordinateAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('CWA_API_KEY')
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
        if not self.api_key:
            raise ValueError("CWA_API_KEY not found in environment variables")
    
    def fetch_weather_data(self):
        """獲取氣象站資料"""
        url = f"{self.base_url}/{self.dataset_id}"
        params = {
            'Authorization': self.api_key,
            'format': 'JSON'
        }
        
        try:
            response = requests.get(url, params=params, verify=False)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 請求失敗: {e}")
            return None
    
    def haversine_distance(self, lat1, lon1, lat2, lon2):
        """計算兩點間的距離（公里）"""
        # 將十進制度數轉為弧度
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        
        # haversine 公式
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        # 地球半徑（公里）
        r = 6371
        return c * r
    
    def parse_coordinate_data(self, data):
        """解析坐標資料"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        for record in records:
            try:
                coordinates = record['GeoInfo']['Coordinates']
                
                # 確保有兩個坐標系統
                if len(coordinates) >= 2:
                    coord_twd67 = None
                    coord_wgs84 = None
                    
                    for coord in coordinates:
                        if coord['CoordinateName'] == 'TWD67':
                            coord_twd67 = {
                                'latitude': float(coord['StationLatitude']),
                                'longitude': float(coord['StationLongitude'])
                            }
                        elif coord['CoordinateName'] == 'WGS84':
                            coord_wgs84 = {
                                'latitude': float(coord['StationLatitude']),
                                'longitude': float(coord['StationLongitude'])
                            }
                    
                    if coord_twd67 and coord_wgs84:
                        # 計算距離（將 TWD67 當作 WGS84 計算）
                        distance = self.haversine_distance(
                            coord_twd67['latitude'], coord_twd67['longitude'],
                            coord_wgs84['latitude'], coord_wgs84['longitude']
                        )
                        
                        station_info = {
                            'station_id': record['StationId'],
                            'station_name': record['StationName'],
                            'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                            'twd67_lat': coord_twd67['latitude'],
                            'twd67_lon': coord_twd67['longitude'],
                            'wgs84_lat': coord_wgs84['latitude'],
                            'wgs84_lon': coord_wgs84['longitude'],
                            'distance_km': distance,
                            'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None
                        }
                        stations.append(station_info)
                        
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def create_comparison_plot(self, stations_data):
        """創建坐標比較圖"""
        if not stations_data:
            print("沒有資料可繪圖")
            return
        
        # 設置中文字體
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft JhengHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 8))
        
        # 提取坐標資料
        twd67_lats = [s['twd67_lat'] for s in stations_data]
        twd67_lons = [s['twd67_lon'] for s in stations_data]
        wgs84_lats = [s['wgs84_lat'] for s in stations_data]
        wgs84_lons = [s['wgs84_lon'] for s in stations_data]
        temperatures = [s['temperature'] for s in stations_data if s['temperature'] is not None]
        
        # 左圖：兩個坐標系統的重疊圖
        scatter1 = ax1.scatter(twd67_lons, twd67_lats, c='red', alpha=0.6, s=30, label='TWD67 (當作WGS84)')
        scatter2 = ax1.scatter(wgs84_lons, wgs84_lats, c='blue', alpha=0.6, s=30, label='WGS84')
        
        ax1.set_xlabel('經度 (Longitude)')
        ax1.set_ylabel('緯度 (Latitude)')
        ax1.set_title('氣象站坐標比較 - TWD67 vs WGS84')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 右圖：溫度分布圖（使用 WGS84 坐標）
        if temperatures:
            scatter3 = ax2.scatter(wgs84_lons[:len(temperatures)], wgs84_lats[:len(temperatures)], 
                                 c=temperatures, cmap='coolwarm', s=50, alpha=0.7)
            ax2.set_xlabel('經度 (Longitude)')
            ax2.set_ylabel('緯度 (Latitude)')
            ax2.set_title('氣象站溫度分布 (WGS84坐標)')
            plt.colorbar(scatter3, ax=ax2, label='溫度 (°C)')
            ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 確保 outputs 目錄存在
        os.makedirs('outputs', exist_ok=True)
        plt.savefig('outputs/coordinate_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("坐標比較圖已儲存至: outputs/coordinate_comparison.png")
    
    def analyze_distances(self, stations_data):
        """分析距離統計"""
        if not stations_data:
            return None
        
        distances = [s['distance_km'] for s in stations_data]
        
        statistics = {
            'total_stations': len(stations_data),
            'mean_distance': np.mean(distances),
            'median_distance': np.median(distances),
            'min_distance': np.min(distances),
            'max_distance': np.max(distances),
            'std_distance': np.std(distances)
        }
        
        return statistics, distances
    
    def save_distance_analysis(self, stations_data, statistics, distances):
        """儲存距離分析結果"""
        if not stations_data:
            return
        
        # 儲存詳細資料
        df = pd.DataFrame(stations_data)
        df_sorted = df.sort_values('distance_km', ascending=False)
        df_sorted.to_csv('outputs/coordinate_distance_analysis.csv', index=False, encoding='utf-8-sig')
        
        # 儲存統計摘要
        summary_data = {
            '統計項目': ['總測站數', '平均距離(km)', '中位數距離(km)', '最小距離(km)', '最大距離(km)', '標準差(km)'],
            '數值': [
                statistics['total_stations'],
                f"{statistics['mean_distance']:.6f}",
                f"{statistics['median_distance']:.6f}",
                f"{statistics['min_distance']:.6f}",
                f"{statistics['max_distance']:.6f}",
                f"{statistics['std_distance']:.6f}"
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv('outputs/distance_statistics_summary.csv', index=False, encoding='utf-8-sig')
        
        print(f"\n=== 距離統計摘要 ===")
        print(f"總測站數: {statistics['total_stations']}")
        print(f"平均距離: {statistics['mean_distance']:.6f} km")
        print(f"中位數距離: {statistics['median_distance']:.6f} km")
        print(f"最小距離: {statistics['min_distance']:.6f} km")
        print(f"最大距離: {statistics['max_distance']:.6f} km")
        print(f"標準差: {statistics['std_distance']:.6f} km")
        
        print(f"\n=== 距離最大的前10個測站 ===")
        top_10 = df_sorted.head(10)
        for i, (_, station) in enumerate(top_10.iterrows(), 1):
            print(f"{i:2d}. {station['station_name']} ({station['location']}): {station['distance_km']:.6f} km")
        
        print(f"\n詳細資料已儲存至: outputs/coordinate_distance_analysis.csv")
        print(f"統計摘要已儲存至: outputs/distance_statistics_summary.csv")

def main():
    """主程式"""
    print("開始分析氣象站坐標系統差異...")
    
    try:
        analyzer = CoordinateAnalyzer()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = analyzer.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析坐標...")
            
            # 解析坐標資料
            stations_data = analyzer.parse_coordinate_data(raw_data)
            
            if stations_data:
                print(f"成功解析 {len(stations_data)} 個測站的坐標資料")
                
                # 分析距離
                statistics, distances = analyzer.analyze_distances(stations_data)
                
                if statistics:
                    # 儲存分析結果
                    analyzer.save_distance_analysis(stations_data, statistics, distances)
                
                # 創建比較圖
                print("\n正在生成坐標比較圖...")
                analyzer.create_comparison_plot(stations_data)
                
            else:
                print("解析坐標資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
