import pandas as pd
import sys
import os


def remove_last_n_percent(input_file, output_file, percent=10):
    if not os.path.exists(input_file):
        print(f"错误: 输入文件 '{input_file}' 不存在")
        return False

    df = pd.read_csv(input_file)
    total_rows = len(df)

    if total_rows == 0:
        print("错误: CSV文件为空")
        return False

    rows_to_remove = int(total_rows * percent / 100)

    if rows_to_remove == 0:
        print(f"警告: 文件总行数{total_rows}，10%为{rows_to_remove}行，不需要删除")
        df.to_csv(output_file, index=False)
        print(f"已保存到: {output_file}")
        return True

    df_trimmed = df.iloc[:-rows_to_remove]

    removed_count = total_rows - len(df_trimmed)
    print(f"原始行数: {total_rows}")
    print(f"删除行数: {removed_count} ({percent}%)")
    print(f"剩余行数: {len(df_trimmed)}")

    df_trimmed.to_csv(output_file, index=False)
    print(f"已保存到: {output_file}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python remove_last_10_percent.py <输入文件> <输出文件> [删除百分比]")
        print("示例: python remove_last_10_percent.py input.csv output.csv 10")
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        percent = int(sys.argv[3]) if len(sys.argv) > 3 else 10

        remove_last_n_percent(input_file, output_file, percent)