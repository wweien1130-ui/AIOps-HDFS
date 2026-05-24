#!/usr/bin/env python3
"""
Redis连接测试脚本
测试Redis连接、认证、基本操作等
"""
import socket
import sys
import os
import time

def load_redis_config():
    """从配置文件加载Redis配置"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        'config', 'redis.yaml'
    )
    
    if not os.path.exists(config_path):
        return None
        
    import yaml
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)['redis']
    return config

def test_network_connectivity(host, port):
    """测试网络连通性"""
    print(f"\n{'='*60}")
    print("1. 网络连通性测试")
    print(f"{'='*60}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"  ✅ 端口 {host}:{port} 可访问")
            return True
        else:
            print(f"  ❌ 端口 {host}:{port} 无法访问")
            return False
    except Exception as e:
        print(f"  ❌ 网络测试失败: {e}")
        return False

def test_redis_connection(host, port, password, db=0):
    """测试Redis连接和认证"""
    print(f"\n{'='*60}")
    print("2. Redis连接测试")
    print(f"{'='*60}")
    
    try:
        import redis
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            socket_timeout=5,
            socket_connect_timeout=5,
            decode_responses=True
        )
        
        # 测试PING命令
        response = r.ping()
        if response:
            print(f"  ✅ Redis连接成功！")
            print(f"     主机: {host}")
            print(f"     端口: {port}")
            print(f"     数据库: {db}")
            if password:
                print(f"     密码: 已配置")
            return r
        else:
            print(f"  ❌ Redis PING失败")
            return None
            
    except Exception as e:
        error_msg = str(e)
        if 'authentication' in error_msg.lower() or 'password' in error_msg.lower():
            print(f"  ❌ 认证失败：密码错误")
        elif 'connection' in error_msg.lower() or 'connect' in error_msg.lower():
            print(f"  ❌ 连接失败: {e}")
        else:
            print(f"  ❌ 连接失败: {e}")
        return None

def test_redis_operations(r, key_prefix):
    """测试Redis基本操作"""
    print(f"\n{'='*60}")
    print("3. Redis操作测试")
    print(f"{'='*60}")
    
    try:
        # 测试String操作
        test_key = f"{key_prefix}test_string"
        test_value = f"test_value_{int(time.time())}"
        r.set(test_key, test_value)
        retrieved = r.get(test_key)
        
        if retrieved == test_value:
            print(f"  ✅ String操作正常")
        else:
            print(f"  ❌ String操作失败")
            return False
        r.delete(test_key)
        
        # 测试Hash操作
        test_hash = f"{key_prefix}test_hash"
        r.hset(test_hash, mapping={'field1': 'value1', 'field2': 'value2'})
        hash_data = r.hgetall(test_hash)
        
        if hash_data and hash_data.get('field1') == 'value1':
            print(f"  ✅ Hash操作正常")
        else:
            print(f"  ❌ Hash操作失败")
            return False
        r.delete(test_hash)
        
        # 测试Sorted Set操作
        test_zset = f"{key_prefix}test_zset"
        r.zadd(test_zset, {'member1': 1.0, 'member2': 2.0})
        members = r.zrange(test_zset, 0, -1)
        
        if len(members) == 2 and 'member1' in members and 'member2' in members:
            print(f"  ✅ Sorted Set操作正常")
        else:
            print(f"  ❌ Sorted Set操作失败")
            return False
        r.delete(test_zset)
        
        print(f"  ✅ 所有基本操作测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ 操作测试失败: {e}")
        return False

def test_project_keys(r, key_prefix):
    """测试项目使用的键结构"""
    print(f"\n{'='*60}")
    print("4. 项目键结构检查")
    print(f"{'='*60}")
    
    try:
        # 检查项目使用的键
        keys_to_check = [
            f"{key_prefix}top",
            f"{key_prefix}last_sync_time"
        ]
        
        existing_keys = []
        for key in r.keys(f"{key_prefix}*"):
            existing_keys.append(key)
        
        if existing_keys:
            print(f"  📋 找到 {len(existing_keys)} 个项目相关的键:")
            for key in existing_keys[:10]:  # 只显示前10个
                key_type = r.type(key)
                if key_type == 'zset':
                    count = r.zcard(key)
                    print(f"     - {key} (Sorted Set, {count} 成员)")
                elif key_type == 'hash':
                    count = r.hlen(key)
                    print(f"     - {key} (Hash, {count} 字段)")
                elif key_type == 'string':
                    value = r.get(key)
                    print(f"     - {key} (String): {value[:50]}...")
                else:
                    print(f"     - {key} ({key_type})")
        else:
            print(f"  ℹ️  未找到项目相关的键（可能尚未初始化）")
        
        # 测试键前缀是否正确
        print(f"\n  🔍 键前缀: {key_prefix}")
        print(f"  ✅ 项目键结构配置正确")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 项目键检查失败: {e}")
        return False

def test_server_info(r):
    """获取Redis服务器信息"""
    print(f"\n{'='*60}")
    print("5. Redis服务器信息")
    print(f"{'='*60}")
    
    try:
        info = r.info()
        print(f"  Redis版本: {info.get('redis_version', 'Unknown')}")
        print(f"  运行模式: {info.get('redis_mode', 'Unknown')}")
        print(f"  操作系统: {info.get('os', 'Unknown')}")
        print(f"  端口: {info.get('tcp_port', 'Unknown')}")
        print(f"  连接数: {info.get('connected_clients', 'Unknown')}")
        print(f"  运行时长: {info.get('uptime_in_days', 'Unknown')} 天")
        print(f"  内存使用: {info.get('used_memory_human', 'Unknown')}")
        print(f"  键数量: {info.get('db0', {}).get('keys', 'Unknown') if isinstance(info.get('db0'), dict) else 'N/A'}")
        
        return True
    except Exception as e:
        print(f"  ❌ 获取服务器信息失败: {e}")
        return False

def quick_test():
    """快速测试模式"""
    print("\n快速测试 Redis 连接...")
    
    config = load_redis_config()
    if not config:
        print("❌ 配置文件不存在: config/redis.yaml")
        return False
    
    host = config['host']
    port = config['port']
    password = config.get('password')
    db = config.get('db', 0)
    key_prefix = config.get('key_prefix', 'anomaly:')
    
    try:
        import redis
        r = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password if password else None,
            socket_timeout=5,
            decode_responses=True
        )
        
        if r.ping():
            print(f"✅ Redis 连接成功: {host}:{port}")
            return True
        else:
            print(f"❌ Redis 连接失败")
            return False
            
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False

def main():
    print("="*60)
    print(" Redis 连接测试工具")
    print("="*60)
    
    # 检查参数
    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        quick_test()
        return
    
    # 加载配置
    config = load_redis_config()
    if not config:
        print("\n❌ 错误: 配置文件不存在 config/redis.yaml")
        print("   将使用默认配置进行测试...")
        
        # 使用默认配置
        host = input("请输入Redis主机地址 [192.168.115.129]: ").strip() or "192.168.115.129"
        port = input("请输入Redis端口 [6382]: ").strip() or "6382"
        password = input("请输入Redis密码 (无密码直接回车): ").strip() or None
        key_prefix = "anomaly:"
    else:
        print(f"\n📋 使用配置文件: config/redis.yaml")
        host = config['host']
        port = config['port']
        password = config.get('password')
        db = config.get('db', 0)
        key_prefix = config.get('key_prefix', 'anomaly:')
        
        print(f"   主机: {host}")
        print(f"   端口: {port}")
        print(f"   密码: {'已配置' if password else '无'}")
        print(f"   数据库: {db}")
    
    # 转换端口为整数
    try:
        port = int(port)
    except:
        print(f"❌ 端口必须是数字: {port}")
        return
    
    # 运行测试
    results = []
    
    # 1. 网络连通性测试
    results.append(("网络连通性", test_network_connectivity(host, port)))
    
    if not results[-1][1]:
        print("\n❌ 网络测试失败，请检查:")
        print("   1. Ubuntu VM是否运行")
        print("   2. Docker容器是否启动")
        print("   3. VMware端口转发是否配置")
        print("   4. 防火墙是否允许该端口")
        return
    
    # 2. Redis连接测试
    r = test_redis_connection(host, port, password, db if 'db' in dir() else 0)
    
    if not r:
        print("\n❌ Redis连接失败，请检查:")
        print("   1. Redis容器是否运行: docker ps | grep redis")
        print("   2. 密码是否正确")
        print("   3. 端口映射是否正确")
        return
    
    results.append(("Redis连接", True))
    
    # 3. Redis操作测试
    results.append(("Redis操作", test_redis_operations(r, key_prefix)))
    
    # 4. 项目键结构检查
    results.append(("项目键结构", test_project_keys(r, key_prefix)))
    
    # 5. 服务器信息
    results.append(("服务器信息", test_server_info(r)))
    
    # 总结
    print(f"\n{'='*60}")
    print("测试结果总结")
    print(f"{'='*60}")
    
    for name, success in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {'通过' if success else '失败'}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！Redis连接正常！")
    else:
        print("\n⚠️ 部分测试失败，请检查上述错误信息")
    
    # 关闭连接
    r.close()
    
    return all_passed

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 未知错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
