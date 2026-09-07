import urllib.request, json, sys
sys.stdout.reconfigure(encoding='utf-8')

try:
    res = json.loads(urllib.request.urlopen('http://localhost:1234/api/status').read().decode('utf-8'))
    print("STATUS SNAPSHOT:")
    print(f"Status: {res.get('status')}")
    print(f"Is running: {res.get('is_running')}")
    print(f"Engine: {res.get('engine')}")
    print(f"Auto close: {res.get('auto_close')}")
    print(f"Status message: {res.get('status_message')}")
    print(f"Total scanned: {res.get('total_scanned')}")
    print(f"Total closed: {res.get('total_closed')}")
    print("\nLATEST LOGS:")
    for l in res.get('logs', [])[-25:]:
        print(f"[{l.get('time')}] [{l.get('level')}] {l.get('message')}")
except Exception as e:
    print("Error:", e)
