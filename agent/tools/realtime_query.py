import os
import yaml


EVENT_MEANINGS = {
    'E1': '重复添加Block', 'E2': '校验成功', 'E3': '提供Block服务',
    'E4': '服务异常', 'E5': '接收Block中', 'E6': '接收Block完成',
    'E7': '写Block异常', 'E8': '数据包响应中断', 'E9': '接收Block成功',
    'E10': '数据包响应异常', 'E11': '数据包响应终止', 'E12': '写镜像异常',
    'E13': '接收空数据包', 'E14': '接收Block异常', 'E15': '偏移变更',
    'E16': '传输完成', 'E17': '传输失败', 'E18': '开始传输',
    'E19': '重新打开Block', 'E20': '删除Block异常', 'E21': '删除Block文件',
    'E22': '分配Block', 'E23': '标记无效', 'E24': '移除复制',
    'E25': '请求复制', 'E26': 'Block映射更新', 'E27': '重复添加存储Block',
    'E28': 'Block不在文件中', 'E29': '复制超时'
}


def get_config_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config')


def query_realtime_anomalies(limit: int = 10) -> str:
    """从 ClickHouse 查询 Top N 异常 Block，包含完整事件分布。"""
    config_dir = get_config_dir()
    ch_path = os.path.join(config_dir, 'clickhouse.yaml')
    if not os.path.exists(ch_path):
        return "[错误] 找不到 ClickHouse 配置文件"

    with open(ch_path, 'r', encoding='utf-8') as f:
        ch_config = yaml.safe_load(f)['clickhouse']['online']

    try:
        import clickhouse_connect
        client = clickhouse_connect.get_client(
            host=ch_config['host'],
            port=ch_config.get('http_port', 8123),
            username=ch_config.get('username', 'default'),
            password=ch_config.get('password', '')
        )

        # 查询异常总数
        count_df = client.query_df(f"""
            SELECT count(DISTINCT block_id) as total
            FROM {ch_config['database']}.anomaly_blocks
        """)
        total_anomalies = int(count_df.iloc[0]['total']) if not count_df.empty else 0

        # 查询 Top N（多取候选以保证多样性）
        candidate_limit = limit * 5
        df = client.query_df(f"""
            SELECT
            block_id, anomaly_score, detected_at,
            E1, E2, E3, E4, E5, E6, E7, E8, E9, E10,
            E11, E12, E13, E14, E15, E16, E17, E18, E19, E20,
            E21, E22, E23, E24, E25, E26, E27, E28, E29
            FROM {ch_config['database']}.anomaly_blocks
            ORDER BY anomaly_score DESC
            LIMIT {candidate_limit}
        """)

        if df.empty:
            return "[提示] ClickHouse 中暂无异常数据"

        # 多样化筛选：按主导事件类型分组，轮询选取
        event_cols = [f'E{i}' for i in range(1, 30)]

        def get_dominant(row):
            max_val, dom = 0, 'E23'
            for col in event_cols:
                val = row.get(col, 0) or 0
                if val > max_val:
                    max_val, dom = val, col
            return dom

        df['dominant'] = df.apply(get_dominant, axis=1)

        groups = {}
        for _, row in df.iterrows():
            evt = row['dominant']
            if evt not in groups:
                groups[evt] = []
            groups[evt].append(row)

        selected = []
        keys = sorted(groups.keys())
        idx = {k: 0 for k in keys}
        while len(selected) < limit:
            added = False
            for k in keys:
                if idx[k] < len(groups[k]):
                    selected.append(groups[k][idx[k]])
                    idx[k] += 1
                    added = True
                    if len(selected) >= limit:
                        break
            if not added:
                break

        # 格式化输出
        output = [f"[查询] Top {len(selected)} 异常Block（ClickHouse中共 {total_anomalies} 个异常Block）", ""]

        for i, row in enumerate(selected, 1):
            events = []
            for col in event_cols:
                val = int(row.get(col, 0) or 0)
                if val > 0:
                    meaning = EVENT_MEANINGS.get(col, col)
                    events.append((col, val, meaning))
            events.sort(key=lambda x: x[1], reverse=True)

            dominant = events[0] if events else ('N/A', 0, '未知')
            event_str = " ".join([f"{e}:{v}" for e, v, _ in events])

            output.append(f"{i}. {row['block_id']}")
            output.append(f"   主导事件: {dominant[0]}:{dominant[1]} ({dominant[2]})")
            output.append(f"   全部事件: {event_str}")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"[错误] ClickHouse 查询失败: {str(e)}"
