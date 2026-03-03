#!/usr/bin/env python3
"""
使用 pyproj 正確轉換 TWD67 坐標為 WGS84
並與 API 提供的 WGS84 數值比對
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

class CoordinateTransformer:
    def __init__(self):
        self.api_key = os.getenv('CWA_API_KEY')
        self.base_url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore"
        self.dataset_id = "O-A0003-001"
        
        # 創建 TWD67 到 WGS84 的轉換器
        # TWD67 使用正確的參數定義
        self.twd67_crs = CRS.from_proj4(
            "+proj=tmerc +lat_0=0 +lon_0=121 +k=0.9999 +x_0=250000 +y_0=0 "
            "+ellps=aust_SA +towgs84=-752,-358,-179,-5,-7,212,0 +units=m +no_defs"
        )
        self.twd67_precise = Transformer.from_crs(self.twd67_crs, "EPSG:4326", always_xy=True)
        
        # 備用方案：使用 TWD97 作為 TWD67 的近似（因為 API 中的 TWD67 可能已經是度數格式）
        self.twd67_to_wgs84 = Transformer.from_crs(
            "EPSG:3824",  # TWD97
            "EPSG:4326",  # WGS84
            always_xy=True
        )
        
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
    
    def parse_and_transform_coordinates(self, data):
        """解析坐標資料並進行轉換"""
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
                        # 使用 pyproj 轉換 TWD67 到 WGS84
                        try:
                            # 方法1: 使用 TWD67 近似轉換
                            transformed_lon1, transformed_lat1 = self.twd67_to_wgs84.transform(
                                coord_twd67['longitude'], coord_twd67['latitude']
                            )
                            
                            # 方法2: 使用精確 TWD67 參數轉換
                            transformed_lon2, transformed_lat2 = self.twd67_precise.transform(
                                coord_twd67['longitude'], coord_twd67['latitude']
                            )
                            
                            # 計算距離
                            distance_original = self.haversine_distance(
                                coord_twd67['latitude'], coord_twd67['longitude'],
                                coord_wgs84_api['latitude'], coord_wgs84_api['longitude']
                            )
                            
                            distance_method1 = self.haversine_distance(
                                transformed_lat1, transformed_lon1,
                                coord_wgs84_api['latitude'], coord_wgs84_api['longitude']
                            )
                            
                            distance_method2 = self.haversine_distance(
                                transformed_lat2, transformed_lon2,
                                coord_wgs84_api['latitude'], coord_wgs84_api['longitude']
                            )
                            
                            station_info = {
                                'station_id': record['StationId'],
                                'station_name': record['StationName'],
                                'location': record['GeoInfo']['CountyName'] + record['GeoInfo']['TownName'],
                                'twd67_lat': coord_twd67['latitude'],
                                'twd67_lon': coord_twd67['longitude'],
                                'wgs84_api_lat': coord_wgs84_api['latitude'],
                                'wgs84_api_lon': coord_wgs84_api['longitude'],
                                'wgs84_transformed_lat1': transformed_lat1,
                                'wgs84_transformed_lon1': transformed_lon1,
                                'wgs84_transformed_lat2': transformed_lat2,
                                'wgs84_transformed_lon2': transformed_lon2,
                                'distance_original_km': distance_original,
                                'distance_method1_km': distance_method1,
                                'distance_method2_km': distance_method2,
                                'temperature': float(record['WeatherElement']['AirTemperature']) if record['WeatherElement']['AirTemperature'] else None
                            }
                            stations.append(station_info)
                            
                        except Exception as e:
                            print(f"坐標轉換錯誤 {record.get('StationId', 'Unknown')}: {e}")
                            continue
                        
            except (KeyError, ValueError, TypeError) as e:
                print(f"解析站點資料時發生錯誤 {record.get('StationId', 'Unknown')}: {e}")
                continue
        
        return stations
    
    def analyze_transformation_results(self, stations_data):
        """分析轉換結果"""
        if not stations_data:
            return None
        
        # 提取距離數據
        original_distances = [s['distance_original_km'] for s in stations_data]
        method1_distances = [s['distance_method1_km'] for s in stations_data]
        method2_distances = [s['distance_method2_km'] for s in stations_data]
        
        statistics = {
            'total_stations': len(stations_data),
            'original': {
                'mean': np.mean(original_distances),
                'median': np.median(original_distances),
                'min': np.min(original_distances),
                'max': np.max(original_distances),
                'std': np.std(original_distances)
            },
            'method1_twd97_approx': {
                'mean': np.mean(method1_distances),
                'median': np.median(method1_distances),
                'min': np.min(method1_distances),
                'max': np.max(method1_distances),
                'std': np.std(method1_distances)
            },
            'method2_twd67_precise': {
                'mean': np.mean(method2_distances),
                'median': np.median(method2_distances),
                'min': np.min(method2_distances),
                'max': np.max(method2_distances),
                'std': np.std(method2_distances)
            }
        }
        
        return statistics
    
    def create_comparison_plots(self, stations_data, statistics):
        """創建比較圖表"""
        if not stations_data:
            return
        
        # 設置中文字體
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft JhengHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        
        # 圖1: 原始距離 vs 轉換後距離比較
        original_distances = [s['distance_original_km'] for s in stations_data]
        method1_distances = [s['distance_method1_km'] for s in stations_data]
        method2_distances = [s['distance_method2_km'] for s in stations_data]
        
        axes[0, 0].hist(original_distances, bins=30, alpha=0.7, label='原始 TWD67 vs API WGS84', color='red')
        axes[0, 0].hist(method1_distances, bins=30, alpha=0.7, label='TWD97轉換 vs API WGS84', color='blue')
        axes[0, 0].hist(method2_distances, bins=30, alpha=0.7, label='TWD67精確轉換 vs API WGS84', color='green')
        axes[0, 0].set_xlabel('距離 (km)')
        axes[0, 0].set_ylabel('頻率')
        axes[0, 0].set_title('坐標轉換距離比較')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # 圖2: 散點圖比較
        axes[0, 1].scatter(original_distances, method1_distances, alpha=0.6, label='TWD97轉換', color='blue')
        axes[0, 1].scatter(original_distances, method2_distances, alpha=0.6, label='TWD67精確轉換', color='green')
        axes[0, 1].plot([0, max(original_distances)], [0, max(original_distances)], 'r--', alpha=0.8, label='完全相等線')
        axes[0, 1].set_xlabel('原始距離 (km)')
        axes[0, 1].set_ylabel('轉換後距離 (km)')
        axes[0, 1].set_title('轉換效果比較')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # 圖3: 柱狀圖顯示平均距離改善
        methods = ['原始', 'TWD97轉換', 'TWD67精確轉換']
        means = [statistics['original']['mean'], statistics['method1_twd97_approx']['mean'], statistics['method2_twd67_precise']['mean']]
        colors = ['red', 'blue', 'green']
        
        bars = axes[1, 0].bar(methods, means, color=colors, alpha=0.7)
        axes[1, 0].set_ylabel('平均距離 (km)')
        axes[1, 0].set_title('平均距離比較')
        axes[1, 0].grid(True, alpha=0.3)
        
        # 在柱狀圖上添加數值
        for bar, mean in zip(bars, means):
            height = bar.get_height()
            axes[1, 0].text(bar.get_x() + bar.get_width()/2., height + 0.001,
                           f'{mean:.6f}', ha='center', va='bottom')
        
        # 圖4: 坐標分布圖（使用 WGS84 API 坐標）
        wgs84_lats = [s['wgs84_api_lat'] for s in stations_data]
        wgs84_lons = [s['wgs84_api_lon'] for s in stations_data]
        temperatures = [s['temperature'] for s in stations_data if s['temperature'] is not None]
        
        if temperatures:
            scatter = axes[1, 1].scatter(wgs84_lons[:len(temperatures)], wgs84_lats[:len(temperatures)], 
                                      c=temperatures, cmap='coolwarm', s=50, alpha=0.7)
            axes[1, 1].set_xlabel('經度 (Longitude)')
            axes[1, 1].set_ylabel('緯度 (Latitude)')
            axes[1, 1].set_title('氣象站溫度分布 (WGS84坐標)')
            plt.colorbar(scatter, ax=axes[1, 1], label='溫度 (°C)')
            axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        # 確保 outputs 目錄存在
        os.makedirs('outputs', exist_ok=True)
        plt.savefig('outputs/coordinate_transformation_comparison.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("坐標轉換比較圖已儲存至: outputs/coordinate_transformation_comparison.png")
    
    def save_transformation_results(self, stations_data, statistics):
        """儲存轉換結果"""
        if not stations_data:
            return
        
        # 儲存詳細資料
        df = pd.DataFrame(stations_data)
        df.to_csv('outputs/coordinate_transformation_results.csv', index=False, encoding='utf-8-sig')
        
        # 儲存統計摘要
        summary_data = []
        for method_name, stats in [('原始', statistics['original']), 
                                   ('TWD97轉換', statistics['method1_twd97_approx']), 
                                   ('TWD67精確轉換', statistics['method2_twd67_precise'])]:
            summary_data.append({
                '轉換方法': method_name,
                '平均距離(km)': f"{stats['mean']:.6f}",
                '中位數距離(km)': f"{stats['median']:.6f}",
                '最小距離(km)': f"{stats['min']:.6f}",
                '最大距離(km)': f"{stats['max']:.6f}",
                '標準差(km)': f"{stats['std']:.6f}"
            })
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_csv('outputs/transformation_statistics_summary.csv', index=False, encoding='utf-8-sig')
        
        print(f"\n=== 坐標轉換結果統計 ===")
        print(f"總測站數: {statistics['total_stations']}")
        print(f"\n原始 TWD67 vs API WGS84:")
        print(f"  平均距離: {statistics['original']['mean']:.6f} km")
        print(f"\nTWD97轉換 vs API WGS84:")
        print(f"  平均距離: {statistics['method1_twd97_approx']['mean']:.6f} km")
        print(f"  改善程度: {((statistics['original']['mean'] - statistics['method1_twd97_approx']['mean']) / statistics['original']['mean'] * 100):.2f}%")
        print(f"\nTWD67精確轉換 vs API WGS84:")
        print(f"  平均距離: {statistics['method2_twd67_precise']['mean']:.6f} km")
        print(f"  改善程度: {((statistics['original']['mean'] - statistics['method2_twd67_precise']['mean']) / statistics['original']['mean'] * 100):.2f}%")
        
        print(f"\n詳細資料已儲存至: outputs/coordinate_transformation_results.csv")
        print(f"統計摘要已儲存至: outputs/transformation_statistics_summary.csv")

def main():
    """主程式"""
    print("開始使用 pyproj 進行坐標轉換分析...")
    
    try:
        transformer = CoordinateTransformer()
        
        # 獲取資料
        print("正在從 CWA API 獲取資料...")
        raw_data = transformer.fetch_weather_data()
        
        if raw_data:
            print("成功獲取資料，正在解析和轉換坐標...")
            
            # 解析並轉換坐標
            stations_data = transformer.parse_and_transform_coordinates(raw_data)
            
            if stations_data:
                print(f"成功處理 {len(stations_data)} 個測站的坐標資料")
                
                # 分析轉換結果
                statistics = transformer.analyze_transformation_results(stations_data)
                
                if statistics:
                    # 儲存結果
                    transformer.save_transformation_results(stations_data, statistics)
                    
                    # 創建比較圖
                    print("\n正在生成坐標轉換比較圖...")
                    transformer.create_comparison_plots(stations_data, statistics)
                
            else:
                print("解析坐標資料失敗")
        else:
            print("獲取資料失敗")
            
    except Exception as e:
        print(f"程式執行發生錯誤: {e}")

if __name__ == "__main__":
    main()
