from utils import emojis

import discord
from discord.ext import commands
from discord import ui
from utils.Tools import *
from datetime import timedelta
from utils.cv2_compat import embed_to_view, embeds_to_view, sync_panel_message

class MuteUnmuteView(ui.View):
    def __init__(self, user, author):
        super().__init__(timeout=120)
        self.user = user
        self.author = author
        self.message = None  

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            await interaction.response.send_message("You are not allowed to interact with this!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        await sync_panel_message(self, skip_labels=("Delete",))

    @ui.button(label="Add Timeout", style=discord.ButtonStyle.danger)
    async def mute(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = MuteReasonModal(user=self.user, author=self.author, view=self)
        await interaction.response.send_modal(modal)

        
        await sync_panel_message(self, skip_labels=("Delete",))

    @ui.button(style=discord.ButtonStyle.gray, emoji=f"{emojis.DELETE}")
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class MuteReasonModal(ui.Modal):
    def __init__(self, user, author, view):
        super().__init__(title="Mute Information")
        self.user = user
        self.author = author
        self.view = view
        self.time_input = ui.TextInput(label="Duration (m/h/d)", placeholder="Leave blank for default 24h", required=False, max_length=5)
        self.reason_input = ui.TextInput(label="Reason", placeholder="Provide a reason or leave it blank.", required=False, max_length=2000, style=discord.TextStyle.paragraph)
        self.add_item(self.time_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        reason = self.reason_input.value or "No reason provided"
        time_str = self.time_input.value or "24h"
        time_seconds = self.parse_duration(time_str)

        if time_seconds is None:
            await interaction.response.send_message(f"Invalid time format! Please provide in m (minutes), h (hours), or d (days).", ephemeral=True)
            return

        try:
            await self.user.edit(timed_out_until=discord.utils.utcnow() + timedelta(seconds=time_seconds))
        except discord.Forbidden:
            await interaction.response.send_message(f"Failed to mute {self.user.mention}. I lack the permissions.", ephemeral=True)
            return

        
        _dm_ok = False
        try:
            from utils.admin_dm import send_admin_dm
            from utils import emojis as _emo
            _dm_ok = await send_admin_dm(
                self.user,
                title="Timeout Applied",
                emoji=str(_emo.TIMER if hasattr(_emo, "TIMER") else _emo.WARNING),
                description=f"You have been muted (timeout) in **{interaction.guild.name}**.",
                color=0xFEE75C,
                fields=[
                    ("Server", interaction.guild.name, True),
                    ("Duration", f"`{time_str}`", True),
                    ("Reason", f"`{reason}`", False),
                ],
            )
        except Exception:
            _dm_ok = False
        dm_status = "Yes" if _dm_ok else "No"

        from cogs.commands.logging import build_pro_embed
        from utils import emojis
        _guild = getattr(interaction, "guild", None) or getattr(self.view, "ctx", None) and getattr(self.view.ctx, "guild", None)
        _banner = _guild.banner.url if _guild and _guild.banner else None
        success_embed = build_pro_embed(
            guild=_guild, user=self.user,
            title="Successfully Muted", emoji=str(emojis.WARNINGICON),
            description=f"{self.user.mention} was muted in **{_guild.name if _guild else ''}**.",
            color=0xED4245,
            fields=[
                ("Target", f"{self.user.mention} `({self.user.id})`", True),
                ("Duration", f"`{time_str}`", True),
                ("DM Sent", f"`{dm_status}`", True),
                ("Reason", f"`{reason}`", False),
            ],
            banner_url=_banner,
            thumbnail_url=self.user.display_avatar.url if self.user.display_avatar else None,
        )

        await interaction.response.edit_message(view = embed_to_view(success_embed, view = self.view))

        
        for item in self.view.children:
            if item.label != "Delete":
                item.disabled = True
        await self.view.message.edit(view=self.view)

    def parse_duration(self, duration_str: str) -> int:
        try:
            if duration_str.endswith("m"):
                duration = int(duration_str[:-1])
                return duration * 60
            elif duration_str.endswith("h"):
                duration = int(duration_str[:-1])
                return duration * 3600
            elif duration_str.endswith("d"):
                duration = int(duration_str[:-1])
                return duration * 86400
            else:
                
                duration = int(duration_str)
                if duration > 60:
                    return (duration // 60) * 3600  
                else:
                    return duration * 60  
        except ValueError:
            return None


class Unmute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color = discord.Color.from_rgb(0, 0, 0)

    def get_user_avatar(self, user):
        return user.avatar.url if user.avatar else user.default_avatar.url

    @commands.command(
        name="unmute",
        help="Unmutes a muted user (role + voice)",
        usage="unmute <member>",
        aliases=["untimeout", "unsmute", "vunmute"])
    @blacklist_check()
    @ignore_check()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.max_concurrency(1, per=commands.BucketType.default, wait=False)
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(self, ctx, user: discord.Member):
        muted_role = discord.utils.get(ctx.guild.roles, name="Zyro Muted")
        is_role_muted = muted_role and muted_role in user.roles
        is_voice_muted = user.voice and user.voice.mute
        is_timed_out = user.timed_out_until and user.timed_out_until > discord.utils.utcnow()
        if not is_role_muted and not is_voice_muted and not is_timed_out:
            embed = discord.Embed(description=f"{emojis.CROSSICON} **{user.mention}** is not muted.", color=self.color)
            embed.set_author(name=f"{user.name} is Not Muted!", icon_url=self.get_user_avatar(user))
            embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            return await ctx.send(view=embed_to_view(embed))

        try:
            if is_role_muted:
                await user.remove_roles(muted_role, reason=f"Unmuted by {ctx.author}")
            if is_voice_muted:
                await user.edit(mute=False, reason=f"Unmuted by {ctx.author}")
            if is_timed_out:
                await user.edit(timed_out_until=None, reason=f"Unmuted by {ctx.author}")

            
            _dm_ok = False
            try:
                from utils.admin_dm import send_admin_dm
                from utils import emojis as _emo
                _dm_ok = await send_admin_dm(
                    user,
                    title="Server Unmute",
                    emoji=str(_emo.TICK),
                    description=f"You have been **unmuted** in **{ctx.guild.name}**.",
                    color=0x57F287,
                    fields=[("Server", ctx.guild.name, True)],
                )
            except Exception:
                _dm_ok = False
            dm_status = "Yes" if _dm_ok else "No"

        except discord.Forbidden:
            error = discord.Embed(color=self.color, description="I can't unmute a user with higher permissions!")
            error.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
            error.set_author(name="Error Unmuting User", icon_url="https://cdn.discordapp.com/emojis/1294218790082711553.png")
            return await ctx.send(view = embed_to_view(error))

        embed = discord.Embed(
            description=f"**Target:** [{user}](https://discord.com/users/{user.id})\n**Mention:** {user.mention}\n**DM Sent:** `{dm_status}`",
            color=self.color
        )
        embed.set_author(name=f"Successfully Unmuted {user.name}", icon_url=self.get_user_avatar(user))
        embed.add_field(name="Moderator:", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=self.get_user_avatar(ctx.author))
        embed.timestamp = discord.utils.utcnow()

        # Log to unwarn/mute logs
        try:
            cog = self.bot.get_cog("Logging")
            if cog:
                banner = ctx.guild.banner.url if ctx.guild.banner else None
                from cogs.commands.logging import build_pro_embed
                log_embed = build_pro_embed(
                    guild=ctx.guild, user=user,
                    title="Member Unmuted", emoji=str(emojis.TICK),
                    description=f"> {user.mention} has been unmuted",
                    color=0x57F287,
                    fields=[
                        ("👤 Member", f"{user.mention} `({user.id})`", True),
                        ("🛡️ Moderator", f"{ctx.author.mention}", True),
                    ],
                    banner_url=banner,
                    thumbnail_url=user.display_avatar.url
                )
                await cog.send_log(ctx.guild, "unwarn", log_embed)
        except Exception:
            pass

        view = MuteUnmuteView(user=user, author=ctx.author)
        message = await ctx.send(view = embed_to_view(embed, view = view))
        view.message = message


"""
@Author: Sonu Jana
    + Discord: me.sonu
    + Community: https://discord.gg/stVsvE9rhT (Zyro)
    + for any queries reach out Community or DM me.
"""