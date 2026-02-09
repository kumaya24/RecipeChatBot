import requests
from bs4 import BeautifulSoup
import json

url = "https://www.allrecipes.com/recipe/10485/salted-peanut-cookies/"
html = requests.get(url).text

soup = BeautifulSoup(html, "html.parser")
for s in soup.find_all("script", type="application/ld+json"):
    try:
        data = json.loads(s.string)
        print(type(data))
        print(data)
        break
    except:
        pass