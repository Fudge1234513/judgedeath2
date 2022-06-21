from datetime import datetime, timezone, timedelta

from discord import Embed
from discord.ui import Button, View

from core.utils import BlockView, EditView, REASONS, COLORS, escape_characters


class MessageConstructor:
    @staticmethod
    def basic(text):
        embed = Embed(title=f"**{text}**", color=0x99d959)
        return {"embed": embed}

    @staticmethod
    def error(text):
        embed = Embed(title=f"**{text}**", color=0xff3f3f)
        return {"embed": embed}

    @staticmethod
    def helper(level):
        embed = Embed(title="**Commands:**",
                      color=0x99d959)
        embed.add_field(name="LVL0: Send this message",
                        value="`?help`", inline=False)
        if level == 0:
            return {"embed": embed}
        embed.add_field(name="LVL1: Check if profile is listed",
                        value="`?check {link/id}`", inline=False)
        if level == 1:
            return {"embed": embed}
        embed.add_field(name="LVL2: Add profile to the list",
                        value="`?block {link/id}`", inline=False)
        if level == 2:
            return {"embed": embed}
        if level == 3:
            embed.add_field(name="LVL3: Edit reasons for existing record",
                            value="`?edit {link/id}`\n", inline=False)
            return {"embed": embed}
        embed.add_field(name="LVL4: Edit or delete existing record",
                        value="`?edit {link/id} {k1:v1;k2:v2;...}`\n", inline=False)
        embed.add_field(name="LVL4: Restore missing messages now",
                        value="`?restore`", inline=False)
        if level == 4:
            return {"embed": embed}
        embed.add_field(name="LVL5: Set current channel",
                        value="`?set-channel {channel name}`", inline=False)
        embed.add_field(name="LVL5: Set to the private mode (with initiator field)",
                        value="`?set-private`", inline=False)
        embed.add_field(name="LVL5: Set to the public mode (without initiator field)",
                        value="`?set-public`", inline=False)
        embed.add_field(name="LVL5: Set command permissions",
                        value="`?set-permissions {level} {r1;r2;...}`", inline=False)
        embed.add_field(name="LVL5: Display command permissions",
                        value="`?get-permissions`", inline=False)
        return {"embed": embed}

    @staticmethod
    def permissions(permissions):
        embed = Embed(title="**Permissions:**",
                      color=0x99d959)
        for i in range(6):
            embed.add_field(name=f"{i}", inline=False,
                            value=", ".join(permissions[i]) or "**-**")
        return {"embed": embed}

    @staticmethod
    def check(message_url):
        embed = Embed(title=f"**User is tracked!**", color=0x99d959)
        button = Button(label="User card", url=message_url)
        view = View(button)
        return {"embed": embed, "view": view}

    @staticmethod
    def block(database, guild_id, steam_id, ctx, item):
        embed = Embed(title=escape_characters(item["name"]),
                      description=escape_characters(item["url"][27: -1]),
                      color=0x6817ff, url=item["url"])
        embed.set_thumbnail(url=item["avatar"])
        embed.set_footer(text="|{}|\nSteamID: {}".format("\u3000" * 35,
                                                         steam_id))
        view = BlockView(database, guild_id, steam_id, ctx, item)
        return {"embed": embed, "view": view}

    @staticmethod
    def edit(database, guild_id, steam_id, ctx, rich, args):
        item = database.get_record(guild_id, steam_id)
        embed = Embed(title=escape_characters(item["name"]),
                      description=escape_characters(item["url"][27: -1]),
                      color=0x6817ff, url=item["url"])
        embed.set_thumbnail(url=item["avatar"])
        for k in ["initiator", "encounters", "date", "last_date"]:
            if k in args:
                embed.add_field(name=k, value=args[k], inline=False)
        embed.set_footer(text="|{}|\nSteamID: {}".format("\u3000" * 35,
                                                         steam_id))
        view = EditView(database, guild_id, steam_id, ctx, rich, args)
        return {"embed": embed, "view": view}

    @staticmethod
    def card(steam_id, item, is_private, i):
        status = 0
        reasons = []
        for reason, reason_status in REASONS:
            if reason in item["reasons"]:
                status = max(status, reason_status)
                if len(reasons):
                    reasons.append(reason.lower())
                else:
                    reasons.append(reason)
        color = COLORS[status]
        old_names = map(lambda x: "`{}`".format(x.replace("`", "'")),
                        item["old_names"][-6: -1][:: -1])
        old_names = "\n".join(old_names) or "**-**"
        ending = "" if item["encounters"] == 1 else "s"
        last_date = ""
        if item["last_date"] != item["date"]:
            last_date = "->" + item["last_date"]
        ld = datetime.strptime(item["last_date"], "%d/%m/%Y")
        tzinfo = timezone(timedelta(hours=3))
        ld = ld.replace(tzinfo=tzinfo)
        td = datetime.now(tzinfo)
        d = (td - ld).days
        latency = "(today)"
        if d:
            latency = " ({} day{} ago)".format(d, "s" * int(d > 1))

        embed = Embed(title=escape_characters(item["name"]),
                      description=escape_characters(item["url"][27: -1]),
                      color=color, url=item["url"])
        embed.set_author(name=", ".join(reasons[:3]))
        embed.set_thumbnail(url=item["avatar"])
        embed.add_field(name="Last names",
                        value=old_names, inline=False)
        embed.add_field(name="{} encounter{} {}".format(item["encounters"], ending, latency),
                        inline=is_private, value="{}{}".format(item["date"], last_date))
        if is_private:
            embed.add_field(name="Initiator", inline=is_private,
                            value=escape_characters(item["initiator"]))
        embed.set_footer(text="\u200B{}\u200B\n{} - SteamID: {}".format("\u3000" * 35,
                                                                        i, steam_id))
        return {"embed": embed}
