import requests
from bs4 import BeautifulSoup

header = {"User-Agent": "Mozilla/5.0(Windows NT 10.0; Win64; x64)"}
url = "https://www.allrecipes.com/ingredients-a-z-6740416"
html = requests.get(url, headers = header, timeout=10).text
soup = BeautifulSoup(html, "html.parser")

ingredients = soup.select("main ul li a")

for a in ingredients:
    name = a.get_text(strip =True)
    href = a.get("href")
    print(name,":", href)

with open("data/category_links.txt","w") as f:
    for a in ingredients:
        href = a.get("href")
        if href:
            f.write(href + "\n")




