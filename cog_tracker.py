from asyncio import sleep
import orjson

from core.steam_api import SteamAPI
from core.utils import CommandInputError
from discord import utils, Game
from discord.errors import NotFound
from discord.ext import tasks, commands

from core.database import Database
from core.message_constructor import MessageConstructor as MC


class Tracker(commands.Cog):
    """Steam accounts tracking Cog"""

    def __init__(self, bot, steam_key):
        self.bot = bot
        self.api = SteamAPI(steam_key)

        self.database = Database(self.bot)

        self.current_guild_tracker = -1
        self.current_guild_updater = -2
        self.guilds = list(self.database.accountants.keys())
        try:
            with open("data/permissions.json", "rb") as f:
                self.permissions = orjson.loads(f.read())
        except FileNotFoundError:
            self.permissions = {guild_id: {} for guild_id in self.guilds}
            self.save_permissions()

        self.status = 1

    async def set_status_busy(self):
        self.status += 1
        game = Game("?help | 🔄")
        await self.bot.change_presence(activity=game)

    async def set_status_done(self):
        self.status -= 1
        if self.status:
            return
        try:
            count = self.api.get_player_count()
        except:
            count = "?"
        suffix = " | {}🧍".format(count)
        game = Game("?help | ✅" + suffix)
        await self.bot.change_presence(activity=game)

    async def update_status(self):
        pass


    def save_permissions(self):
        with open("data/permissions.json", "wb") as f:
            f.write(orjson.dumps(self.permissions))

    @commands.Cog.listener()
    async def on_ready(self):
        self.tracker.start()
        self.updater.start()
        self.saver.start()
        self.backuper.start()
        await self.set_status_done()

    def cog_unload(self):
        self.tracker.cancel()
        self.updater.cancel()
        self.saver.cancel()
        self.backuper.cancel()

    @tasks.loop(seconds=30)
    async def tracker(self):
        try:
            await self.set_status_busy()
            if l := len(self.guilds):
                self.current_guild_tracker = (
                    self.current_guild_tracker + 1) % l
                guild_id = self.guilds[self.current_guild_tracker]
                steam_ids = self.database.get_ids(guild_id)
                response = self.api.get_summaries(steam_ids)
                await self.database.compare_records(guild_id, response)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @tracker.after_loop
    async def exit_tracker(self):
        self.database.save_state()
        self.save_permissions()

    @tasks.loop(hours=3)
    async def updater(self):
        try:
            await self.set_status_busy()
            if self.current_guild_updater == -2:
                self.current_guild_updater = -1
                await self.set_status_done()
                return
            if l := len(self.guilds):
                self.current_guild_updater = (
                    self.current_guild_updater + 1) % l
                guild_id = self.guilds[self.current_guild_updater]
                await self.database.check_messages(guild_id)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @tasks.loop(minutes=1)
    async def saver(self):
        self.database.save_state()

    @tasks.loop(hours=12)
    async def backuper(self):
        self.database.backup_state()

    async def respond(self, ctx, timer=15, **kvargs):
        reply = await ctx.message.reply(**kvargs)
        await sleep(timer)
        try:
            await reply.delete()
        except NotFound:
            pass
        try:
            await ctx.message.delete()
        except NotFound:
            pass

    async def get_level(self, ctx):
        guild_id = str(ctx.guild.id)
        if await self.bot.is_owner(ctx.author):
            return 5
        if ctx.guild.owner_id == ctx.author.id:
            return 5
        if not self.database.check_guild(guild_id):
            return 0
        member_level = 0
        for role in ctx.author.roles:
            role_level = self.permissions[guild_id].get(str(role.id), 0)
            member_level = max(role_level, member_level)
        return member_level

    async def level_checker(self, level, ctx):
        if await self.get_level(ctx) < level:
            error_arg = f"You do not have LVL{level} permissions."
            raise CommandInputError(error_arg)
        return True

    @commands.command(name="check")
    @commands.guild_only()
    async def check(self, ctx, user):
        """Check if user is blocked"""

        await self.level_checker(1, ctx)
        guild_id = str(ctx.guild.id)
        if not self.database.check_guild(guild_id):
            raise CommandInputError("Missing guild.")
        steam_id = self.api.get_id(user)
        if not steam_id:
            raise CommandInputError("Invalid profile.")
        try:
            message_url = await self.database.get_message(guild_id, steam_id)
        except ValueError:
            message_body = MC.basic("User is not tracked.")
            await self.respond(ctx, **message_body)
        else:
            if not message_url:
                error_arg = "User is tracked. Could not resolve message."
                raise CommandInputError(error_arg)
            message_body = MC.check(message_url)
            await self.respond(ctx, **message_body)

    @commands.command(name="block")
    @commands.guild_only()
    async def block(self, ctx, user):
        """Block user"""

        await self.level_checker(2, ctx)
        guild_id = str(ctx.guild.id)
        if not self.database.check_guild(guild_id):
            raise CommandInputError("Missing guild.")
        steam_id = self.api.get_id(user)
        if not steam_id:
            raise CommandInputError("Invalid profile.")
        item = self.api.get_summaries([steam_id, ])[steam_id]
        pass_in = [self.database, guild_id, steam_id, ctx, item]
        message_body = MC.block(*pass_in)
        reply = await ctx.send(**message_body)
        await message_body["view"].set_reply(reply)
        await sleep(30)
        try:
            await reply.delete()
        except NotFound:
            pass
        try:
            await ctx.message.delete()
        except NotFound:
            pass

    @commands.command(name="edit")
    @commands.guild_only()
    async def edit(self, ctx, user, *, args=""):
        """Edit user record"""

        args = list(filter(None, args.split(";")))
        await self.level_checker(3, ctx)
        if len(args):
            await self.level_checker(4, ctx)
        guild_id = str(ctx.guild.id)
        if not self.database.check_guild(guild_id):
            raise CommandInputError("Missing guild.")
        steam_id = self.api.get_id(user)
        if not self.database.check_record(guild_id, steam_id):
            raise CommandInputError("Missing record.")
        if not steam_id:
            raise CommandInputError("Invalid profile.")
        f = await self.get_level(ctx) > 3
        if len(args):
            args = {k.lower(): v for k, v in map(lambda x: x.split(":"), args)}
        else:
            args = {}
        for key in list(args.keys()):
            if key not in ["initiator", "encounters", "date"]:
                raise CommandInputError(f"Wrong argument: {key}.")
            if key == "encounters":
                if not args[key].isnumeric():
                    raise CommandInputError(
                        "Encounters parameter should be an integer.")
                args[key] = int(args[key])
        pass_in = [self.database, guild_id, steam_id, ctx, f, args]
        message_body = MC.edit(*pass_in)
        reply = await ctx.send(**message_body)
        await message_body["view"].set_reply(reply)
        await sleep(30)
        try:
            await reply.delete()
        except NotFound:
            pass
        try:
            await ctx.message.delete()
        except NotFound:
            pass

    @commands.command(name="restore")
    @commands.guild_only()
    async def restore(self, ctx):
        """Restore missing messages now"""
        try:
            await self.level_checker(4, ctx)
            await self.set_status_busy()
            guild_id = str(ctx.guild.id)
            if not self.database.check_guild(guild_id):
                raise CommandInputError("Missing guild.")
            await self.database.check_messages(guild_id)
            message_body = MC.basic("Done!")
            await self.respond(ctx, **message_body)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @commands.command(name="set-channel")
    @commands.guild_only()
    async def set_channel(self, ctx, channel_name):
        """Define target channel"""
        try:
            await self.level_checker(5, ctx)
            await self.set_status_busy()
            guild_id = str(ctx.guild.id)
            channel = utils.get(ctx.guild.text_channels, name=channel_name)
            if not channel:
                raise CommandInputError("Invalid channel.")
            channel_id = channel.id
            if not self.database.check_guild(guild_id):
                self.database.add_guild(guild_id, channel_id)
                self.guilds.append(guild_id)
                self.permissions[guild_id] = {}
                self.save_permissions()
            else:
                await self.database.set_channel(guild_id, channel_id)
            message_body = MC.basic("Done!")
            await self.respond(ctx, **message_body)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @commands.command(name="set-private")
    @commands.guild_only()
    async def set_private(self, ctx):
        """Set to private mode"""
        try:
            await self.level_checker(5, ctx)
            await self.set_status_busy()
            guild_id = str(ctx.guild.id)
            if not self.database.check_guild(guild_id):
                raise CommandInputError("Missing guild.")
            await self.database.set_private(guild_id, True)
            message_body = MC.basic("Done!")
            await self.respond(ctx, **message_body)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @commands.command(name="set-public")
    @commands.guild_only()
    async def set_public(self, ctx):
        """Set to public mode"""
        try:
            await self.level_checker(5, ctx)
            await self.set_status_busy()
            guild_id = str(ctx.guild.id)
            if not self.database.check_guild(guild_id):
                raise CommandInputError("Missing guild.")
            await self.database.set_private(guild_id, False)
            message_body = MC.basic("Done!")
            await self.respond(ctx, **message_body)
        except:
            pass
        try:
            await self.set_status_done()
        except:
            pass

    @commands.command(name="set-permissions")
    @commands.guild_only()
    async def set_permissions(self, ctx, level, *, roles):
        """Set command permissions"""

        await self.level_checker(5, ctx)
        guild_id = str(ctx.guild.id)
        if not self.database.check_guild(guild_id):
            raise CommandInputError("Missing guild.")
        if not level.isnumeric() or not (0 <= int(level) <= 5):
            raise CommandInputError("Level should be an integer from 0 to 5.")
        level = int(level)
        roles = roles.split(";")
        role_ids = []
        for role_name in roles:
            role = utils.get(ctx.guild.roles, name=role_name)
            if not role:
                raise CommandInputError(f"Invalid role name: {role_name}.")
            role_ids.append(str(role.id))
        for role_id in role_ids:
            self.permissions[guild_id][role_id] = level
        self.save_permissions()
        message_body = MC.basic("Done!")
        await self.respond(ctx, **message_body)

    @commands.command(name="get-permissions")
    @commands.guild_only()
    async def get_permissions(self, ctx):
        """Display command permissions"""

        await self.level_checker(5, ctx)
        guild_id = str(ctx.guild.id)
        if not self.database.check_guild(guild_id):
            raise CommandInputError("Missing guild.")
        reversed_permissions = [[] for i in range(6)]
        for role_id, level in list(self.permissions[guild_id].items()):
            try:
                role_name = ctx.guild.get_role(int(role_id)).name
            except AttributeError:
                pass
            reversed_permissions[level].append(role_name)
        message_body = MC.permissions(reversed_permissions)
        await self.respond(ctx, **message_body)

    @commands.command(name="help")
    async def help(self, ctx):
        """Send help message"""

        message_body = MC.helper(await self.get_level(ctx))
        await self.respond(ctx, timer=60, **message_body)
