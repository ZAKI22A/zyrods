from utils import emojis

import discord
from discord.ext import commands
from discord import ui
import asyncio
from utils.Tools import *
from utils.cv2_compat import embed_to_view, sync_panel_message

DEFAULT_MUTE_DURATION = 300  # 5 minutes
DEFAULT_MUTE_TEXT = "5 minutes"
MUTED_ROLE_NAME = "Zyro Muted"

class ServerMuteView(ui.View):
    def __init__(self, user, author, role):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.role = role
        self.message = None
        self.color = discord.Color.from_rgb(0, 0, 0)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await sync_panel_message(self)

    @ui.button(label="Unmute", style=discord.ButtonStyle.success)
    async def unmute(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = guild.get_member(self.user.id)
        if not member:
            await interaction.response.send_message("Member not found.", ephemeral=True)
            return
        role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
        if role not in member.roles and (not member.voice or not member.voice.mute):
            await interaction.response.send_message(f"{member.mention} is not muted.", ephemeral=True)
            return
        try:
            if role and role in member.roles:
                await member.remove_roles(role, reason=f"Unmuted by {interaction.user}")
            if member.voice and member.voice.mute:
                await member.edit(mute=False, reason=f"Unmuted by {interaction.user}")
        except discord.Forbidden:
            await interaction.response.send_message("I lack permission to unmute.", ephemeral=True)
            return
        embed = discord.Embed(description=f"**Target:** {member.mention} (`{member.id}`)\n**Moderator:** {interaction.user.mention}", color=0x000000)
        embed.set_author(name=f"Successfully Unmuted {member.name}", icon_url=member.display_avatar.url if member.display_avatar else member.default_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else interaction.user.default_avatar.url)
        embed.timestamp = discord.utils.utcnow()
        await interaction.response.edit_message(view=embed_to_view(embed, view=self))
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except Exception:
            pass

    @ui.button(style=discord.ButtonStyle.gray, emoji=f"{emojis.DELETE}")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class Mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.display_avatar.url if user.display_avatar else user.default_avatar.url

    async def get_or_create_muted_role(self, guild: discord.Guild) -> discord.Role:
        role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
        if role:
            return role
        # Create Zyro Muted role - professional
        try:
            role = await guild.create_role(
                name=MUTED_ROLE_NAME,
                color=discord.Color.from_rgb(99, 102, 107),
                reason="Zyro mute system - auto created",
                permissions=discord.Permissions.none()
            )
            # Place role just below bot's top role
            try:
                await guild.edit_role_positions(positions={role: guild.me.top_role.position - 1})
            except Exception:
                pass
            # Voice: deny speak (mic) only - member can still join voice channels
            # (do NOT set connect=False, and NO timeout is applied)
            for channel in guild.channels:
                try:
                    if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                        await channel.set_permissions(role, speak=False)
                    elif isinstance(channel, discord.TextChannel):
                        await channel.set_permissions(role, send_messages=False, add_reactions=False)
                except discord.Forbidden:
                    continue
                except Exception:
                    continue
                await asyncio.sleep(0.02)
        except discord.Forbidden:
            raise
        return role

    async def _send_mute_log(self, guild, member, moderator, reason, duration_text):
        try:
            cog = self.bot.get_cog("Logging")
            if cog:
                banner = guild.banner.url if guild.banner else None
                from cogs.commands.logging import build_pro_embed
                embed = build_pro_embed(
                    guild=guild, user=member,
                    title="Member Muted", emoji=str(emojis.WARNINGICON),
                    description=f"{member.mention} was muted and given `{MUTED_ROLE_NAME}`",
                    color=0xED4245,
                    fields=[
                        ("Member", f"{member.mention} `({member.id})`", True),
                        ("Moderator", f"{moderator.mention}", True),
                        ("Duration", f"`{duration_text}`", True),
                        ("Reason", f"`{reason or 'No reason'}`", False),
                        ("Role", f"`{MUTED_ROLE_NAME}`", True),
                    ],
                    banner_url=banner,
                    thumbnail_url=member.display_avatar.url
                )
                await cog.send_log(guild, "mute", embed)
        except Exception:
            pass

    async def _auto_unmute_role(self, guild_id: int, member_id: int, duration: int):
        await asyncio.sleep(duration)
        try:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                return
            member = guild.get_member(member_id)
            if not member:
                return
            role = discord.utils.get(guild.roles, name=MUTED_ROLE_NAME)
            if role and role in member.roles:
                await member.remove_roles(role, reason="Auto unmute - mute duration expired")
            if member.voice and member.voice.mute:
                await member.edit(mute=False, reason="Auto unmute - mute duration expired")
        except Exception:
            pass

    @commands.command(
        name="mute",
        help="Mute a member with Zyro Muted role (5m auto)",
        usage="mute <member> [reason]",
        aliases=["servermute", "vmute", "timeout", "stfu"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @bot_has_permissions(manage_roles=True, mute_members=True)
    async def mute(self, ctx, member: discord.Member, *, reason: str = None):
        # Basic checks
        if member.bot:
            embed = discord.Embed(description=f"{emojis.CROSSICON} You cannot mute a bot.", color=self.color)
            return await ctx.send(view=embed_to_view(embed))
        if member == ctx.guild.owner:
            error = discord.Embed(color=self.color, description=f"{emojis.CROSSICON} You can't mute the Server Owner!")
            error.set_author(name="Error")
            return await ctx.send(view=embed_to_view(error))
        if ctx.author != ctx.guild.owner and member.top_role >= ctx.author.top_role:
            error = discord.Embed(color=self.color, description=f"{emojis.CROSSICON} You can't mute users having higher or equal role than yours!")
            error.set_author(name="Error")
            return await ctx.send(view=embed_to_view(error))
        if member.top_role >= ctx.guild.me.top_role:
            error = discord.Embed(color=self.color, description=f"{emojis.CROSSICON} I can't mute users having higher or equal role than mine. Move my role higher.")
            error.set_author(name="Error")
            return await ctx.send(view=embed_to_view(error))

        # Get or create muted role
        try:
            muted_role = await self.get_or_create_muted_role(ctx.guild)
        except discord.Forbidden:
            embed = discord.Embed(description=f"{emojis.CROSSICON} I need `Manage Roles` permission to create `{MUTED_ROLE_NAME}`.", color=self.color)
            return await ctx.send(view=embed_to_view(embed))

        if muted_role in member.roles:
            embed = discord.Embed(description=f"{emojis.ICONS_WARNING} **{member.name}** is already muted (`{MUTED_ROLE_NAME}`).", color=self.color)
            embed.set_author(name="Already Muted", icon_url=self.get_user_avatar(member))
            return await ctx.send(view=embed_to_view(embed))

        reason = reason or "No reason provided"
        duration_text = DEFAULT_MUTE_TEXT
        duration_seconds = DEFAULT_MUTE_DURATION

        # Apply role + voice mute if in voice
        try:
            await member.add_roles(muted_role, reason=f"Muted by {ctx.author} | {reason}")
            if member.voice and member.voice.channel:
                try:
                    await member.edit(mute=True, reason=f"Muted by {ctx.author}")
                except Exception:
                    pass
        except discord.Forbidden:
            embed = discord.Embed(description=f"{emojis.CROSSICON} I lack permission to give {muted_role.mention} to {member.mention}.", color=self.color)
            return await ctx.send(view=embed_to_view(embed))

        try:
            from utils.admin_dm import send_admin_dm
            from utils import emojis as _emo
            dm_ok = await send_admin_dm(
                member,
                title="Server Muted",
                emoji=str(_emo.WARNINGICON),
                description=f"You have been **muted** in **{ctx.guild.name}**.",
                color=0xED4245,
                fields=[
                    ("Server", ctx.guild.name, True),
                    ("Duration", f"`{duration_text}`", True),
                    ("Reason", f"`{reason}`", False),
                ],
            )
            dm_status = "Yes" if dm_ok else "No"
        except Exception:
            dm_status = "No"

        # Professional, consistent confirmation embed (avatar thumbnail + server banner)
        from cogs.commands.logging import build_pro_embed
        _banner = ctx.guild.banner.url if ctx.guild.banner else None
        embed = build_pro_embed(
            guild=ctx.guild, user=member,
            title="Successfully Muted", emoji=str(emojis.WARNINGICON),
            description=f"{member.mention} was muted with `{MUTED_ROLE_NAME}` — voice mic muted, auto-unmute after `{duration_text}`.",
            color=0xED4245,
            fields=[
                ("Target", f"{member.mention} `({member.id})`", True),
                ("Role", muted_role.mention, True),
                ("Duration", f"`{duration_text}`", True),
                ("DM Sent", f"`{dm_status}`", True),
                ("Reason", f"`{reason}`", False),
            ],
            banner_url=_banner,
            thumbnail_url=member.display_avatar.url if member.display_avatar else None,
        )

        view = ServerMuteView(user=member, author=ctx.author, role=muted_role)
        msg = await ctx.send(view=embed_to_view(embed, view=view))
        view.message = msg

        await self._send_mute_log(ctx.guild, member, ctx.author, reason, duration_text)
        asyncio.create_task(self._auto_unmute_role(ctx.guild.id, member.id, duration_seconds))

    @mute.error
    async def mute_error(self, ctx, error):
        if isinstance(error, commands.BotMissingPermissions):
            # Bot has Administrator? then this is a stale-cache false positive
            has_admin = ctx.guild and ctx.guild.me and ctx.guild.me.guild_permissions.administrator
            if has_admin:
                embed = discord.Embed(title=f"{emojis.CROSSICON} Access Denied", description="The bot is missing `Mute Members` in its current permission cache (it has Administrator). Restart the bot or grant `Mute Members` to the bot role.", color=self.color)
                embed.set_footer(text="Administrator detected - try again after bot restart")
                await ctx.send(view=embed_to_view(embed))
            else:
                embed = discord.Embed(title=f"{emojis.CROSSICON} Access Denied", description=f"I need `Manage Roles` and `Mute Members` to run `mute`.", color=self.color)
                await ctx.send(view=embed_to_view(embed))
        elif isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(title=f"{emojis.CROSSICON} Missing Permissions", description="You need `Manage Roles` to mute.", color=self.color)
            await ctx.send(view=embed_to_view(embed))
        elif isinstance(error, discord.Forbidden):
            embed = discord.Embed(title=f"{emojis.CROSSICON} Missing Permissions", description="I can't mute this user due to role hierarchy.", color=self.color)
            await ctx.send(view=embed_to_view(embed))
        else:
            embed = discord.Embed(title=f"{emojis.CROSSICON} Unexpected Error", description=str(error), color=self.color)
            await ctx.send(view=embed_to_view(embed))
