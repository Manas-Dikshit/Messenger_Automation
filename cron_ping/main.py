import requests

data = requests.get('https://philiphacker.in/api/deb/test.php?data=testdev2')
print(data.json())