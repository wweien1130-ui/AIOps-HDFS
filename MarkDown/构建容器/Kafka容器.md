# KAFKA

### 1. 创建 Kafka（KRaft 模式，host 网络）

```bash
docker run -d \
  --network=host \
  --name kafka \
  -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_NODE_ID=1 \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_LISTENERS=PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://192.168.115.129:9092 \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT \
  -e KAFKA_LOG_DIRS=/tmp/kraft-combined-logs \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_DELETE_TOPIC_ENABLE=true \
  apache/kafka:3.7.0
```


### 2、创建 Kafka Topics

```bash
# 在线 Topic
docker exec kafka /opt/kafka/bin/kafka-topics.sh --create \
  --topic hdfs-logs-online \
  --bootstrap-server localhost:9092 \
  --partitions 6 --replication-factor 1

# 离线 Topic
docker exec kafka /opt/kafka/bin/kafka-topics.sh --create \
  --topic hdfs-logs-offline \
  --bootstrap-server localhost:9092 \
  --partitions 6 --replication-factor 1
```
