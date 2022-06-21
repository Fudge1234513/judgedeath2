from steam.webapi import WebAPI


class SteamAPI:
    def __init__(self, key):
        self.core = WebAPI(key)

    def get_id(self, arg):
        if arg[-1] == "/":
            arg = arg[:-1]
        arg = arg.split("/")
        if not len(arg):
            return
        if len(arg) == 1 or arg[-2].lower() == "profiles":
            interface = "ISteamUser.GetPlayerSummaries"
            response = self.core.call(interface, steamids=arg[-1])
            if len(response["response"]["players"]):
                return response["response"]["players"][0]["steamid"]
        if len(arg) == 1 or arg[-2].lower() == "id":
            interface = "ISteamUser.ResolveVanityURL"
            response = self.core.call(interface, vanityurl=arg[-1])
            if "steamid" in response["response"]:
                return response["response"]["steamid"]

    def get_summaries(self, steam_ids):
        mapping = dict.fromkeys(steam_ids)
        interface = "ISteamUser.GetPlayerSummaries"
        for i in range((len(steam_ids) - 1) // 100 + 1):
            chunk = steam_ids[i * 100:i * 100 + 100]
            response = self.core.call(interface, steamids=",".join(chunk))
            for item in response["response"]["players"]:
                if item["steamid"] in mapping:
                    mapping[item["steamid"]] = {"name": item["personaname"],
                                                "avatar": item["avatarfull"],
                                                "url": item["profileurl"]}
        return mapping

    def get_player_count(self):
        interface = "ISteamUserStats.GetNumberOfCurrentPlayers"
        response = self.core.call(interface, appid=1418630)
        if response["response"]["result"] == 1:
            return response["response"]["player_count"]
