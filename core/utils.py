from datetime import datetime, timezone, timedelta

from discord import ButtonStyle
from discord.errors import NotFound
from discord.ui import View, Button

REASONS = [("Griefer", 2),
           ("Cheater", 2),
           ("Exploiter", 1),
           ("Hate speech", 1),
           ("Toxic", 0),
           ("Leaver", 0)]

COLORS = [0xffbe3f, 0xff7f3f, 0xff3f3f]


def escape_characters(string, characters=r"\*-_~`>#.[](){}+!?%|&$;"):
    for c in characters:
        string = string.replace(c, "\\" + c)
    return string


class CommandInputError(ValueError):
    pass


class Placeholder:
    pass


class BlockView(View):
    def __init__(self, database, guild_id, steam_id, ctx, item):
        super().__init__(timeout=40)
        self.tzinfo = timezone(timedelta(hours=3))
        self.database = database
        self.guild_id = guild_id
        self.steam_id = steam_id
        self.ctx = ctx
        self.reply = None

        self.count = 0
        self.reason_checks = []

        self.new_date = datetime.now(self.tzinfo).strftime("%d/%m/%Y")
        if self.database.check_record(guild_id, steam_id):
            self.item = self.database.get_record(guild_id, steam_id)
        else:
            self.item = {"message": 0,
                         "name": item["name"],
                         "old_names": [item["name"], ],
                         "initiator": f"{ctx.author.name}#{ctx.author.discriminator}",
                         "encounters": 0,
                         "date": self.new_date,
                         "last_date": "",
                         "reasons": [],
                         "url": item["url"],
                         "avatar": item["avatar"]}

        async def confirm_callback(interaction):
            self.stop()
            try:
                await self.reply.delete()
            except NotFound:
                pass
            try:
                await self.ctx.message.delete()
            except NotFound:
                pass
            if self.count:
                self.item["reasons"] = []
                for i, check in enumerate(self.reason_checks):
                    if check:
                        self.item["reasons"].append(REASONS[i][0])
                self.item["encounters"] += 1
                self.item["last_date"] = self.new_date
                if self.database.check_record(self.guild_id, self.steam_id):
                    await self.database.update_record(self.guild_id, self.steam_id, self.item)
                else:
                    await self.database.add_record(self.guild_id, self.steam_id, self.item)

        self.confirm_button = Button(label="Confirm", disabled=True,
                                     style=ButtonStyle.green, row=2)
        self.confirm_button.callback = confirm_callback

        async def cancel_callback(interaction):
            self.stop()
            try:
                await self.reply.delete()
            except NotFound:
                pass
            try:
                await self.ctx.message.delete()
            except NotFound:
                pass

        self.cancel_button = Button(label="Cancel", disabled=True,
                                    style=ButtonStyle.red, row=2)
        self.cancel_button.callback = cancel_callback

        def make_reason_callback(button, i):
            async def reason_callback(interaction):
                if button.style == ButtonStyle.grey:
                    button.style = ButtonStyle.blurple
                    self.reason_checks[i] = True
                    self.count += 1
                elif button.style == ButtonStyle.blurple:
                    button.style = ButtonStyle.grey
                    self.reason_checks[i] = False
                    self.count -= 1
                if self.count and self.reply:
                    self.confirm_button.disabled = False
                else:
                    self.confirm_button.disabled = True
                await self.reply.edit(view=self)
            return reason_callback

        for i, [reason, _] in enumerate(REASONS):
            self.reason_checks.append(reason in self.item["reasons"])
            if reason in self.item["reasons"]:
                self.count += 1
                button = Button(label=REASONS[i][0], disabled=True,
                                style=ButtonStyle.blurple, row=i // 3)
            else:
                button = Button(label=REASONS[i][0],
                                style=ButtonStyle.grey, row=i // 3)
                button.callback = make_reason_callback(button, i)
            self.add_item(button)
        self.add_item(self.confirm_button)
        self.add_item(self.cancel_button)

    async def set_reply(self, reply):
        self.reply = reply
        if self.count:
            self.confirm_button.disabled = False
        self.cancel_button.disabled = False
        await self.reply.edit(view=self)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.message.author


class EditView(View):
    def __init__(self, database, guild_id, steam_id, ctx, f, args):
        super().__init__(timeout=40)
        self.database = database
        self.guild_id = guild_id
        self.steam_id = steam_id
        self.ctx = ctx
        self.f = f
        self.args = args
        self.reply = None

        self.count = 0
        self.reason_checks = []

        self.item = self.database.get_record(guild_id, steam_id)

        async def confirm_callback(interaction):
            self.stop()
            try:
                await self.reply.delete()
            except NotFound:
                pass
            try:
                await self.ctx.message.delete()
            except NotFound:
                pass
            if self.count:
                self.item["reasons"] = []
                for i, check in enumerate(self.reason_checks):
                    if check:
                        self.item["reasons"].append(REASONS[i][0])
                for k, v in self.args.items():
                    self.item[k] = v
                await self.database.update_record(self.guild_id, self.steam_id, self.item)
            elif self.f:
                await self.database.delete_record(self.guild_id, self.steam_id, self.ctx)
            else:
                return

        self.confirm_button = Button(label="Confirm", disabled=True,
                                     style=ButtonStyle.green, row=2)
        self.confirm_button.callback = confirm_callback

        async def cancel_callback(interaction):
            self.stop()
            try:
                await self.reply.delete()
            except NotFound:
                pass
            try:
                await self.ctx.message.delete()
            except NotFound:
                pass

        self.cancel_button = Button(label="Cancel", disabled=True,
                                    style=ButtonStyle.red, row=2)
        self.cancel_button.callback = cancel_callback

        def make_reason_callback(button, i):
            async def reason_callback(interaction):
                if button.style == ButtonStyle.grey:
                    button.style = ButtonStyle.blurple
                    self.reason_checks[i] = True
                    self.count += 1
                elif button.style == ButtonStyle.blurple:
                    button.style = ButtonStyle.grey
                    self.reason_checks[i] = False
                    self.count -= 1
                if (self.count or self.f) and self.reply:
                    self.confirm_button.disabled = False
                else:
                    self.confirm_button.disabled = True
                await self.reply.edit(view=self)
            return reason_callback

        for i, [reason, _] in enumerate(REASONS):
            self.reason_checks.append(reason in self.item["reasons"])
            if reason in self.item["reasons"]:
                self.count += 1
                button = Button(label=REASONS[i][0],
                                style=ButtonStyle.blurple, row=i // 3)
            else:
                button = Button(label=REASONS[i][0],
                                style=ButtonStyle.grey, row=i // 3)
            button.callback = make_reason_callback(button, i)
            self.add_item(button)
        self.add_item(self.confirm_button)
        self.add_item(self.cancel_button)

    async def set_reply(self, reply):
        self.reply = reply
        if self.count or self.f:
            self.confirm_button.disabled = False
        self.cancel_button.disabled = False
        await self.reply.edit(view=self)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.message.author
