import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:5000/api/admin/drivers',
    method='POST',
    headers={'Content-Type': 'application/json'},
    data=json.dumps({
        "driver_id": "DRV-TEST",
        "name": "Test Driver",
        "phone": "1234567890",
        "password": "pass"
    }).encode('utf-8')
)

try:
    with urllib.request.urlopen(req) as response:
        print(response.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print(e.read().decode('utf-8'))
