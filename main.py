import os
from concurrent.futures import ThreadPoolExecutor

import httpx
from typing import Any
from flask import Flask, jsonify, render_template

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")

DEBUG = True
API_KEY = os.getenv("STEAM_API_KEY")
GAME_IMAGES = [
    "https://cdn.cloudflare.steamstatic.com/steam/apps/<app_id>/header.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/<app_id>/capsule_616x353.jpg",
    "https://cdn.cloudflare.steamstatic.com/steam/apps/<app_id>/library_hero.jpg",
]


###################################################################################################################################
# Routes
###################################################################################################################################
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/games/<steam_id>")
def get_games(steam_id):
    owned_url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"

    params = {
        "key": API_KEY,
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True,
    }

    owned_response = httpx.get(owned_url, params=params).json()
    owned_games = owned_response.get("response", {}).get("games", [])

    with ThreadPoolExecutor(
        max_workers=len(owned_games) if len(owned_games) < 100 else 100
    ) as executor:
        futures = [
            executor.submit(get_game_data, game, steam_id) for game in owned_games
        ]
    return jsonify([future.result() for future in futures if future.result()])


###################################################################################################################################
# Aux methods
###################################################################################################################################
def get_achivements_guides(url: str):
    """
    temkp: https://steamcommunity.com/app/1174180/guides/?browsefilter=trend&requiredtags[]=Achievements#scrollTop=0
    https://steamcommunity.com/app/238960/guides/?browsefilter=trend&requiredtags[]=Achievements

    Args:
        url (str): _description_

    Returns:
        _type_: _description_
    """
    try:
        return httpx.get(url).json() or {}
    except Exception:
        return {}


def get_game_achivements_info(url: str, app_id: str) -> dict[str, Any]:
    """
    Get achivements info from a game url.

    Args:
        url (str): URL used to get achivement details. The base is: `https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key=<apiKey>&appid=<appid>`

    Returns:
        dict: Resultado esperado `{'name': str, 'displayName': str, 'description': str, 'icon': 'https://steamcdn-a.akamaihd.net/steamcommunity/public/images/apps/<appId>/<hash>.jpg'}`
    """
    try:
        return {
            "trophies": httpx.get(url).json() or {},
            "guides_url": f"https://steamcommunity.com/app/{app_id}/guides/?browsefilter=trend&requiredtags[]=Achievements",
        }
    except Exception:
        return {}


def check_valid_img(url):
    try:
        return (
            True
            if (
                status_code := httpx.head(
                    url, timeout=3, follow_redirects=True
                ).status_code
            )
            and status_code == 200
            else False
        )
    except Exception:
        return False


def get_game_data(game: dict, steam_id: str):
    try:
        achievements_response = httpx.get(
            str(os.getenv("STEAM_USER_STATS_URL")),
            params={
                "key": API_KEY,
                "steamid": steam_id,
                "appid": game["appid"],
            },
        ).json()
        achievements = achievements_response["playerstats"].get("achievements", [])
        if not achievements:
            return {}
        achivements_details = get_game_achivements_info(
            f"https://api.steampowered.com/ISteamUserStats/GetSchemaForGame/v2/?key={API_KEY}&appid={game['appid']}",
            game["appid"],
        )

        unlocked = sum(1 for a in achievements if a["achieved"] == 1)
        total = len(achievements)

        image_url = None
        for img_url in GAME_IMAGES:
            url = img_url.replace("<app_id>", str(game["appid"]))
            if check_valid_img(url):
                image_url = url
                break
        if not image_url:
            image_url = (
                f"http://media.steampowered.com/steamcommunity/public/images/apps/{game['appid']}/{game['img_icon_url']}.jpg",
            )

        # 1. https://cdn.cloudflare.steamstatic.com/steam/apps/{game['appid']}/header.jpg >> header (468x215 px) 🌄
        # 2. https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/capsule_616x353.jpg >> capsule (616x353 px) 🌅
        # 3. https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/library_hero.jpg >> hero image 🌇
        # 4. http://media.steampowered.com/steamcommunity/public/images/apps/{game['appid']}/{game['img_icon_url']}.jpg >> icon (32x32 or 64x64 px) image 🖼️

        return {
            **game,
            **{
                "image_url": image_url,
                "unlocked": unlocked,
                "total": total,
                "achievement_percent": int((unlocked / total) * 100),
                "achivements": achivements_details.get("trophies"),
                "guides": achivements_details.get("guides_url"),
            },
        }
    except Exception:
        return {}


app.run(debug=True, load_dotenv=DEBUG)
