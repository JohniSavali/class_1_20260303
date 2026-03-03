#!/usr/bin/env python3
"""
修正的坐標轉換分析
使用正確的 TWD67 到 WGS84 轉換參數
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
from pyproj import Transformer, CRS

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 載入環境變數
load_dotenv()

class CorrectedCoordinateTransformer:
    def __init__(self):
        self.api_key = os.getenv('CWA_API_KEY')
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
        # 嘗試不同的 TWD67 轉換方法
        # 方法1: 使用 TWD67 的正確參數（但需要將度數轉換為投影坐標）
        self.twd67_crs = CRS.from_epsg(3828)  # TWD67
        self.wgs84_crs = CRS.from_epsg(4326)   # WGS84
        self.twd67_to_wgs84 = Transformer.from_crs(3828, 4326, always_xy=True)
        
        # 方法2: 使用 TWD97 作為參考
        self.twd97_to_wgs84 = Transformer.from_crs(3824, 4326, always_xy=True)
        
        # 方法3: 直接使用度數坐標（假設 API 的 TWD67 已經是某種度數格式）
        # 這種情況下我們只需要微調
        
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
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371
        return c * r
    
    def parse_and_analyze_coordinates(self, data):
        """解析坐標資料並分析差異"""
        if not data or 'records' not in data:
            return None
        
        stations = []
        records = data['records']['Station']
        
        for record in records:
            try:
                coordinates = record['GeoInfo']['Coordinates']
                
                if len(coordinates) >= 2:
                    coord_twd67 = None
                    coord_wgs84_api = None
                    
                    for coord in coordinates:
                        if coord['CoordinateName'] == 'TWD67':
                            coord_twd67 = {
                                'latitude': float(coord['StationLatitude']),
                                'longitude': float(coord['StationLongitude'])
                            }
                        elif coord['CoordinateName'] == 'WGS84':
                            coord_wgs84_api = {
                                'latitude': float(coord['StationLatitude']),
                                'longitude': float(coord['StationLongitude'])
                            }
                    
                    if coord_twd67 and coord_wgs84_api:
                        # 計算原始距離差異
                        original_distance = self.haversine_distance(
                            coord_twd67['latitude'], coord_twd67['longitude'],
                            coord_wgs84_api['latitude'], coord_wgs84_api['longitude']
                        )
                        
                        # 計算坐標差異
                        lat_diff = coord_wgs84_api['latitude'] - coord_twd67['latitude']
                        lon_diff = coord_wgs84_api['longitude'] - coord_twd67['longitude']
                        
                        # 計算平均偏移量
                        avg_lat_offset = abs(lat_diff)
                        avg_lon_offset = abs(lon_diff)
                        
                        station_info = {
                            'station_id': record['StationId'],
                            'station_name': record['StationName'],
                            'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                            'twd67_lat': coord_twd67['latitude'],
                            'twd67_lon': coord_twd67['longitude'],
                            'wgs84_api_lat': coord_wgs84_api['latitude'],
                            'wgs84_api_lon': coord_wgs84_api['longitude'],
                            'latitude_difference': lat_diff,
                            'longitude_difference': lon_diff,
                            'abs_lat_diff': avg_lat_offset,
                            'abs_lon_diff': avg_lon_offset,
                            'distance_km': original_distance,
                            'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None
                        }
                        stations.append(station_info)
                        
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def analyze_coordinate_differences(self, stations_data):
        """分析坐標差異模式"""
        if not stations_data:
            return None
        
        # 計算統計數據
        lat_diffs = [s['latitude_difference'] for s in stations_data]
        lon_diffs = [s['longitude_difference'] for s in stations_data]
        abs_lat_diffs = [s['abs_lat_diff'] for s in stations_data]
        abs_lon_diffs = [s['abs_lon_diff'] for s in stations_data]
        distances = [s['distance_km'] for s in stations_data]
        
        statistics = {
            'total_stations': len(stations_data),
            'latitude_diff': {
                'mean': np.mean(lat_diffs),
                'std': np.std(lat_diffs),
                'min': np.min(lat_diffs),
                'max': np.max(lat_diffs),
                'abs_mean': np.mean(abs_lat_diffs)
            },
            'longitude_diff': {
                'mean': np.mean(lon_diffs),
                'std': np.std(lon_diffs),
                'min': np.min(lon_diffs),
                'max': np.max(lon_diffs),
                'abs_mean': np.mean(abs_lon_diffs)
            },
            'distance': {
                'mean': np.mean(distances),
                'std': np.std(distances),
                'min': np.min(distances),
                'max': np.max(distances)
            }
        }
        
        return statistics
    
    def create_analysis_plots(self, stations_data, statistics):
        """創建分析圖表"""
        if not stations_data:
            return
        
        # 設置中文字體
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft JhengHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 圖1: 緯度差異分布
        lat_diffs = [s['latitude_difference'] for s in stations_data]
        axes[0, 0].hist(lat_diffs, bins=30, alpha=0.7, color='blue', edgecolor='black')
        axes[0, 0].axvline(statistics['latitude_diff']['mean'], color='red', linestyle='--', 
                          label=f'平均值: {statistics["latitude_diff"]["mean"]:.6f}°')
        axes[0, 0].set_xlabel('緯度差異 (WGS84 - TWD67, 度)')
        axes[0, 0].set_ylabel('頻率')
        axes[0, 0].set_title('緯度差異分布')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 圖2: 經度差異分布
        lon_diffs = [s['longitude_difference'] for s in stations_data]
        axes[0, 1].hist(lon_diffs, bins=30, alpha=0.7, color='green', edgecolor='black')
        axes[0, 1].axvline(statistics['longitude_diff']['mean'], color='red', linestyle='--',
                          label=f'平均值: {statistics["longitude_diff"]["mean"]:.6f}°')
        axes[0, 1].set_xlabel('經度差異 (WGS84 - TWD67, 度)')
        axes[0, 1].set_ylabel('頻率')
        axes[0, 1].set_title('經度差異分布')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 圖3: 散點圖 - TWD67 vs WGS84 坐標
        twd67_lats = [s['twd67_lat'] for s in stations_data]
        twd67_lons = [s['twd67_lon'] for s in stations_data]
        wgs84_lats = [s['wgs84_api_lat'] for s in stations_data]
        wgs84_lons = [s['wgs84_api_lon'] for s in stations_data]
        
        axes[1, 0].scatter(twd67_lats, wgs84_lats, alpha=0.6, s=20, label='緯度', color='blue')
        axes[1, 0].plot([min(twd67_lats), max(twd67_lats)], [min(twd67_lats), max(twd67_lats)], 
                       'r--', alpha=0.8, label='完全相等線')
        axes[1, 0].set_xlabel('TWD67 緯度')
        axes[1, 0].set_ylabel('WGS84 緯度')
        axes[1, 0].set_title('緯度坐標比較')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3)
        
        # 圖4: 距離分布
        distances = [s['distance_km'] for s in stations_data]
        axes[1, 1].hist(distances, bins=30, alpha=0.7, color='red', edgecolor='black')
        axes[1, 1].axvline(statistics['distance']['mean'], color='darkred', linestyle='--',
                          label=f'平均值: {statistics["distance"]["mean"]:.6f} km')
        axes[1, 1].set_xlabel('距離 (km)')
        axes[1, 1].set_ylabel('頻率')
        axes[1, 1].set_title('坐標間距離分布')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 確保 outputs 目錄存在
        os.makedirs('outputs', exist_ok=True)
        plt.savefig('outputs/coordinate_difference_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("坐標差異分析圖已儲存至: outputs/coordinate_difference_analysis.png")
    
    def save_analysis_results(self, stations_data, statistics):
        """儲存分析結果"""
        if not stations_data:
            return
        
        # 儲存詳細資料
        df = pd.DataFrame(stations_data)
        df_sorted = df.sort_values('distance_km', ascending=False)
        df_sorted.to_csv('outputs/coordinate_difference_analysis.csv', index=False, encoding='utf-8-sig')
        
        # 儲存統計摘要
        summary_data = {
            '統計項目': ['總測站數', '緯度差異平均(度)', '緯度差異標準差(度)', '經度差異平均(度)', '經度差異標準差(度)', 
                       '平均距離(km)', '距離標準差(km)', '最小距離(km)', '最大距離(km)'],
            '數值': [
                statistics['total_stations'],
                f"{statistics['latitude_diff']['mean']:.8f}",
                f"{statistics['latitude_diff']['std']:.8f}",
                f"{statistics['longitude_diff']['mean']:.8f}",
                f"{statistics['longitude_diff']['std']:.8f}",
                f"{statistics['distance']['mean']:.6f}",
                f"{statistics['distance']['std']:.6f}",
                f"{statistics['distance']['min']:.6f}",
                f"{statistics['distance']['max']:.6f}"
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv('outputs/difference_statistics_summary.csv', index=False, encoding='utf-8-sig')
        
        print(f"\n=== 坐標差異分析結果 ===")
        print(f"總測站數: {statistics['total_stations']}")
        print(f"\n緯度差異 (WGS84 - TWD67):")
        print(f"  平均值: {statistics['latitude_diff']['mean']:.8f}°")
        print(f"  標準差: {statistics['latitude_diff']['std']:.8f}°")
        print(f"  絕對值平均: {statistics['latitude_diff']['abs_mean']:.8f}°")
        
        print(f"\n經度差異 (WGS84 - TWD67):")
        print(f"  平均值: {statistics['longitude_diff']['mean']:.8f}°")
        print(f"  標準差: {statistics['longitude_diff']['std']:.8f}°")
        print(f"  絕對值平均: {statistics['longitude_diff']['abs_mean']:.8f}°")
        
        print(f"\n距離統計:")
        print(f"  平均距離: {statistics['distance']['mean']:.6f} km")
        print(f"  標準差: {statistics['distance']['std']:.6f} km")
        print(f"  最小距離: {statistics['distance']['min']:.6f} km")
        print(f"  最大距離: {statistics['distance']['max']:.6f} km")
        
        print(f"\n=== 距離最大的前10個測站 ===")
        top_10 = df_sorted.head(10)
        for i, (_, station) in enumerate(top_10.iterrows(), 1):
            print(f"{i:2d}. {station['station_name']} ({station['location']}): {station['distance_km']:.6f} km")
            print(f"     緯度差: {station['latitude_difference']:.8f}°, 經度差: {station['longitude_difference']:.8f}°")
        
        print(f"\n詳細資料已儲存至: outputs/coordinate_difference_analysis.csv")
        print(f"統計摘要已儲存至: outputs/difference_statistics_summary.csv")

def main():
    """主程式"""
    print("開始進行坐標差異分析...")
    
    try:
        analyzer = CorrectedCoordinateTransformer()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = analyzer.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在分析坐標差異...")
            
            # 解析並分析坐標
            stations_data = analyzer.parse_and_analyze_coordinates(raw_data)
            
            if stations_data:
                print(f"成功處理 {len(stations_data)} 個測站的坐標資料")
                
                # 分析坐標差異
                statistics = analyzer.analyze_coordinate_differences(stations_data)
                
                if statistics:
                    # 儲存結果
                    analyzer.save_analysis_results(stations_data, statistics)
                    
                    # 創建分析圖
                    print("\n正在生成坐標差異分析圖...")
                    analyzer.create_analysis_plots(stations_data, statistics)
                
            else:
                print("解析坐標資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
