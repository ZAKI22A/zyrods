from utils import emojis

import discord
from discord.ext import commands
from utils.Tools import *
from utils.cv2_compat import embed_to_view

class Move(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_avatar(self, user):
        return user.display_avatar.url if user.display_avatar else user.default_avatar.url

    async def _send_move_log(self, guild, member, moderator, before_ch, after_ch):
        try:
            cog = self.bot.get_cog("Logging")
            if cog:
                banner = guild.banner.url if guild.banner else None
                from cogs.commands.logging import build_pro_embed
                embed = build_pro_embed(
                    guild=guild, user=member,
                    title="Member Moved", emoji="↗️",
                    description=f"> {member.mention} was moved between voice channels",
                    color=0x5865F2,
                    fields=[
                        ("👤 Member", f"{member.mention} `({member.id})`", True),
                        ("🛡️ Moderator", f"{moderator.mention}", True),
                        ("🔊 From", f"{before_ch.mention if before_ch else '`Unknown`'}", True),
                        ("🔊 To", f"{after_ch.mention}", True),
                    ],
                    banner_url=banner,
                    thumbnail_url=member.display_avatar.url
                )
                await cog.send_log(guild, "voice_move", embed)
        except Exception:
            pass

    @commands.command(
        name="move",
        help="Move a member to another voice channel",
        usage="move <member> [channel]",
        aliases=["m", "vmove"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(move_members=True)
    @commands.bot_has_permissions(move_members=True)
    async def move(self, ctx, member: discord.Member, channel: discord.VoiceChannel = None):
        # If no channel provided, move to author's channel
        if channel is None:
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
            else:
                embed = discord.Embed(description=f"{emojis.CROSSICON} Please provide a voice channel or join a voice channel.", color=self.color)
                embed.set_author(name="Missing Channel", icon_url=self.get_avatar(ctx.author))
                return await ctx.send(view=embed_to_view(embed))

        if member.voice is None or member.voice.channel is None:
            embed = discord.Embed(description=f"{emojis.CROSSICON} {member.mention} is not connected to any voice channel.", color=self.color)
            embed.set_author(name="Cannot Move", icon_url=self.get_avatar(member))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_avatar(ctx.author))
            return await ctx.send(view=embed_to_view(embed))

        if member.voice.channel.id == channel.id:
            embed = discord.Embed(description=f"{emojis.ICONS_WARNING} {member.mention} is already in {channel.mention}.", color=self.color)
            embed.set_author(name="Already There", icon_url=self.get_avatar(member))
            return await ctx.send(view=embed_to_view(embed))

        before = member.voice.channel
        try:
            await member.edit(voice_channel=channel, reason=f"Moved by {ctx.author}")
        except discord.Forbidden:
            embed = discord.Embed(description=f"{emojis.CROSSICON} I lack permission to move {member.mention}.", color=self.color)
            return await ctx.send(view=embed_to_view(embed))
        except discord.HTTPException as e:
            embed = discord.Embed(description=f"{emojis.CROSSICON} Failed to move: {e}", color=self.color)
            return await ctx.send(view=embed_to_view(embed))

        embed = discord.Embed(
            description=f"**Member:** {member.mention} (`{member.id}`)\n**From:** {before.mention}\n**To:** {channel.mention}\n**Moderator:** {ctx.author.mention}",
            color=self.color
        )
        embed.set_author(name=f"Moved {member.name}", icon_url=self.get_avatar(member))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_avatar(ctx.author))
        embed.timestamp = discord.utils.utcnow()
        await ctx.send(view=embed_to_view(embed))

        await self._send_move_log(ctx.guild, member, ctx.author, before, channel)

    @move.error
    async def move_error(self, ctx, error):
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(description=f"{emojis.CROSSICON} I don't have `Move Members` permission.", color=self.color)
            await ctx.send(view=embed_to_view(embed))
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(description=f"{emojis.CROSSICON} You need `Move Members` permission.", color=self.color)
            await ctx.send(view=embed_to_view(embed))
        else:
            embed = discord.Embed(description=f"{emojis.CROSSICON} Error: {str(error)}", color=self.color)
            await ctx.send(view=embed_to_view(embed))
