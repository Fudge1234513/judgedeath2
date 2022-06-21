from asyncio import sleep
from datetime import datetime, timezone, timedelta

from discord.errors import NotFound
from discord.ext import commands

from core.message_constructor import MessageConstructor as MC


class Overseer(commands.Cog):
    """Overseer Cog"""

    def __init__(self, bot):
        self.bot = bot
        self.tzinfo = timezone(timedelta(hours=3))

    async def respond(self, ctx, **kvargs):
        reply = await ctx.message.reply(**kvargs)
        await sleep(15)
        try:
            await reply.delete()
        except NotFound:
            pass
        try:
            await ctx.message.delete()
        except NotFound:
            pass

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandInvokeError):
            i = str(error).find("CommandInputError:")
            if i != -1:
                message_body = MC.error(str(error)[i + 18:])
                await self.respond(ctx, **message_body)
            else:
                raise error
        elif isinstance(error, commands.MissingRequiredArgument):
            message_body = MC.error("Missing arguments.")
            await self.respond(ctx, **message_body)

    @commands.Cog.listener()
    async def on_command(self, ctx):
        time = datetime.now(self.tzinfo).strftime("%Y-%m-%d-%H:%M:%S")
        guild = str(ctx.guild.id)
        author = f"{ctx.author.name}#{ctx.author.discriminator}"
        command = ctx.command.qualified_name
        params = ", ".join(ctx.args[2:])
        with open("data/commands.log", "a") as f:
            f.write(f"{time} {guild} {author} {command} {params}\n")
