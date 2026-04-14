# kafka_verifier.py
import socket
import time
import sys
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient
from kafka.errors import NoBrokersAvailable, NodeNotReadyError
import subprocess
import platform


class KafkaConnectionVerifier:
    def __init__(self, bootstrap_servers='192.168.115.129:9092'):
        self.bootstrap_servers = bootstrap_servers
        self.host, self.port = bootstrap_servers.split(':')
        self.port = int(self.port)

    def print_section(self, title):
        print(f"\n{'=' * 60}")
        print(f"  {title}")
        print(f"{'=' * 60}")

    def test_network(self):
        """测试网络连通性"""
        self.print_section("1. 网络连通性测试")

        # Ping 测试
        print(f"Ping 测试: {self.host}")
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        result = subprocess.run(['ping', param, '1', self.host],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Ping 成功")
        else:
            print(f"  ❌ Ping 失败")
            return False

        # 端口测试
        print(f"\n端口测试: {self.host}:{self.port}")
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((self.host, self.port))
            sock.close()

            if result == 0:
                print(f"  ✅ 端口 {self.port} 开放")
            else:
                print(f"  ❌ 端口 {self.port} 关闭")
                return False
        except Exception as e:
            print(f"  ❌ 端口测试失败: {e}")
            return False

        return True

    def test_kafka_connection(self):
        """测试 Kafka 连接"""
        self.print_section("2. Kafka 连接测试")

        # 尝试 Admin 连接
        for attempt in range(3):
            try:
                print(f"尝试连接 (第 {attempt + 1}/3 次)...")
                admin = KafkaAdminClient(
                    bootstrap_servers=self.bootstrap_servers,
                    request_timeout_ms=5000,
                    api_version_auto_timeout_ms=5000
                )
                topics = admin.list_topics()
                print(f"  ✅ Kafka 连接成功!")
                print(f"  现有主题: {list(topics)}")
                admin.close()
                return True

            except NodeNotReadyError:
                print(f"  ⚠️ Kafka 节点未就绪，等待 3 秒...")
                time.sleep(3)
            except NoBrokersAvailable:
                print(f"  ❌ 无法找到 Kafka broker")
                return False
            except Exception as e:
                print(f"  ❌ 连接失败: {type(e).__name__}: {e}")
                if attempt < 2:
                    print(f"  等待 3 秒重试...")
                    time.sleep(3)

        return False

    def test_producer(self):
        """测试生产者"""
        self.print_section("3. 生产者测试")

        try:
            producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: v.encode('utf-8'),
                request_timeout_ms=5000,
                acks=1
            )

            # 发送测试消息
            test_message = f"Test message from verifier at {time.time()}"
            future = producer.send('test-verification', test_message)
            result = future.get(timeout=5)

            print(f"  ✅ 消息发送成功!")
            print(f"  主题: test-verification")
            print(f"  分区: {result.partition}")
            print(f"  偏移量: {result.offset}")
            producer.close()
            return True

        except Exception as e:
            print(f"  ❌ 生产者测试失败: {e}")
            return False

    def test_consumer(self):
        """测试消费者"""
        self.print_section("4. 消费者测试")

        try:
            consumer = KafkaConsumer(
                'test-verification',
                bootstrap_servers=self.bootstrap_servers,
                auto_offset_reset='earliest',
                group_id='verifier-group',
                value_deserializer=lambda m: m.decode('utf-8'),
                consumer_timeout_ms=3000
            )

            messages = []
            for msg in consumer:
                messages.append(msg.value)
                break

            consumer.close()

            if messages:
                print(f"  ✅ 消息消费成功!")
                print(f"  消息内容: {messages[0][:100]}")
                return True
            else:
                print(f"  ⚠️ 未消费到消息 (可能主题为空)")
                return True  # 不算失败，可能只是没有消息

        except Exception as e:
            print(f"  ❌ 消费者测试失败: {e}")
            return False

    def test_topic_operations(self):
        """测试主题操作"""
        self.print_section("5. 主题操作测试")

        test_topic = "test-operations"

        # 创建主题
        try:
            result = subprocess.run([
                'docker', 'exec', 'kafka',
                '/opt/kafka/bin/kafka-topics.sh',
                '--create', '--topic', test_topic,
                '--bootstrap-server', 'localhost:9092',
                '--partitions', '3', '--replication-factor', '1'
            ], capture_output=True, text=True)

            if result.returncode == 0 or "already exists" in result.stderr:
                print(f"  ✅ 主题创建成功")
            else:
                print(f"  ⚠️ 主题创建失败: {result.stderr}")

        except Exception as e:
            print(f"  ⚠️ 无法测试主题创建: {e}")

        # 列出主题
        try:
            result = subprocess.run([
                'docker', 'exec', 'kafka',
                '/opt/kafka/bin/kafka-topics.sh',
                '--list', '--bootstrap-server', 'localhost:9092'
            ], capture_output=True, text=True)

            if result.returncode == 0:
                topics = result.stdout.strip().split('\n')
                print(f"  ✅ 当前主题: {topics[:5]}")
            else:
                print(f"  ⚠️ 无法列出主题")

        except Exception as e:
            print(f"  ⚠️ 无法列出主题: {e}")

    def full_verification(self):
        """完整验证流程"""
        print("\n" + "=" * 60)
        print(" Kafka 连接完整验证器")
        print(f" 目标: {self.bootstrap_servers}")
        print("=" * 60)

        results = []

        # 1. 网络测试
        results.append(("网络连通性", self.test_network()))

        if not results[-1][1]:
            print("\n❌ 网络测试失败，请检查:")
            print("  1. Ubuntu VM 是否运行")
            print("  2. VMware 端口转发是否配置")
            print("  3. Kafka 容器是否启动")
            return False

        # 2. Kafka 连接测试
        results.append(("Kafka 连接", self.test_kafka_connection()))

        if not results[-1][1]:
            print("\n❌ Kafka 连接失败，请检查:")
            print("  1. Kafka 容器是否完全启动")
            print("  2. advertised.listeners 配置")
            return False

        # 3. 生产者测试
        results.append(("生产者", self.test_producer()))

        # 4. 消费者测试
        results.append(("消费者", self.test_consumer()))

        # 5. 主题操作测试
        self.test_topic_operations()

        # 总结
        self.print_section("验证结果总结")
        for name, success in results:
            status = "✅" if success else "❌"
            print(f"  {status} {name}: {'通过' if success else '失败'}")

        all_passed = all(success for _, success in results)

        if all_passed:
            print("\n🎉 所有测试通过！Kafka 连接正常！")
        else:
            print("\n⚠️ 部分测试失败，请检查上述错误信息")

        return all_passed


def quick_verify():
    """快速验证"""
    print("\n快速验证 Kafka 连接...")

    # 测试网络
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('192.168.115.129', 9092))
        sock.close()

        if result != 0:
            print("❌ 无法连接到 192.168.115.129:9092")
            print("请检查:")
            print("  1. Ubuntu VM 是否运行")
            print("  2. Kafka 容器是否启动: docker ps | grep kafka")
            print("  3. VMware 端口转发: 主机9092 -> 虚拟机9092")
            return False
        else:
            print("✅ 端口 9092 可访问")

    except Exception as e:
        print(f"❌ 网络测试失败: {e}")
        return False

    # 测试 Kafka
    try:
        admin = KafkaAdminClient(
            bootstrap_servers='192.168.115.129:9092',
            request_timeout_ms=5000
        )
        topics = admin.list_topics()
        print(f"✅ Kafka 连接成功，主题: {list(topics)}")
        admin.close()
        return True
    except Exception as e:
        print(f"❌ Kafka 连接失败: {e}")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Kafka 连接验证器')
    parser.add_argument('--host', default='192.168.115.129:9092',
                        help='Kafka 地址 (默认: 192.168.115.129:9092)')
    parser.add_argument('--quick', action='store_true',
                        help='快速验证模式')
    args = parser.parse_args()

    if args.quick:
        quick_verify()
    else:
        verifier = KafkaConnectionVerifier(args.host)
        verifier.full_verification()