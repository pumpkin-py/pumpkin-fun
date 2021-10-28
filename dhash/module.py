import aiohttp
import random
import re
from typing import Optional, List, Dict

import discord
from discord.ext import commands

from core import utils, i18n, logger, check
from .database import HashChannel

_ = i18n.Translator("modules/fun").translate
guild_log = logger.Guild.logger()

class Dhash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.guild_only()
    @commands.check(check.acl)
    @commands.group(name="dhash")
    async def dhash(self, ctx):
        await utils.Discord.send_help(ctx)

    @commands.check(check.acl)
    @dhash.command(name="add")
    async def dhash_add(self, ctx, channel: discord.TextChannel):
        hash_channel = HashChannel.get(ctx.guild.id, channel.id)
        if hash_channel:
            await ctx.send(
                _(
                    ctx,
                    "{channel} is already hash channel.",
                ).format(channel=channel.mention)
            )
            return

        hash_channel = HashChannel.add(ctx.guild.id, channel.id)
        await ctx.send(
            _(
                ctx,
                "Channel {channel} added as hash channel.",
            ).format(channel=channel.mention)
        )
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Channel #{channel.name} set as hash channel.",
        )

    @commands.check(check.acl)
    @dhash.command(name="list")
    async def dhash_list(self, ctx):
        hash_channels = HashChannel.get_all(ctx.guild.id)
        if not hash_channels:
            await ctx.reply(_(ctx, "This server has no hash channels."))
            return

        channels = [ctx.guild.get_channel(c.channel_id) for c in hash_channels]
        column_name_width: int = max([len(c.name) for c in channels if c])

        result = []
        for hash_channel, channel in zip(hash_channels, channels):
            name = getattr(channel, "name", "???")
            line = f"#{name:<{column_name_width}} {hash_channel.channel_id}"
            result.append(line)

        await ctx.reply("```" + "\n".join(result) + "```")

    @commands.check(check.acl)
    @dhash.command(name="remove", aliases=["rem"])
    async def dhash_remove(self, ctx, channel: discord.TextChannel):
        if HashChannel.remove(ctx.guild.id, channel.id):
            message = _(ctx, "Hash channel {channel} removed.")
        else:
            message = _(ctx, "{channel} is not hash channel.")
        await ctx.reply(message.format(channel=channel.mention))
        await guild_log.info(
            ctx.author,
            ctx.channel,
            f"Channel #{channel.name} is no longer a hash channel.",
        )


def setup(bot) -> None:
    bot.add_cog(Dhash(bot))
