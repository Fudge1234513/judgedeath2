from asyncio import Lock
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import orjson

from core.accountant import Accountant


class Database:
    def __init__(self, bot):
        self.tzinfo = timezone(timedelta(hours=3))
        self.bot = bot
        self.accountants = {}
        self.state = {}
        self.locks = {}
        try:
            with open("data/state.json", "rb") as f:
                self.state = orjson.loads(f.read())
        except FileNotFoundError:
            self.state = {"time": None, "guilds": {}}
        for guild_id, guild_data in self.state["guilds"].items():
            self.accountants[guild_id] = {}
            self.locks[guild_id] = Lock()
            channel_id = guild_data["channel"]
            is_private = guild_data["private"]
            for steam_id, item in guild_data["data"].items():
                accountant = Accountant(self.bot, channel_id, steam_id,
                                        item, is_private, self.make_counter(guild_id))
                self.accountants[guild_id][steam_id] = accountant

    def save_state(self):
        self.state["time"] = datetime.now(
            self.tzinfo).strftime("%Y-%m-%d-%H:%M:%S")
        with open("data/state.json", "wb") as f:
            f.write(orjson.dumps(self.state))

    def backup_state(self):
        time = datetime.now(self.tzinfo).strftime("%Y-%m-%d-%H_%M_%S")
        with open(f"backups/{time}.json", "wb") as f:
            f.write(orjson.dumps(self.state))

    def check_guild(self, guild_id):
        return guild_id in self.state["guilds"]

    def make_counter(self, guild_id):
        def f():
            if not self.check_guild(guild_id):
                raise ValueError("Missing guild.")
            self.state["guilds"][guild_id]["counter"] += 1
            return self.state["guilds"][guild_id]["counter"]
        return f

    def add_guild(self, guild_id, channel_id):
        if self.check_guild(guild_id):
            raise ValueError("Guild is already present.")
        self.state["guilds"][guild_id] = {"channel": channel_id, "private": True,
                                          "counter": 0, "data": {}}
        self.accountants[guild_id] = {}
        self.locks[guild_id] = Lock()

    async def set_channel(self, guild_id, channel_id):
        async with self.locks[guild_id]:
            if not self.check_guild(guild_id):
                raise ValueError("Missing guild.")
            self.state["guilds"][guild_id]["channel"] = channel_id
            for accountant in self.accountants[guild_id]:
                await accountant.set_channel(channel_id)

    async def set_private(self, guild_id, is_private):
        async with self.locks[guild_id]:
            if not self.check_guild(guild_id):
                raise ValueError("Missing guild.")
            if self.state["guilds"][guild_id]["private"] == is_private:
                return
            self.state["guilds"][guild_id]["private"] = is_private
            order = sorted([(datetime.strptime(self.state["guilds"][guild_id]["data"][x]["last_date"], "%d/%m/%Y"), x)
                            for x in self.accountants[guild_id].keys()])
            for _, steam_id in order:
                try:
                    await self.accountants[guild_id][steam_id].set_private(is_private)
                except KeyError:
                    pass

    def check_record(self, guild_id, steam_id):
        if not self.check_guild(guild_id):
            return False
        return steam_id in self.state["guilds"][guild_id]["data"]

    async def add_record(self, guild_id, steam_id, item):
        async with self.locks[guild_id]:
            if not self.check_guild(guild_id):
                raise ValueError("Missing guild.")
            if self.check_record(guild_id, steam_id):
                raise ValueError("Record is already present.")
            self.state["guilds"][guild_id]["data"][steam_id] = item
            channel_id = self.state["guilds"][guild_id]["channel"]
            is_private = self.state["guilds"][guild_id]["private"]
            accountant = Accountant(self.bot, channel_id, steam_id,
                                    item, is_private, self.make_counter(guild_id))
            await accountant.check_message()
            self.accountants[guild_id][steam_id] = accountant

    async def update_record(self, guild_id, steam_id, item):
        async with self.locks[guild_id]:
            if not self.check_record(guild_id, steam_id):
                raise ValueError("Missing record.")
            return await self.accountants[guild_id][steam_id].set_item(item)

    def get_record(self, guild_id, steam_id):
        if not self.check_record(guild_id, steam_id):
            raise ValueError("Missing record.")
        return deepcopy(self.state["guilds"][guild_id]["data"][steam_id])

    def get_ids(self, guild_id):
        if not self.check_guild(guild_id):
            raise ValueError("Missing guild.")
        return list(self.state["guilds"][guild_id]["data"].keys())

    async def compare_records(self, guild_id, response):
        if not self.check_guild(guild_id):
            raise ValueError("Missing guild.")
        for steam_id, item in response.items():
            if item is None:
                continue
            changed = False
            current_item = self.state["guilds"][guild_id]["data"][steam_id]
            if item["name"] != current_item["name"]:
                changed = True
                item["old_names"] = current_item["old_names"] + [item["name"], ]
            if item["url"] != current_item["url"]:
                changed = True
            if item["avatar"] != current_item["avatar"]:
                changed = True
            if await self.accountants[guild_id][steam_id].check_missing():
                changed = True
            if changed:
                await self.update_record(guild_id, steam_id, item)

    async def get_message(self, guild_id, steam_id):
        async with self.locks[guild_id]:
            if not self.check_record(guild_id, steam_id):
                raise ValueError("Missing record.")
            return await self.accountants[guild_id][steam_id].check_message()

    async def check_messages(self, guild_id):
        async with self.locks[guild_id]:
            if not self.check_guild(guild_id):
                raise ValueError("Missing guild.")
            order = sorted([(datetime.strptime(self.state["guilds"][guild_id]["data"][x]["last_date"], "%d/%m/%Y"), x)
                            for x in self.accountants[guild_id].keys()])
            for _, steam_id in order:
                try:
                    await self.accountants[guild_id][steam_id].check_message()
                except KeyError:
                    pass

    async def delete_record(self, guild_id, steam_id, ctx):
        async with self.locks[guild_id]:
            if not self.check_record(guild_id, steam_id):
                raise ValueError("Missing record.")
            try:
                with open("data/unblocked.json", "rb") as f:
                    unblocked = orjson.loads(f.read())
            except FileNotFoundError:
                unblocked = {}
            if guild_id not in unblocked:
                unblocked[guild_id] = []
            unblocked[guild_id].append(["{}#{}".format(ctx.author.name, ctx.author.discriminator),
                                        steam_id, self.state["guilds"][guild_id]["data"][steam_id]])
            with open("data/unblocked.json", "wb") as f:
                f.write(orjson.dumps(unblocked))
            await self.accountants[guild_id][steam_id].delete_item()
            del self.state["guilds"][guild_id]["data"][steam_id]
            del self.accountants[guild_id][steam_id]
