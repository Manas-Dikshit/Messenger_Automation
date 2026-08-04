import requests

data = requests.get('https://philiphacker.in/api/deb/test.php?data=testdev')
print(data.json())