import itertools

import requests

url = "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"

for num in itertools.count(1):
    u = url.format(num)
    print("Downloading", u)
    r = requests.get(u)
    if r.status_code != 200:
        break
    with open(f"subs/subst_{num:03}.htm", "wb") as f:
        f.write(r.content)
    if b'; URL=subst_001.htm">' in r.content:
        break
