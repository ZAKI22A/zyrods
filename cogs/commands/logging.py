import discord
from discord.ext import commands
from datetime import datetime, timezone
import asyncio

from utils.database import open_connection
from utils import emojis

DB_FILE = "logging.db"

# ============================================================
# SYSTEM-LOGS definitions - English + only project emojis
# ============================================================
LOG_DEFINITIONS = {
    "mod-logs": ("mod", str(emojis.MOD), "Mod Logs", "General moderation actions", 0x2B2D31),
    "join-left-server": ("join_left", str(emojis.GREET), "Member Join / Leave", "Members joining and leaving the server", 0x57F287),
    "edit-message-logs": ("msg_edit", str(emojis.FILE), "Message Edited", "Edited messages", 0xFEE75C),
    "delete-message-logs": ("msg_delete", str(emojis.DELETE), "Message Deleted", "Deleted messages", 0xED4245),
    "channel-updated": ("ch_update", str(emojis.ICONS_CHANNEL), "Channel Updated", "Channel settings updated", 0x5865F2),
    "channel-created": ("ch_create", str(emojis.ICONS_CHANNEL), "Channel Created", "New channel created", 0x57F287),
    "channel-deleted": ("ch_delete", str(emojis.DELETE), "Channel Deleted", "Channel deleted", 0xED4245),
    "channel-permission-updated": ("ch_perms", str(emojis.GEAR), "Channel Permissions Updated", "Channel permission overwrites updated", 0xFEE75C),
    "roles-updated": ("role_update", str(emojis.CUSTOMROLE), "Role Updated", "Role settings updated", 0x5865F2),
    "roles-created": ("role_create", str(emojis.ICONS_PLUS), "Role Created", "New role created", 0x57F287),
    "roles-deleted": ("role_delete", str(emojis.DELETE), "Role Deleted", "Role deleted", 0xED4245),
    "roles-given": ("role_given", str(emojis.STAR), "Roles Given", "Role assigned to member", 0x57F287),
    "roles-removed": ("role_removed", str(emojis.REM_NO), "Roles Removed", "Role removed from member", 0xED4245),
    "updated-server": ("guild_update", str(emojis.HOME), "Server Updated", "Server settings updated", 0x5865F2),
    "join-left-voice": ("voice_join", str(emojis.VOICE), "Voice Join / Leave", "Voice channel join and leave", 0x57F287),
    "switch-voice-logs": ("voice_switch", str(emojis.VOICE), "Voice Switch", "Switched between voice channels", 0x5865F2),
    "move-logs": ("voice_move", str(emojis.VOICE), "Member Moved", "Member moved between voice channels by moderator", 0xFEE75C),
    "disconnect-logs": ("voice_disconnect", str(emojis.VOICE), "Voice Disconnect", "Voice disconnect / leave", 0xED4245),
    "security-logs": ("security", str(emojis.SECURITY), "Security Logs", "Security and AntiNuke alerts", 0xED4245),
    "ticket-logs": ("ticket", str(emojis.TICKET), "Ticket Logs", "Ticket events", 0x5865F2),
    "bot-logs": ("bot", str(emojis.BOTS), "Bot Logs", "Bot join and leave", 0x5865F2),
    "command-logs": ("command", str(emojis.COMMANDS), "Command Logs", "Command usage", 0x2B2D31),
    "member-kicked": ("kick", str(emojis.EMOJI_7CLUB_BAN), "Member Kicked", "Member kicked from server", 0xED4245),
    "ban-logs": ("ban", str(emojis.EMOJI_7CLUB_BAN), "Member Banned", "Member banned", 0xED4245),
    "unban-logs": ("unban", str(emojis.TICK), "Member Unbanned", "Member unbanned", 0x57F287),
    "mute-logs": ("mute", str(emojis.WARNINGICON), "Server Muted", "Member server muted", 0xFEE75C),
    "warn-logs": ("warn", str(emojis.WARNING), "Member Warned", "Member warned", 0xFEE75C),
    "unwarn-logs": ("unwarn", str(emojis.TICK), "Warning Removed", "Warning removed", 0x57F287),
    "timeout-given": ("timeout", str(emojis.TIMER), "Timeout Given", "Timeout applied", 0xFEE75C),
    "nickname-change": ("nick", str(emojis.USER), "Nickname Changed", "Nickname updated", 0x5865F2),
    "invite-logs": ("invite", str(emojis.INVITETRACKER), "Invite Logs", "Invite created and deleted", 0x57F287),
}

CATEGORY_NAME = "SYSTEM-LOGS"

def _now():
    return datetime.now(timezone.utc)

async def _fetch_banner_url(bot, user: discord.abc.User | None, guild: discord.Guild | None) -> str | None:
    """Fetch banner - rectangular image at bottom"""
    url = None
    if user:
        try:
            fetched = await bot.fetch_user(user.id)
            if fetched.banner:
                url = fetched.banner.url
        except Exception:
            pass
    if not url and guild and guild.banner:
        url = guild.banner.url
    return url

def build_pro_embed(
    guild: discord.Guild | None,
    user: discord.abc.User | discord.Member | None,
    title: str,
    emoji: str,
    description: str,
    color: int,
    fields: list[tuple[str, str, bool]] | None = None,
    banner_url: str | None = None,
    thumbnail_url: str | None = None,
) -> discord.Embed:
    """
    Professional organized embed:
    - Author: server name + icon (top)
    - Title: emoji + title
    - Description: short English
    - Fields: organized (2-3 per row max, single column for content)
    - Thumbnail: small top-right (user avatar)
    - Image: rectangular banner at bottom
    - Footer: guild + timestamp + icon
    - Timestamp: UTC
    """
    embed = discord.Embed(
        title=f"{emoji}  {title}",
        description=description,
        color=color,
        timestamp=_now(),
    )
    # Author - server
    if guild and guild.icon:
        embed.set_author(name=guild.name, icon_url=guild.icon.url)
    elif guild:
        embed.set_author(name=guild.name)

    # Thumbnail: small top-right - user avatar
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    elif user and hasattr(user, "display_avatar"):
        embed.set_thumbnail(url=user.display_avatar.url)

    # Banner: rectangular bottom
    if banner_url:
        embed.set_image(url=banner_url)

    # Organized fields
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)

    footer_icon = guild.icon.url if guild and guild.icon else (user.display_avatar.url if user and hasattr(user, "display_avatar") else None)
    embed.set_footer(text=f"{guild.name if guild else 'Zyro'}  •  {_now().strftime('%Y-%m-%d %H:%M UTC')}", icon_url=footer_icon)
    return embed

class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self._invite_cache = {}

    async def cog_load(self) -> None:
        self.db = await open_connection(DB_FILE)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS log_channels (
                guild_id INTEGER,
                log_type TEXT,
                channel_id INTEGER,
                PRIMARY KEY (guild_id, log_type)
            )
        """)
        await self.db.commit()
        if not self._invite_cache and self.bot.is_ready():
            await self._refresh_invites()

    async def _refresh_invites(self):
        for guild in self.bot.guilds:
            try:
                self._invite_cache[guild.id] = await guild.invites()
            except Exception:
                self._invite_cache[guild.id] = []

    @commands.Cog.listener()
    async def on_ready(self):
        await self._refresh_invites()

    async def cog_unload(self) -> None:
        if self.db is not None:
            await self.db.close()

    async def set_log_channel(self, guild_id, log_type, channel_id):
        await self.db.execute(
            "REPLACE INTO log_channels (guild_id, log_type, channel_id) VALUES (?, ?, ?)",
            (guild_id, log_type, channel_id),
        )
        await self.db.commit()

    async def get_log_channel(self, guild_id, log_type):
        async with self.db.execute(
            "SELECT channel_id FROM log_channels WHERE guild_id = ? AND log_type = ?",
            (guild_id, log_type),
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] if result else None

    async def send_log(self, guild: discord.Guild, log_type: str, embed: discord.Embed):
        if not guild:
            return
        channel_id = await self.get_log_channel(guild.id, log_type)
        if not channel_id:
            print(f"[LOGGING] {log_type}: no channel configured for guild {guild.id}")
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            try:
                channel = await guild.fetch_channel(channel_id)
            except Exception:
                return
        if channel:
            try:
                # Native embed - thumbnail top-right + banner rectangular (professional, not random gallery)
                await channel.send(embed=embed)
                print(f"[LOGGING] {log_type} -> sent to #{channel.name}")
            except discord.Forbidden:
                print(f"[LOGGING] {log_type}: Missing permissions in {channel.name}")
            except Exception as e:
                print(f"[LOGGING] {log_type}: send failed in {channel.name}: {type(e).__name__}: {e}")

    # ================== SETUP COMMAND ==================
    @commands.command(name="setuplogging", aliases=["loggingsetup", "setuplogs", "setup-logs", "setuplog"])
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def setuplogging(self, ctx: commands.Context):
        guild = ctx.guild
        await ctx.typing()
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True, manage_channels=True)
        }
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if not category:
            category = await guild.create_category(CATEGORY_NAME, overwrites=overwrites, reason="Setup logging - Zyro")

        # Self-healing: clear stale DB mappings for this guild so every channel gets revalidated
        await self.db.execute("DELETE FROM log_channels WHERE guild_id = ?", (guild.id,))
        await self.db.commit()

        created = []
        for channel_name, (db_key, emoji, title, desc, color) in LOG_DEFINITIONS.items():
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if not channel or channel.category != category:
                if channel:
                    try:
                        channel = await guild.fetch_channel(channel.id)
                    except Exception:
                        channel = None
                    if channel:
                        try:
                            await channel.edit(category=category, sync_permissions=True)
                        except Exception:
                            channel = None
                if not channel:
                    channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, reason="Logging setup")
                    await asyncio.sleep(0.25)
            # Re-fetch to guarantee a valid, resolvable channel id
            try:
                channel = await guild.fetch_channel(channel.id)
            except Exception:
                channel = None
            if not channel:
                channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites, reason="Logging setup")
                await asyncio.sleep(0.25)
            await self.set_log_channel(guild.id, db_key, channel.id)
            created.append(channel)

            banner_url = guild.banner.url if guild.banner else None
            intro = build_pro_embed(
                guild=guild, user=ctx.author,
                title=title, emoji=emoji,
                description=f"**{desc}**\nThis channel is strictly for **{title}** events. All logs here use a professional embed with the member's avatar (top-right thumbnail) and a rectangular banner at the bottom.",
                color=color,
                fields=[
                    ("Status", f"{emojis.TICK} Active", True),
                    ("Channel", channel.mention, True),
                    ("Category", category.name, True),
                    ("Type", f"`{db_key}`", True),
                ],
                banner_url=banner_url,
                thumbnail_url=guild.icon.url if guild.icon else ctx.author.display_avatar.url
            )
            try:
                async for msg in channel.history(limit=10):
                    if msg.author == guild.me and msg.embeds:
                        try:
                            await msg.delete()
                        except Exception:
                            pass
                await channel.send(embed=intro)
            except Exception:
                pass

        summary_banner = guild.banner.url if guild.banner else None
        summary = build_pro_embed(
            guild=guild, user=ctx.author,
            title="SYSTEM-LOGS Setup Completed", emoji=str(emojis.LOGGING),
            description=f"Successfully created **{len(created)}** logging channels under {category.mention}. Each channel has a dedicated, organized professional embed (avatar thumbnail + rectangular banner) using only built-in Zyro emojis and English language.",
            color=0x2B2D31,
            fields=[
                ("Category", category.mention, True),
                ("Total Channels", f"`{len(created)}`", True),
                ("Moderator", ctx.author.mention, True),
            ],
            banner_url=summary_banner,
            thumbnail_url=guild.icon.url if guild.icon else ctx.author.display_avatar.url
        )
        # Add list as field (organized)
        channel_list = "\n".join([f"{emoji} `{name}`" for name, (_, emoji, _, _, _) in LOG_DEFINITIONS.items()])
        summary.add_field(name="Channels Created", value=channel_list[:1024], inline=False)
        await ctx.send(embed=summary)

    @commands.command(name="removelogs", aliases=["deletelogs", "clearlogs"])
    @commands.has_permissions(administrator=True)
    async def removelogs(self, ctx):
        guild = ctx.guild
        await self.db.execute("DELETE FROM log_channels WHERE guild_id = ?", (guild.id,))
        await self.db.commit()
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        count = 0
        if category:
            for channel in list(category.channels):
                try:
                    await channel.delete(reason="Remove logs")
                    count += 1
                    await asyncio.sleep(0.2)
                except Exception:
                    pass
            try:
                await category.delete(reason="Remove logs")
            except Exception:
                pass
        embed = build_pro_embed(guild, ctx.author, "Logs Removed", str(emojis.DELETE), f"Deleted `{count}` logging channels and category `{CATEGORY_NAME}`.", 0xED4245, None, None, guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)

    @commands.command(name="testlogs", aliases=["testlog", "logstest", "test-logs"])
    @commands.has_permissions(administrator=True)
    async def testlogs(self, ctx, *, target: str = "all"):
        """Test every logging channel one by one to verify they work."""
        guild = ctx.guild
        target = target.strip().lower()
        banner = guild.banner.url if guild.banner else None
        thumb = guild.icon.url if guild.icon else ctx.author.display_avatar.url
        tested = []
        missing = []

        async def send_test(db_key, channel_name):
            channel_id = await self.get_log_channel(guild.id, db_key)
            if not channel_id:
                missing.append(f"{channel_name} (no config for `{db_key}`)")
                return
            ch = guild.get_channel(channel_id)
            if not ch:
                missing.append(f"{channel_name} (channel gone/bot can't see)")
                return
            embed = build_pro_embed(
                guild, ctx.author, f"Test: {channel_name}", str(emojis.TICK if True else emojis.DELETE),
                f"LOG TEST for **`{db_key}`** — if you see this, the channel works.",
                0x57F287,
                [
                    ("Channel", f"{ch.mention} `@{channel_name}`", True),
                    ("Type", f"`{db_key}`", True),
                    ("Entered By", ctx.author.mention, True),
                ],
                banner, thumb
            )
            try:
                await ch.send(embed=embed)
                tested.append(f"{channel_name} ✓")
            except Exception as e:
                missing.append(f"{channel_name} (send failed: {type(e).__name__})")

        if target == "all":
            for channel_name, (db_key, *_rest) in LOG_DEFINITIONS.items():
                await send_test(db_key, channel_name)
                await asyncio.sleep(0.1)
        else:
            # match by channel name or db_key
            matched = None
            for channel_name, (db_key, *_rest) in LOG_DEFINITIONS.items():
                if channel_name == target or db_key == target:
                    matched = (channel_name, db_key)
                    break
            if not matched:
                avail = ", ".join(list(LOG_DEFINITIONS.keys())[:20])
                await ctx.send(embed=build_pro_embed(guild, ctx.author, "Test Logs", str(emojis.WARNING), f"No channel matched `{target}`.\n\nTry `all` or one of:\n`{avail}`...", 0xFEE75C, None, banner, thumb))
                return
            await send_test(matched[0], matched[1])

        fields = [("Working", "\n".join(tested[:20]) if tested else "None", False)]
        if missing:
            fields.append(("Failed / Missing", "\n".join(missing[:20]), False))
        fields.append(("Total Channels", f"`{len(LOG_DEFINITIONS)}`", True))
        embed = build_pro_embed(guild, ctx.author, "Logging Test Complete", str(emojis.LOGGING), f"Tested **{len(tested)}** channels. Check each channel for its test embed.", 0x5865F2, fields, banner, thumb)
        await ctx.send(embed=embed)

    # ================== LISTENERS - English + organized ==================

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        try:
            await self._member_join_inner(member)
        except Exception:
            import traceback; traceback.print_exc()
            print(f"[LOGGING] on_member_join UNHANDLED")

    async def _member_join_inner(self, member: discord.Member):
        print(f"[LOGGING] on_member_join called for {member}")
        banner = await _fetch_banner_url(self.bot, member, member.guild)
        inviter = None
        # Detect who invited via invite uses tracking (reliable)
        try:
            if member.guild.me.guild_permissions.manage_guild or member.guild.me.guild_permissions.manage_channels:
                before = self._invite_cache.get(member.guild.id, [])
                after_invites = await member.guild.invites()
                self._invite_cache[member.guild.id] = after_invites
                for a in after_invites:
                    b = discord.utils.get(before, code=a.code)
                    if b is None or a.uses > b.uses:
                        inviter = a.inviter
                        break
                if not inviter:
                    print(f"[LOGGING] join: {member} no inviter matched (cache={len(before)})")
        except Exception as e:
            print(f"[LOGGING] invite detect failed for {member}: {type(e).__name__}: {e}")
        fields = [
            ("Member", f"{member.mention}\n`{member}`", True),
            ("ID", f"`{member.id}`", True),
            ("Account Created", f"<t:{int(member.created_at.timestamp())}:R>", True),
            ("Member Count", f"`{member.guild.member_count}`", True),
        ]
        if inviter and not member.bot:
            fields.append(("Invited By", f"{inviter.mention} `({inviter.id})`", True))
        embed = build_pro_embed(
            member.guild, member, "Member Joined", str(emojis.GREET),
            f"{member.mention} joined the server.",
            0x57F287,
            fields,
            banner
        )
        await self.send_log(member.guild, "join_left", embed)
        if member.bot:
            b_embed = build_pro_embed(member.guild, member, "Bot Added", str(emojis.BOTS), f"{member.mention} was added to the server.", 0x5865F2, [("Bot", f"{member.mention} `({member.id})`", True)], banner)
            await self.send_log(member.guild, "bot", b_embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        try:
            await self._member_remove_inner(member)
        except Exception:
            import traceback; traceback.print_exc()
            print(f"[LOGGING] on_member_remove UNHANDLED")

    async def _member_remove_inner(self, member: discord.Member):
        print(f"[LOGGING] on_member_remove called for {member}")
        guild = member.guild
        banner = await _fetch_banner_url(self.bot, member, guild)
        embed = build_pro_embed(
            guild, member, "Member Left", str(emojis.DELETE),
            f"{member} left the server.",
            0xED4245,
            [
                ("Member", f"`{member}`", True),
                ("ID", f"`{member.id}`", True),
                ("Joined", f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", True),
            ],
            banner
        )
        await self.send_log(guild, "join_left", embed)

        # Detect manual kick via mouse / right-click (audit log) - ensures every kick is logged regardless of method
        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                    if entry.target and entry.target.id == member.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 10:
                        kick_banner = await _fetch_banner_url(self.bot, entry.user, guild)
                        kick_embed = build_pro_embed(
                            guild, member, "Member Kicked", str(emojis.EMOJI_7CLUB_BAN),
                            f"{member} was kicked from the server",
                            0xED4245,
                            [
                                ("Member", f"`{member}` `({member.id})`", True),
                                ("Moderator", f"{entry.user.mention} `({entry.user.id})`", True),
                                ("Reason", f"`{entry.reason or 'No reason'}`", False),
                            ],
                            kick_banner or banner
                        )
                        await self.send_log(guild, "kick", kick_embed)
                        # Also log to mod-logs for legacy
                        await self.send_log(guild, "mod", kick_embed)
                        break
        except discord.Forbidden:
            pass
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        banner = await _fetch_banner_url(self.bot, message.author, message.guild)
        content = (message.content[:1000] + "...") if len(message.content) > 1000 else (message.content or "*No content / attachment*")
        embed = build_pro_embed(
            message.guild, message.author, "Message Deleted", str(emojis.DELETE),
            f"Message deleted in {message.channel.mention}",
            0xED4245,
            [
                ("Author", f"{message.author.mention} `({message.author.id})`", True),
                ("Channel", f"{message.channel.mention}", True),
                ("Content", f"```{content}```", False),
            ],
            banner
        )
        await self.send_log(message.guild, "msg_delete", embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot or before.content == after.content:
            return
        banner = await _fetch_banner_url(self.bot, before.author, before.guild)
        before_c = (before.content[:500] + "...") if len(before.content) > 500 else before.content or "None"
        after_c = (after.content[:500] + "...") if len(after.content) > 500 else after.content or "None"
        embed = build_pro_embed(
            before.guild, before.author, "Message Edited", str(emojis.FILE),
            f"Message edited in {before.channel.mention} [Jump]({after.jump_url})",
            0xFEE75C,
            [
                ("Author", f"{before.author.mention}", True),
                ("Channel", before.channel.mention, True),
                ("Before", f"```{before_c}```", False),
                ("After", f"```{after_c}```", False),
            ],
            banner
        )
        await self.send_log(before.guild, "msg_edit", embed)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        banner = guild.banner.url if guild.banner else None
        embed = build_pro_embed(
            guild, guild.me, "Channel Created", str(emojis.ICONS_CHANNEL),
            f"New channel created",
            0x57F287,
            [
                ("Channel", f"{channel.mention if hasattr(channel,'mention') else channel.name} `({channel.id})`", True),
                ("Type", str(channel.type), True),
                ("Category", channel.category.name if channel.category else "None", True),
            ],
            banner, guild.icon.url if guild.icon else None
        )
        await self.send_log(guild, "ch_create", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        banner = guild.banner.url if guild.banner else None
        embed = build_pro_embed(guild, guild.me, "Channel Deleted", str(emojis.DELETE), f"Channel deleted", 0xED4245, [("Name", f"`{channel.name}` `({channel.id})`", True), ("Type", str(channel.type), True)], banner, guild.icon.url if guild.icon else None)
        await self.send_log(guild, "ch_delete", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        guild = after.guild
        banner = guild.banner.url if guild.banner else None
        # Permission overwrites -> dedicated channel-permission-updated
        if before.overwrites != after.overwrites:
            # Try to get moderator from audit log
            mod = None
            try:
                if guild.me.guild_permissions.view_audit_log:
                    async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.overwrite_update):
                        if entry.target and entry.target.id == after.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                            mod = entry.user
                            break
            except Exception:
                pass
            # Skip logging when the change is from the bot itself (e.g. auto-created muted role)
            if mod and mod.id == self.bot.user.id:
                return
            fields = [("Channel", f"{after.mention} `({after.id})`", True), ("Moderator", mod.mention if mod else "Unknown", True)]
            embed = build_pro_embed(guild, guild.me, "Channel Permissions Updated", str(emojis.GEAR), f"Permission overwrites updated for {after.mention}", 0xFEE75C, fields, banner, guild.icon.url if guild.icon else None)
            await self.send_log(guild, "ch_perms", embed)
        # Any other channel attribute change -> channel-updated (comprehensive - logs every small change)
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if getattr(before, 'topic', None) != getattr(after, 'topic', None):
            changes.append(f"**Topic:** `{before.topic or 'None'}` → `{after.topic or 'None'}`")
        if getattr(before, 'bitrate', None) != getattr(after, 'bitrate', None):
            changes.append(f"**Bitrate:** `{before.bitrate}` → `{after.bitrate}`")
        if getattr(before, 'user_limit', None) != getattr(after, 'user_limit', None):
            changes.append(f"**User Limit:** `{before.user_limit}` → `{after.user_limit}`")
        if getattr(before, 'nsfw', None) != getattr(after, 'nsfw', None):
            changes.append(f"**NSFW:** `{before.nsfw}` → `{after.nsfw}`")
        if getattr(before, 'slowmode_delay', None) != getattr(after, 'slowmode_delay', None):
            changes.append(f"**Slowmode:** `{before.slowmode_delay}s` → `{after.slowmode_delay}s`")
        if getattr(before, 'category', None) != getattr(after, 'category', None):
            changes.append(f"**Category:** `{before.category}` → `{after.category}`")
        if changes:
            # Get moderator for channel update
            mod = None
            try:
                if guild.me.guild_permissions.view_audit_log:
                    async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.channel_update):
                        if entry.target and entry.target.id == after.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                            mod = entry.user
                            break
            except Exception:
                pass
            if mod and mod.id == self.bot.user.id:
                return
            desc = "\n".join(changes)[:1000]
            fields = [("Channel", f"{after.mention} `({after.id})`", True)]
            if mod:
                fields.append(("Moderator", mod.mention, True))
            fields.append(("Changes", desc, False))
            embed = build_pro_embed(guild, guild.me, "Channel Updated", str(emojis.ICONS_CHANNEL), f"Channel {after.mention} was updated", 0x5865F2, fields, banner, guild.icon.url if guild.icon else None)
            await self.send_log(guild, "ch_update", embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        # Skip roles auto-created by the bot (e.g. Zyro Muted)
        try:
            if role.guild.me.guild_permissions.view_audit_log:
                async for entry in role.guild.audit_logs(limit=3, action=discord.AuditLogAction.role_create):
                    if entry.target and entry.target.id == role.id and entry.user.id == self.bot.user.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        return
                    break
        except Exception:
            pass
        banner = role.guild.banner.url if role.guild.banner else None
        embed = build_pro_embed(role.guild, role.guild.me, "Role Created", str(emojis.ICONS_PLUS), f"New role created", 0x57F287, [("Role", f"{role.mention} `({role.id})`", True), ("Color", str(role.color), True)], banner, role.guild.icon.url if role.guild.icon else None)
        await self.send_log(role.guild, "role_create", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        banner = role.guild.banner.url if role.guild.banner else None
        embed = build_pro_embed(role.guild, role.guild.me, "Role Deleted", str(emojis.DELETE), f"Role deleted", 0xED4245, [("Role", f"`{role.name}` `({role.id})`", True)], banner, role.guild.icon.url if role.guild.icon else None)
        await self.send_log(role.guild, "role_delete", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before, after):
        guild = after.guild
        banner = guild.banner.url if guild.banner else None
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.color != after.color:
            changes.append(f"**Color:** `{before.color}` → `{after.color}`")
        if before.permissions.value != after.permissions.value:
            changes.append(f"**Permissions:** updated")
        if before.hoist != after.hoist:
            changes.append(f"**Hoist:** `{before.hoist}` → `{after.hoist}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**Mentionable:** `{before.mentionable}` → `{after.mentionable}`")
        if not changes:
            changes.append("Role settings changed")
        mod = None
        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.role_update):
                    if entry.target and entry.target.id == after.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        mod = entry.user
                        break
        except Exception:
            pass
        # Skip when the bot itself modified the role (e.g. Zyro Muted auto-created)
        if mod and mod.id == self.bot.user.id:
            return
        fields = [("Role", f"{after.mention} `({after.id})`", True)]
        if mod:
            fields.append(("Moderator", mod.mention, True))
        fields.append(("Changes", "\n".join(changes)[:1000], False))
        embed = build_pro_embed(guild, guild.me, "Role Updated", str(emojis.CUSTOMROLE), f"Role {after.mention} was updated", 0x5865F2, fields, banner, guild.icon.url if guild.icon else None)
        await self.send_log(guild, "role_update", embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        try:
            await self._member_update_inner(before, after)
        except Exception:
            import traceback; traceback.print_exc()
            print(f"[LOGGING] on_member_update UNHANDLED {type(before).__name__}")

    async def _member_update_inner(self, before: discord.Member, after: discord.Member):
        guild = after.guild
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        if added or removed:
            nicks = "Y" if before.nick != after.nick else "N"
            print(f"[LOGGING] member_update: {after} added={[r.name for r in added]} removed={[r.name for r in removed]} nick_change={nicks}")
        if before.nick != after.nick:
            banner = await _fetch_banner_url(self.bot, after, guild)
            embed = build_pro_embed(guild, after, "Nickname Changed", str(emojis.USER), f"Nickname changed", 0x5865F2, [("Member", f"{after.mention} `({after.id})`", True), ("Before", f"`{before.nick or before.name}`", True), ("After", f"`{after.nick or after.name}`", True)], banner)
            await self.send_log(guild, "nick", embed)
        added = set(after.roles) - set(before.roles)
        removed = set(before.roles) - set(after.roles)
        # Fetch audit log for role changes (mouse click) to get moderator
        moderator = None
        audit_reason = None
        try:
            if (added or removed) and guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target and entry.target.id == after.id and (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        moderator = entry.user
                        audit_reason = entry.reason
                        break
        except Exception as e:
            print(f"[LOGGING] audit fetch failed: {type(e).__name__}: {e}")
        if added:
            for role in added:
                try:
                    banner = await _fetch_banner_url(self.bot, after, guild)
                    fields = [("Member", after.mention, True), ("Role", role.mention, True)]
                    if moderator:
                        fields.append(("Moderator", moderator.mention, True))
                    if audit_reason:
                        fields.append(("Reason", f"`{audit_reason}`", False))
                    embed = build_pro_embed(guild, after, "Role Assigned", str(emojis.STAR), f"Role assigned to member (detected via {'audit log' if moderator else 'event'})", 0x57F287, fields, banner)
                    print(f"[LOGGING] role_given calling send for {role.name}")
                    await self.send_log(guild, "role_given", embed)
                    print(f"[LOGGING] role_given send done for {role.name}")
                    # Special: Zyro Muted role manually given via mouse -> also log to mute-logs (dedicated)
                    if role.name == "Zyro Muted":
                        mute_embed = build_pro_embed(guild, after, "Member Muted", str(emojis.WARNINGICON), f"{after.mention} was muted via role", 0xED4245, [("Member", f"{after.mention} `({after.id})`", True), ("Moderator", f"{moderator.mention if moderator else 'Unknown'}", True), ("Role", role.mention, True)], banner)
                        await self.send_log(guild, "mute", mute_embed)
                except Exception as e:
                    import traceback; traceback.print_exc()
                    print(f"[LOGGING] role_given FAILED-WITH-ERR for {role.name}: {type(e).__name__}: {e}")
        if removed:
            for role in removed:
                try:
                    banner = await _fetch_banner_url(self.bot, after, guild)
                    fields = [("Member", after.mention, True), ("Role", f"`{role.name}`", True)]
                    if moderator:
                        fields.append(("Moderator", moderator.mention, True))
                    embed = build_pro_embed(guild, after, "Role Removed", str(emojis.REM_NO), f"Role removed from member", 0xED4245, fields, banner)
                    await self.send_log(guild, "role_removed", embed)
                    if role.name == "Zyro Muted":
                        unmute_embed = build_pro_embed(guild, after, "Member Unmuted", str(emojis.TICK), f"{after.mention} was unmuted (role removed)", 0x57F287, [("Member", f"{after.mention} `({after.id})`", True), ("Moderator", f"{moderator.mention if moderator else 'Unknown'}", True)], banner)
                        await self.send_log(guild, "unwarn", unmute_embed)
                except Exception as e:
                    print(f"[LOGGING] role_removed failed for {role.name}: {type(e).__name__}: {e}")
        if before.timed_out_until != after.timed_out_until:
            if after.timed_out_until:
                banner = await _fetch_banner_url(self.bot, after, guild)
                embed = build_pro_embed(guild, after, "Timeout Applied", str(emojis.TIMER), f"Timeout applied", 0xFEE75C, [("Member", f"{after.mention}", True), ("Until", f"<t:{int(after.timed_out_until.timestamp())}:F>", True)], banner)
                await self.send_log(guild, "timeout", embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        banner = await _fetch_banner_url(self.bot, member, guild)
        if before.channel is None and after.channel is not None:
            embed = build_pro_embed(guild, member, "Voice Joined", str(emojis.VOICE), f"{member.mention} joined {after.channel.mention}", 0x57F287, [("Member", member.mention, True), ("Channel", after.channel.mention, True)], banner)
            await self.send_log(guild, "voice_join", embed)
        elif before.channel is not None and after.channel is None:
            embed = build_pro_embed(guild, member, "Voice Left", str(emojis.VOICE), f"{member.mention} left {before.channel.mention}", 0xED4245, [("Member", member.mention, True), ("Channel", f"`{before.channel.name}`", True)], banner)
            await self.send_log(guild, "voice_disconnect", embed)
        elif before.channel != after.channel:
            embed = build_pro_embed(guild, member, "Voice Switched", str(emojis.VOICE), f"{member.mention} switched voice channels", 0x5865F2, [("Member", member.mention, True), ("From", f"`{before.channel.name}`", True), ("To", f"{after.channel.mention}", True)], banner)
            await self.send_log(guild, "voice_switch", embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        guild = after
        banner = guild.banner.url if guild.banner else None
        changes = []
        if before.name != after.name:
            changes.append(f"**Name:** `{before.name}` → `{after.name}`")
        if before.icon != after.icon:
            changes.append(f"**Icon:** updated")
        if before.banner != after.banner:
            changes.append(f"**Banner:** updated")
        if before.verification_level != after.verification_level:
            changes.append(f"**Verification:** `{before.verification_level}` → `{after.verification_level}`")
        if before.default_notifications != after.default_notifications:
            changes.append(f"**Notifications:** updated")
        if before.premium_tier != after.premium_tier:
            changes.append(f"**Boost Tier:** `{before.premium_tier}` → `{after.premium_tier}`")
        if not changes:
            changes.append("Server settings updated")
        mod = None
        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(limit=3, action=discord.AuditLogAction.guild_update):
                    if (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        mod = entry.user
                        break
        except Exception:
            pass
        fields = []
        if mod:
            fields.append(("Moderator", mod.mention, True))
        fields.append(("Changes", "\n".join(changes)[:1000], False))
        embed = build_pro_embed(guild=guild, user=guild.me, title="Server Updated", emoji=str(emojis.HOME), description="Server was updated", color=0x5865F2, fields=fields, banner_url=banner, thumbnail_url=guild.icon.url if guild.icon else None)
        await self.send_log(guild, "guild_update", embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        banner = await _fetch_banner_url(self.bot, user, guild)
        embed = build_pro_embed(guild, user, "Member Banned", str(emojis.EMOJI_7CLUB_BAN), f"Member banned from server", 0xED4245, [("User", f"`{user}` `({user.id})`", True)], banner)
        await self.send_log(guild, "ban", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        banner = await _fetch_banner_url(self.bot, user, guild)
        embed = build_pro_embed(guild, user, "Member Unbanned", str(emojis.TICK), f"Member unbanned", 0x57F287, [("User", f"`{user}` `({user.id})`", True)], banner)
        await self.send_log(guild, "unban", embed)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        guild = invite.guild
        banner = guild.banner.url if guild and guild.banner else None
        inviter = invite.inviter
        thumb = inviter.display_avatar.url if inviter else (guild.icon.url if guild and guild.icon else None)
        embed = build_pro_embed(guild, inviter, "Invite Created", str(emojis.INVITETRACKER), f"New invite created", 0x57F287, [("Code", f"`{invite.code}`", True), ("Channel", invite.channel.mention if hasattr(invite.channel,'mention') else str(invite.channel), True), ("Created By", inviter.mention if inviter else "Unknown", True)], banner, thumb)
        await self.send_log(guild, "invite", embed)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        guild = invite.guild
        banner = guild.banner.url if guild and guild.banner else None
        embed = build_pro_embed(guild, None, "Invite Deleted", str(emojis.DELETE), f"Invite deleted", 0xED4245, [("Code", f"`{invite.code}`", True)], banner, guild.icon.url if guild and guild.icon else None)
        await self.send_log(guild, "invite", embed)

    COMMAND_TO_LOG = {
        "ban": "ban", "forceban": "ban", "guildban": "ban", "ownerban": "ban",
        "unban": "unban", "forceunban": "unban", "guildunban": "unban", "globalunban": "unban",
        "kick": "kick",
        "mute": "mute", "timeout": "mute",
        "unmute": "unwarn",
        "warn": "warn", "clearwarns": "warn",
        "unwarn": "unwarn",
        "nick": "nick",
    }

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if not ctx.guild:
            return
        banner = await _fetch_banner_url(self.bot, ctx.author, ctx.guild)
        cmd = str(ctx.command.qualified_name).lower() if ctx.command else "unknown"
        base = cmd.split()[0]
        dedicated = self.COMMAND_TO_LOG.get(base)
        if dedicated:
            embed = build_pro_embed(ctx.guild, ctx.author, f"Command: {cmd}", str(emojis.COMMANDS), f"Command `{cmd}` was used", 0x2B2D31, [("User", f"{ctx.author.mention}", True), ("Command", f"`{cmd}`", True), ("Channel", f"{ctx.channel.mention}", True), ("Content", f"`{ctx.message.content[:500]}`" if ctx.message.content else "None", False)], banner)
            await self.send_log(ctx.guild, dedicated, embed)
            return
        embed = build_pro_embed(ctx.guild, ctx.author, "Command Used", str(emojis.COMMANDS), f"Command `{ctx.command}` was used", 0x2B2D31, [("User", f"{ctx.author.mention}", True), ("Command", f"`{ctx.command}`", True), ("Channel", f"{ctx.channel.mention}", True)], banner)
        await self.send_log(ctx.guild, "command", embed)

    async def log_mod_action(self, guild: discord.Guild, log_type: str, user: discord.abc.User, title: str, emoji: str, color: int, fields: list, banner_url: str | None = None):
        embed = build_pro_embed(guild, user, title, emoji, f"> {title}", color, fields, banner_url or (guild.banner.url if guild.banner else None))
        await self.send_log(guild, log_type, embed)

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        embed = build_pro_embed(channel.guild, None, "Webhook Updated", str(emojis.GEAR), f"Webhook updated in {channel.mention}", 0x5865F2, [("Channel", channel.mention, True)], channel.guild.banner.url if channel.guild.banner else None, channel.guild.icon.url if channel.guild.icon else None)
        await self.send_log(channel.guild, "security", embed)

    @commands.Cog.listener()
    async def on_guild_emojis_update(self, guild, before, after):
        added = [e for e in after if e not in before]
        removed = [e for e in before if e not in after]
        for e in added:
            embed = build_pro_embed(guild, None, "Emoji Created", str(emojis.STAR), f"New emoji added", 0x57F287, [("Name", f"`{e.name}`", True)], guild.banner.url if guild.banner else None, e.url)
            await self.send_log(guild, "security", embed)
        for e in removed:
            embed = build_pro_embed(guild, None, "Emoji Deleted", str(emojis.DELETE), f"Emoji deleted", 0xED4245, [("Name", f"`{e.name}`", True)], guild.banner.url if guild.banner else None, guild.icon.url if guild.icon else None)
            await self.send_log(guild, "security", embed)


async def setup(bot):
    await bot.add_cog(Logging(bot))
