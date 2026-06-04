#!/usr/bin/env python3
"""
测试 OpenClaw 工具调用的脚本

这个脚本会模拟 OpenClaw 调用工具的过程，验证是否能正确访问后端 API
"""

import requests
import json
import time

def test_tool_call():
    """测试工具调用"""
    print("=== 测试 OpenClaw 工具调用 ===")

    # 测试 1: 检查后端 API 是否可访问
    print("\n1. 检查后端 API 可访问性...")
    try:
        response = requests.get("http://172.21.64.1:8000/api/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ 后端 API 可访问")
            print(f"   响应: {response.json()}")
        else:
            print(f"   ❌ 后端 API 不可访问: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 无法连接后端 API: {e}")
        return False

    # 测试 2: 检查系统状态 API
    print("\n2. 检查系统状态 API...")
    try:
        response = requests.get("http://172.21.64.1:8000/api/realtime/total", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 系统状态 API 可访问")
            print(f"   总 Block 数: {data.get('total_blocks', 'N/A')}")
        else:
            print(f"   ❌ 系统状态 API 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 无法连接系统状态 API: {e}")
        return False

    # 测试 3: 检查异常查询 API
    print("\n3. 检查异常查询 API...")
    try:
        response = requests.get("http://172.21.64.1:8000/api/anomalies/query?hours=1&limit=5", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 异常查询 API 可访问")
            print(f"   异常数量: {data.get('anomaly_count', 'N/A')}")
        else:
            print(f"   ❌ 异常查询 API 失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 无法连接异常查询 API: {e}")
        return False

    return True

def main():
    """主函数"""
    print("OpenClaw 工具调用测试脚本")
    print("=" * 50)

    success = test_tool_call()

    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试通过！OpenClaw 应该能正确调用后端 API。")
        print("\n现在可以尝试:")
        print("  1. 在微信中发送: '查询健康度'")
        print("  2. 或者在终端运行: openclaw agent --message '查询健康度'")
    else:
        print("⚠️  测试失败，请检查后端服务是否正常运行。")

    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)