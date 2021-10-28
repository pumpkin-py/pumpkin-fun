import asyncio
import dhash
import time
from io import BytesIO
from PIL import Image
from typing import Optional, List, Dict

import discord
from discord.ext import commands

from core import utils, i18n, logger, check, TranslationContext
from .database import HashChannel, ImageHash

_ = i18n.Translator("modules/fun").translate
guild_log = logger.Guild.logger()
bot_log = logger.Bot.logger()

LIMIT_FULL = 3
LIMIT_HARD = 7
LIMIT_SOFT = 14

NOT_DUPE_LIMIT = 5

MAX_ATTACHMENT_SIZE = 8000


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

    @commands.check(check.acl)
    @commands.group()
    async def repost(self, ctx):
        """Scan for reposts"""
        await utils.Discord.send_help(ctx)

    @commands.check(check.acl)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.bot_has_permissions(read_message_history=True)
    @dhash.command(name="history")
    async def repost_history(self, ctx, limit: int):
        """Scan current channel for images and save them as hashes.
        limit: How many messages should be scanned. Negative to scan all.
        """
        if limit < 0:
            limit = None

        async with ctx.typing():
            messages = await ctx.channel.history(limit=limit).flatten()

        status = await ctx.send(
            _(ctx, "**LOADING**")
            + "\n"
            + _(ctx, "Downloaded **count** messages.").format(count=len(messages))
        )

        await asyncio.sleep(1)

        ctr_nofile: int = 0
        ctr_hashes: int = 0
        now = time.time()
        for i, message in enumerate(messages, 1):
            if i % 20 == 0:
                await status.edit(
                    content=(
                        _(ctx, "**SCANNING**")
                        + "\n"
                        + _(
                            ctx,
                            "Processed **{count}** out of **{total}** messages {percent} %).",
                        )
                        + "\n"
                        + _(ctx, "Calculated **((hashes))** hashes.")
                    ).format(
                        count=i,
                        total=len(messages),
                        percent="{:.1f}".format(i / len(messages) * 100),
                        hashes=ctr_hashes,
                    )
                )

            if not len(message.attachments):
                ctr_nofile += 1
                continue

            hashes = [x async for x in self._save_hashes(message)]
            ctr_hashes += len(hashes)

        await status.edit(
            content=(
                _(ctx, "**COMPLETED**")
                + "\n"
                + _(ctx, "Processed **{messages}** messages.")
                + "\n"
                + _(
                    ctx,
                    "calculated **{hashes}** image hashes in **{seconds}** seconds.",
                )
            ).format(
                messages=len(messages),
                hashes=ctr_hashes,
                seconds="{:.1f}".format(time.time() - now),
            )
        )

    @commands.check(check.acl)
    @dhash.command(name="compare", aliases=["messages"])
    async def scan_compare(self, ctx, messages: commands.Greedy[discord.Message]):
        """Display hashes of given messages.
        messages: Space separated list of messages.
        """
        text = []

        for message in messages:
            db_images = ImageHash.get_by_message(message.guild.id, message.id)
            if not len(db_images):
                continue

            text.append(
                _(ctx, "Message **`{message_id}`**").format(message_id=message.id)
            )
            for db_image in db_images:
                text.append(
                    "   " + _(ctx, "> `{hash}`").format(hash=db_image.dhash[2:])
                )
            text.append("")

        if not len(text):
            return await ctx.send(_(ctx, "Message has no associtated hashes"))

        await ctx.send("\n".join(text))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self._in_repost_channel(message):
            await self._check_message(message)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        channel = HashChannel.get(payload.guild_id, payload.channel_id)
        if channel:
            ImageHash.delete_by_message(payload.guild_id, payload.message_id)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not self._in_repost_channel(message):
            return

        # try to detect and delete repost embed
        messages = await message.channel.history(
            after=message, limit=3, oldest_first=True
        ).flatten()
        for report in messages:
            if not report.author.bot:
                continue
            if len(report.embeds) != 1 or type(report.embeds[0].footer.text) != str:
                continue
            if str(message.id) != report.embeds[0].footer.text.split(" | ")[1]:
                continue

            try:
                await report.delete()
            except discord.errors.HTTPException as exc:
                await bot_log.error(
                    "Could not delete repost embed {msg_id} at guild {guild}".format(
                        msg_id=message.id, guild=message.guild.id
                    ),
                    exception=exc,
                )
            break

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        """Handle 'This is a repost' report.
        The footer contains reposter's user ID and repost message id.
        """
        if not self._in_repost_channel(reaction.message):
            return
        if user.bot:
            return
        if not reaction.message.author.bot:
            return
        emoji = str(reaction.emoji)
        if emoji != "❎":
            return

        try:
            repost_message_id = int(
                reaction.message.embeds[0].footer.text.split(" | ")[1]
            )
            repost_message = await reaction.message.channel.fetch_message(
                repost_message_id
            )
        except discord.errors.HTTPException as exc:
            return await bot_log.error(
                "Could not find repost message {msg_id} at guild {guild}".format(
                    msg_id=reaction.message.id, guild=reaction.guild.id
                ),
                exception=exc,
            )

        for report_reaction in reaction.message.reactions:
            if str(report_reaction) != "❎":
                continue

            if (
                emoji == "❎"
                and str(report_reaction) == "❎"
                and report_reaction.count > NOT_DUPE_LIMIT
            ):
                # remove bot's reaction, it is not a repost
                try:
                    await repost_message.remove_reaction("♻️", self.bot.user)
                    await repost_message.remove_reaction("🤷🏻", self.bot.user)
                    await repost_message.remove_reaction("🤔", self.bot.user)
                except discord.errors.HTTPException as exc:
                    return await bot_log.error(
                        "Could not delete bot reactions from message {msg_id} at guild {guild}".format(
                            msg_id=reaction.message.id, guild=reaction.guild.id
                        ),
                        exception=exc,
                    )
                return await utils.Discord.delete(reaction.message)

    # Helper functions

    async def _save_hashes(self, message: discord.Message):
        for attachment in message.attachments:
            if attachment.size > MAX_ATTACHMENT_SIZE * 1024:
                continue

            extension = attachment.filename.split(".")[-1].lower()
            if extension not in ("jpg", "jpeg", "png", "webp", "gif"):
                continue

            fp = BytesIO()

            await attachment.save(fp)
            try:
                image = Image.open(fp)
            except OSError:
                continue

            h = dhash.dhash_int(image)
            ImageHash.add(
                guild_id=message.guild.id,
                channel_id=message.channel.id,
                message_id=message.id,
                attachment_id=attachment.id,
                hash=str(hex(h)),
            )
            yield h

    async def _check_message(self, message: discord.Message):
        """Check if message contains duplicate image."""
        image_hashes = [x async for x in self._save_hashes(message)]

        duplicates = {}
        all_images = None

        for image_hash in image_hashes:
            # try to look up hash directly
            images = ImageHash.get_hash(
                message.guild.id, message.channel.id, str(hex(image_hash))
            )
            duplicated = False

            for image in images:
                # skip current message
                if image.message_id == message.id:
                    continue
                # add to duplicates
                duplicates[image] = 0
                duplicated = True
                break

            # move on to the next hash
            if duplicated:
                continue

            # full match not found, iterate over whole database
            if all_images is None:
                all_images = ImageHash.get_all(message.guild.id, message.channel.id)

            minimal_distance = 128
            duplicate = None
            for image in all_images:
                # skip current image
                if image.message_id == message.id:
                    continue

                # do the comparison
                db_image_hash = int(image.dhash, 16)
                distance = dhash.get_num_bits_different(db_image_hash, image_hash)
                if distance < minimal_distance:
                    duplicate = image
                    minimal_distance = distance

            if minimal_distance < LIMIT_SOFT:
                duplicates[duplicate] = minimal_distance

        for image_hash, distance in duplicates.items():
            await self._report_duplicate(message, image_hash, distance)

    async def _report_duplicate(
        self, message: discord.Message, original: ImageHash, distance: int
    ):
        """Send report.
        message: The new message containing attachment repost.
        original: The original attachment.
        distance: Hamming distance between the original and repost.
        """
        ctx = TranslationContext(message.guild.id, message.author.id)

        if distance <= LIMIT_FULL:
            level = _(ctx, "**♻️ This is repost!**")
            await message.add_reaction("♻️")
        elif distance <= LIMIT_HARD:
            level = _(ctx, "**♻️ This is probably repost!**")
            await message.add_reaction("🤔")
        else:
            level = _(ctx, "🤷🏻 This could be repost.")
            await message.add_reaction("🤷🏻")

        similarity = "{:.1f} %".format((1 - distance / 128) * 100)
        timestamp = utils.Time.id_to_datetime(original.attachment_id).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        try:
            original_channel = message.guild.get_channel(original.channel_id)
            original_message = await original_channel.fetch_message(original.message_id)
            author = discord.utils.escape_markdown(original_message.author.display_name)
            link = f"[**{author}**, {timestamp}]({original_message.jump_url})"
        except discord.errors.NotFound:
            link = "404 " + emote.sad

        description = _(ctx, "{name}, matching **{similarity}**!").format(
            name=discord.utils.escape_markdown(message.author.display_name),
            similarity=similarity,
        )

        embed = utils.Discord.create_embed(title=level, description=description)

        embed.add_field(
            name=_(ctx, "Original"),
            value=link,
            inline=False,
        )

        embed.add_field(
            name=_(ctx, "Hint"),
            value=_(
                ctx,
                " _If image is repost, give it ♻️ reaction. If it's not, click here on ❎ and when we reach {limit} reactions this message will be deleted._",
            ).format(
                limit=NOT_DUPE_LIMIT,
            ),
            inline=False,
        )
        embed.set_footer(text=f"{message.author.id} | {message.id}")
        report = await message.reply(embed=embed)
        await report.add_reaction("❎")

    def _in_repost_channel(self, message: discord.Message) -> bool:
        channel = HashChannel.get(message.guild.id, message.channel.id)
        if not channel:
            return False
        if message.attachments is None or not len(message.attachments):
            return False
        if message.author.bot:
            return False
        return True


def setup(bot) -> None:
    bot.add_cog(Dhash(bot))
