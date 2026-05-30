# -*- coding: utf-8 -*-  
\"\"  
\"\" 
@tool(description=\"删除ClickHouse offline指定批次的数据（需要人工确认）\")  
def delete_offline_batch(batch_id: str, confirm: bool = False) -> str: 
