#!/usr/bin/env python3
"""
验证 OpenClaw 是否能与后端 API 交互的脚本
"""

import requests
import json
import sys

def check_backend_api():
    """检查后端 API 是否可访问"""
    print("=== 1. 检查后端 API ===")

    try:
        response = requests.get("http://172.21.64.1:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ 后端 API 健康检查通过")
            print(f"   响应: {response.json()}")
            return True
        else:
            print(f"❌ 后端 API 健康检查失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接后端 API: {e}")
        return False

def check_system_status():
    """检查系统状态 API"""
    print("\n=== 2. 检查系统状态 API ===")

    try:
        response = requests.get("http://172.21.64.1:8000/api/realtime/total", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ 系统状态 API 可访问")
            print(f"   总 Block 数: {data.get('total_blocks', 'N/A')}")
            return True
        else:
            print(f"❌ 系统状态 API 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接系统状态 API: {e}")
        return False

def check_anomalies_api():
    """检查异常查询 API"""
    print("\n=== 3. 检查异常查询 API ===")

    try:
        response = requests.get("http://172.21.64.1:8000/api/anomalies/query?hours=1&limit=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✅ 异常查询 API 可访问")
            print(f"   异常数量: {data.get('anomaly_count', 'N/A')}")
            return True
        else:
            print(f"❌ 异常查询 API 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接异常查询 API: {e}")
        return False

def main():
    """主函数"""
    print("OpenClaw 与后端 API 交互验证脚本")
    print("=" * 50)

    # 检查后端 API
    backend_ok = check_backend_api()

    # 检查系统状态 API
    system_ok = check_system_status()

    # 检查异常查询 API
    anomalies_ok = check_anomalies_api()

    # 总结
    print("\n" + "=" * 50)
    print("验证总结:")
    print(f"  后端 API: {'✅ 正常' if backend_ok else '❌ 异常'}")
    print(f"  系统状态 API: {'✅ 正常' if system_ok else '❌ 异常'}")
    print(f"  异常查询 API: {'✅ 正常' if anomalies_ok else '❌ 异常'}")

    if all([backend_ok, system_ok, anomalies_ok]):
        print("\n🎉 所有 API 检查通过！后端服务正常运行。")
        print("\n下一步:")
        print("  1. 确保 OpenClaw 配置中的工具 API 端点正确")
        print("  2. 重启 OpenClaw Gateway")
        print("  3. 在微信中发送: '查询健康度'")
    else:
        print("\n⚠️  部分 API 检查失败，请检查后端服务是否正常运行。")

    return all([backend_ok, system_ok, anomalies_ok])

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)