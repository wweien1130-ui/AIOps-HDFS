import csv

input_file = "E:\private_project\AI_application\HDFS_v1\preprocessed\Event_occurrence_matrix.csv"
output_file = "Event.csv"

with open(input_file, 'r', newline='', encoding='utf-8') as infile, \
     open(output_file, 'w', newline='', encoding='utf-8') as outfile:

    reader = csv.DictReader(infile)
    # 获取原始列名（可能包含 BOM 头，但一般无碍）
    fieldnames = reader.fieldnames

    # 确保 'BlockId' 和 'Label' 存在
    if 'BlockId' not in fieldnames or 'Label' not in fieldnames:
        raise ValueError("CSV 文件中缺少 BlockId 或 Label 列")

    writer = csv.DictWriter(outfile, fieldnames=['BlockId', 'Label'])
    writer.writeheader()

    for row in reader:
        writer.writerow({'BlockId': row['BlockId'], 'Label': row['Label']})

print(f"已提取 {output_file} 文件，包含 BlockId 和 Label 两列。")