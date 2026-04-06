import re
import pandas as pd
import numpy as np
from collections import defaultdict

class LogPreprocessor:
    def __init__(self):
        self.templates = {}
        self.template_counter = 0
    
    def load_templates(self, template_file):
        """加载预定义的日志模板"""
        data = pd.read_csv(template_file)
        for _, row in data.iterrows():
            event_id = row['EventId']
            template = row['EventTemplate']
            self.templates[template] = event_id
        # 反转映射，方便通过事件ID查找模板
        self.id_to_template = {v: k for k, v in self.templates.items()}
    
    def preprocess_log(self, log_file, output_file):
        """预处理日志文件，生成事件出现矩阵"""
        # 读取日志文件
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
            logs = f.readlines()
        
        # 初始化事件计数器
        event_counts = defaultdict(lambda: defaultdict(int))
        current_block = None
        
        # 处理每条日志
        for log in logs:
            # 提取块ID
            block_match = re.search(r'blk_[-\d]+', log)
            if block_match:
                current_block = block_match.group(0)
            
            if current_block:
                # 模板化日志
                templated_log = self.template_log(log)
                # 查找对应的事件ID
                event_id = self.templates.get(templated_log, 'Unknown')
                if event_id != 'Unknown':
                    event_counts[current_block][event_id] += 1
        
        # 生成事件出现矩阵
        blocks = list(event_counts.keys())
        event_ids = sorted(self.templates.values())
        
        # 创建数据框
        data = []
        for block in blocks:
            row = {'BlockId': block}
            for event_id in event_ids:
                row[event_id] = event_counts[block].get(event_id, 0)
            data.append(row)
        
        df = pd.DataFrame(data)
        
        # 保存结果
        df.to_csv(output_file, index=False)
        print(f'Preprocessed log saved to {output_file}')
    
    def template_log(self, log):
        """将日志转换为模板"""
        # 替换IP地址
        log = re.sub(r'\d+\.\d+\.\d+\.\d+', '<*>', log)
        # 替换日期时间
        log = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}', '<*>', log)
        # 替换数字
        log = re.sub(r'\b\d+\b', '<*>', log)
        # 替换块ID
        log = re.sub(r'blk_[-\d]+', '<*>', log)
        return log

if __name__ == '__main__':
    preprocessor = LogPreprocessor()
    # 加载预定义的模板
    preprocessor.load_templates('HDFS_v1/preprocessed/HDFS.log_templates.csv')
    # 预处理日志
    preprocessor.preprocess_log('HDFS_v1/HDFS.log', 'HDFS_v1/preprocessed/Event_occurrence_matrix_new.csv')
