#!/usr/bin/env python3
"""
将大文件按指定行数分割成多个小文件
"""
import os
import sys

SOURCE_FILE = r"E:\private_project\AI_application\HDFS_Test"
OUTPUT_DIR = r"E:\private_project\AI_application\HDFS_Test\processed"
LINES_PER_FILE = 1000000  # 每100万行一个文件

def split_file():
    if not os.path.exists(SOURCE_FILE):
        print(f"❌ 源文件不存在: {SOURCE_FILE}")
        return
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    file_num = 1
    line_count = 0
    current_file = None
    
    print(f"📂 源文件: {SOURCE_FILE}")
    print(f"📁 输出目录: {OUTPUT_DIR}")
    print(f"📊 每文件行数: {LINES_PER_FILE:,}")
    print("-" * 50)
    
    with open(SOURCE_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if line_count % LINES_PER_FILE == 0:
                if current_file:
                    current_file.close()
                    print(f"  已保存: {os.path.basename(output_path)} ({line_count:,} 行)")
                
                output_path = os.path.join(OUTPUT_DIR, f"HDFS{file_num}.log")
                current_file = open(output_path, 'w', encoding='utf-8')
                file_num += 1
            
            current_file.write(line)
            line_count += 1
            
            if line_count % LINES_PER_FILE == 0:
                print(f"  进度: {line_count:,} 行...")
    
    if current_file:
        current_file.close()
        print(f"  已保存: {os.path.basename(output_path)} ({line_count % LINES_PER_FILE:,} 行)")
    
    print("-" * 50)
    print(f"✅ 完成！共分成 {file_num - 1} 个文件，总计 {line_count:,} 行")

if __name__ == '__main__':
    split_file()
