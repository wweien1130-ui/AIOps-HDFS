# test_delete_windows.py
from kafka.admin import KafkaAdminClient, NewTopic
from kafka import KafkaProducer, KafkaConsumer
import time

bootstrap = '192.168.115.129:9092'
topic = 'test-delete-python'

print("="*50)
print("测试 Kafka 删除功能")
print("="*50)

admin = KafkaAdminClient(bootstrap_servers=bootstrap)

# 1. 创建主题
print("\n1. 创建主题...")
try:
    admin.delete_topics([topic])
    time.sleep(2)
except:
    pass
admin.create_topics([NewTopic(topic, num_partitions=3, replication_factor=1)])
print(f"   ✅ 主题 '{topic}' 创建成功")

# 2. 发送消息
print("\n2. 发送测试消息...")
producer = KafkaProducer(
    bootstrap_servers=bootstrap,
    value_serializer=lambda v: v
)
producer.send(topic, b'test data')
producer.flush()
print(f"   ✅ 消息已发送")

# 3. 消费消息验证
print("\n3. 验证消息...")
consumer = KafkaConsumer(
    topic,
    bootstrap_servers=bootstrap,
    auto_offset_reset='earliest',
    consumer_timeout_ms=5000
)
messages = list(consumer)
print(f"   ✅ 收到 {len(messages)} 条消息")

# 4. 删除主题
print("\n4. 删除主题...")
admin.delete_topics([topic])
time.sleep(2)
print(f"   ✅ 删除命令已执行")

# 5. 验证删除
topics = admin.list_topics()
if topic not in topics:
    print("\n🎉 删除成功！主题已不存在")
else:
    print(f"\n❌ 删除失败，主题仍然存在: {topic}")

admin.close()