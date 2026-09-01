"""地理位置服务：随机虚拟定位、IP/坐标归属地查询"""
from __future__ import annotations

import random
from typing import Optional

import requests

from app.core.constants import CITY_COORDS


def get_random_location(log=lambda m, l="DEBUG": None) -> dict:
    """从全国城市坐标库中随机获取一个虚拟定位"""
    city = random.choice(CITY_COORDS)
    log(f"随机选择城市: {city['name']} (纬度={city['latitude']:.4f}, 经度={city['longitude']:.4f})")
    return {
        "latitude": city["latitude"],
        "longitude": city["longitude"],
        "accuracy": random.randint(50, 200),
        "city_name": city["name"],
    }


def get_city_name_from_ip(ip_address: str, log=lambda m, l="DEBUG": None) -> str:
    """根据IP地址获取城市名称（百度API）"""
    if not ip_address or ip_address == "未知":
        return "未知"
    try:
        api_url = f"https://opendata.baidu.com/api.php?query={ip_address}&co=&resource_id=6006&oe=utf8"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(api_url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "0" and data.get("data"):
                location = data["data"][0].get("location", "")
                if location:
                    log(f"从百度API获取到城市信息: {location}")
                    return location
    except Exception as e:
        log(f"通过IP地址查询城市信息失败: {str(e)}")
    return "未知"


def get_city_name_from_coordinates(latitude: float, longitude: float, amap_key: str,
                                   log=lambda m, l="DEBUG": None) -> str:
    """根据经纬度获取城市名称（高德逆地理编码）"""
    try:
        api_url = (
            f"https://restapi.amap.com/v3/geocode/regeo?key={amap_key}"
            f"&location={longitude},{latitude}&radius=1000&extensions=base"
        )
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(api_url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "1" and "regeocode" in data:
                addr = data["regeocode"].get("addressComponent", {})
                city = addr.get("city", "")
                district = addr.get("district", "")
                province = addr.get("province", "")
                if city:
                    return str(city).replace("市", "")
                if district and province:
                    return (
                        f"{province}{district}"
                        .replace("省", "").replace("市", "")
                        .replace("区", "").replace("县", "")
                    )
    except Exception as e:
        log(f"通过坐标查询城市信息失败: {str(e)}")
    return "未知"


def format_location(ip_address: str, log=lambda m, l="DEBUG": None) -> str:
    """根据IP地址获取城市名称（供备注使用）"""
    if not ip_address or ip_address == "未知":
        return "未知"
    return get_city_name_from_ip(ip_address, log) or "未知"
