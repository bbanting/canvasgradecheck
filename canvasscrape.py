# For scraping course data from canvas.
# This is necessary because the api authorization is messed up.

import requests
import json
from bs4 import BeautifulSoup


with open("config.json", "r") as fp:
    config = json.load(fp)



login_url = config["login_url"] + "/login/ldap"

session = requests.session()
document = session.get(login_url).text
soup = BeautifulSoup(document, "html.parser")

token = soup.find(attrs={"name": "authenticity_token"})["value"]
payload = {
    "pseudonym_session[unique_id]": config["uname"],
    "pseudonym_session[password]": config["pass"],
    "authenticity_token": token,
}
session.post(login_url, payload, headers={"referer": login_url})

result = session.get(config["base_url"] + "/accounts/" + config["account"])
soup =  BeautifulSoup(result.text, "html.parser")