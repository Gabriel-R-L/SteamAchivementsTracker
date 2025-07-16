import os
from concurrent.futures import ThreadPoolExecutor

import httpx
from flask import Flask, jsonify, render_template

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/games/<steam_id>")
def get_games(steam_id):
    owned_url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    owned_params = {
        "key": os.getenv("STEAM_API_KEY"),
        "steamid": steam_id,
        "include_appinfo": True,
        "include_played_free_games": True,
    }

    owned_response = httpx.get(owned_url, params=owned_params).json()
    owned_games = owned_response.get("response", {}).get("games", [])

    games_with_achievements = []

    def get_game_data(game: dict):
        try:
            achievements_response = httpx.get(
                str(os.getenv("STEAM_USER_STATS_URL")),
                params={
                    "key": os.getenv("STEAM_API_KEY"),
                    "steamid": steam_id,
                    "appid": game["appid"],
                },
            ).json()
            achievements = achievements_response["playerstats"].get("achievements", [])
            if not achievements:
                return {}

            unlocked = sum(1 for a in achievements if a["achieved"] == 1)
            total = len(achievements)

            return {
                "unlocked": unlocked,
                "total": total,
                "percent": int((unlocked / total) * 100),
            }
        except Exception:
            return {}

    with ThreadPoolExecutor(max_workers=len(owned_games) if len(owned_games) < 100 else 100) as executor:
        futures = [executor.submit(get_game_data, game) for game in owned_games]
        
        # for f in futures:
        #     input(f.result())
        

    # for game in owned_games:
    #     appid = game["appid"]
    #     name = game["name"]
    #     total_playtime = game["playtime_forever"]
    #     image_icon_hash = game["img_icon_url"]
    #     last_time_played = game["rtime_last_played"]

    #     image_url = f"http://media.steampowered.com/steamcommunity/public/images/apps/{appid}/{image_icon_hash}.jpg"

    #     # image_url = (
    #     #     f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{image_icon_hash}.jpg"
    #     # )

    #     try:
    #         games_with_achievements.append(
    #             {
    #                 "name": name,
    #                 "image_url": image_url,
    #                 "achievement_percent": percent,
    #                 "total_playtime": total_playtime,
    #                 "last_time_played": last_time_played,
    #             }
    #         )
    #     except Exception:
    #         continue
    return jsonify(games_with_achievements)


if __name__ == "__main__":
    app.run(debug=True, load_dotenv=True)
