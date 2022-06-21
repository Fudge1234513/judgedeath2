from asyncio import Lock
import warnings

from discord import NotFound, Forbidden

from core.message_constructor import MessageConstructor as MC
from core.utils import Placeholder


class Accountant:
    def __init__(self, bot, channel_id, steam_id, item, is_private, counter):
        self.bot = bot
        self.channel_id = channel_id
        self.is_private = is_private

        self.steam_id = steam_id
        self.item = item

        self.channel = Placeholder()
        self.message = None
        self.lock = Lock()
        self.counter = counter
        self.is_waiting = False

    async def _setup(self):
        channel = self.bot.get_channel(self.channel_id)
        try:
            self.message = await channel.fetch_message(self.item["message"])
        except (AttributeError, NotFound, Forbidden) as e:
            if isinstance(e, Forbidden):
                warnings.warn("Not allowed to read messages."
                              "Could not verify initial message!")
            else:
                self.item["message"] = 0
        self.channel = channel
        self.is_waiting = False

    async def check_missing(self):
        async with self.lock:
            if self.message or self.is_waiting or isinstance(self.channel, Placeholder):
                return False
            return True

    async def check_message(self):
        async with self.lock:
            if isinstance(self.channel, Placeholder):
                await self._setup()
                if self.message:
                    return self.message.jump_url
            try:
                self.message = await self.channel.fetch_message(self.item["message"])
            except (AttributeError, NotFound, Forbidden) as e:
                if isinstance(e, Forbidden):
                    warnings.warn("Not allowed to read messages."
                                  "Could not verify existence!")
                    self.is_waiting = True
                    return
                elif isinstance(e, AttributeError):
                    self.is_waiting = False
                    return
                elif isinstance(e, NotFound):
                    self.item["message"] = 0
                else:
                    self.is_waiting = False
                    raise e
            else:
                self.is_waiting = False
                return self.message.jump_url
            i = self.counter()
            message_body = MC.card(self.steam_id, self.item,
                                   self.is_private, i)
            try:
                self.message = await self.channel.send(**message_body)
            except (AttributeError, Forbidden) as e:
                if isinstance(e, Forbidden):
                    warnings.warn("Not allowed to send messages."
                                  "Could not send new!")
                self.message = None
                self.is_waiting = True
            else:
                self.item["message"] = self.message.id
                self.is_waiting = False
                return self.message.jump_url

    async def set_item(self, item):
        async with self.lock:
            if isinstance(self.channel, Placeholder):
                await self._setup()
            for k in item:
                self.item[k] = item[k]
            try:
                await self.message.delete()
            except (AttributeError, NotFound) as e:
                if isinstance(e, NotFound):
                    self.item["message"] = 0
            self.message = None
            self.is_waiting = True
        await self.check_message()

    async def set_channel(self, channel_id):
        async with self.lock:
            if isinstance(self.channel, Placeholder):
                await self._setup()
            self.channel_id = channel_id
            self.channel = self.bot.get_channel(self.channel_id)
            try:
                await self.message.delete()
            except (AttributeError, NotFound):
                pass
            self.message = None
            self.is_waiting = True
            self.item["message"] = 0
        await self.check_message()

    async def set_private(self, is_private):
        async with self.lock:
            if self.is_private == is_private:
                return
            if isinstance(self.channel, Placeholder):
                await self._setup()
            self.is_private = is_private
            try:
                await self.message.delete()
            except (AttributeError, NotFound):
                pass
            self.message = None
            self.is_waiting = True
            self.item["message"] = 0
        await self.check_message()

    async def delete_item(self):
        async with self.lock:
            if isinstance(self.channel, Placeholder):
                await self._setup()
            try:
                await self.message.delete()
            except (AttributeError, NotFound):
                pass
