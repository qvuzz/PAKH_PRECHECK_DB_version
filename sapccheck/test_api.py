import requests

url = "http://10.155.42.218/api/sapc/84917969796"

r = requests.get(url)

print("STATUS:", r.status_code)
print(r.text[:1000])