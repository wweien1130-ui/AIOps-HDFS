import requests

url = "http://192.168.115.129:8124/"
query = "SELECT 1"
auth = ('default', '')  # 空密码

try:
    r = requests.post(url, params={'query': query}, auth=auth)
    print("状态码:", r.status_code)
    print("返回内容:", r.text)
    if r.text.strip() == '1':
        print("✅ 连接成功，空密码有效")
    else:
        print("❌ 返回异常")
except Exception as e:
    print("❌ 连接失败:", e)