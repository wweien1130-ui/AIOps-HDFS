import requests
url = "http://192.168.115.129:8123/"
query = "SELECT 1"
auth = ('default', '')
r = requests.post(url, params={'query': query}, auth=auth)
print(r.status_code, r.text)
