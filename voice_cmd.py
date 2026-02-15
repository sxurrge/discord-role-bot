import discord
from discord.ext import commands

# =========================
# 必ず変更する設定
# =========================
VOICE_CATEGORY_ID = 1330098326820884513  # ←あなたのカテゴリIDに変更


# =========================
# VC作成モーダル
# =========================
class VoiceCreateModal(discord.ui.Modal, title="VC作成フォーム"):
    vc_name = discord.ui.TextInput(
        label="通話名（必須）",
        placeholder="例: 雑談部屋",
        required=True,
        max_length=32
    )

    user_limit = discord.ui.TextInput(
        label="人数制限（0〜99 / 空欄で無制限）",
        placeholder="例: 3",
        required=False,
        max_length=2
    )

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=300)
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        # ---- 入力値チェック ----
        name = str(self.vc_name.value).strip()
        if not name:
            await interaction.response.send_message("通話名は必須です。", ephemeral=True)
            return

        limit_raw = str(self.user_limit.value).strip()
        if limit_raw == "":
            limit = 0
        else:
            if not limit_raw.isdigit():
                await interaction.response.send_message("人数制限は数字で入力してください。", ephemeral=True)
                return
            limit = int(limit_raw)
            if not (0 <= limit <= 99):
                await interaction.response.send_message("人数制限は0〜99で入力してください。", ephemeral=True)
                return

        # ---- カテゴリ確認 ----
        category = guild.get_channel(VOICE_CATEGORY_ID)
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                "カテゴリIDが無効です。voice_cmd.py の VOICE_CATEGORY_ID を確認してください。",
                ephemeral=True
            )
            return

        # ---- ここで「限定メンバー選択UI」へ進む ----
        await interaction.response.send_message(
            "✅ 基本設定を受け取りました。\n"
            "次に、限定メンバーを設定する場合は下のセレクトで選択してください。\n"
            "制限なしにする場合はそのまま「VC作成」を押してください。",
            view=FinalizeCreateView(
                bot=self.bot,
                creator_id=interaction.user.id,
                vc_name=name,
                user_limit=limit,
                category_id=category.id
            ),
            ephemeral=True
        )


# =========================
# 作成前の最終設定View（メンバーセレクト + 作成ボタン）
# =========================
class FinalizeCreateView(discord.ui.View):
    def __init__(self, bot: commands.Bot, creator_id: int, vc_name: str, user_limit: int, category_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.creator_id = creator_id
        self.vc_name = vc_name
        self.user_limit = user_limit
        self.category_id = category_id
        self.selected_user_ids: set[int] = set()

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="限定メンバーを選択（複数可 / 未選択なら制限なし）",
        min_values=0,
        max_values=25,
        custom_id="voice_select_allowed_users"
    )
    async def select_users(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
            return

        self.selected_user_ids = {u.id for u in select.values}
        if self.selected_user_ids:
            names = ", ".join([u.display_name for u in select.values])
            await interaction.response.send_message(f"限定メンバーを設定: {names}", ephemeral=True)
        else:
            await interaction.response.send_message("限定メンバー設定を解除（制限なし）しました。", ephemeral=True)

    @discord.ui.button(label="VC作成", style=discord.ButtonStyle.success, custom_id="voice_finalize_create")
    async def create_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("この操作はコマンド実行者のみ可能です。", ephemeral=True)
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        category = guild.get_channel(self.category_id)
        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("カテゴリが見つかりません。", ephemeral=True)
            return

        # ---- 限定メンバー権限 ----
        overwrites_dict = None
        allowed_users = []

        if self.selected_user_ids:
            allowed_users = [guild.get_member(uid) for uid in self.selected_user_ids]
            allowed_users = [m for m in allowed_users if m is not None]

            overwrites_dict = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True, connect=True),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True, connect=True, manage_channels=True, move_members=True
                )
            }
            for m in allowed_users:
                overwrites_dict[m] = discord.PermissionOverwrite(view_channel=True, connect=True)

        # ---- VC作成 ----
        try:
            kwargs = {
                "name": self.vc_name,
                "category": category,
                "user_limit": self.user_limit,
                "reason": f"Created by {interaction.user} via !voice"
            }
            if overwrites_dict:
                kwargs["overwrites"] = overwrites_dict

            vc = await guild.create_voice_channel(**kwargs)

        except discord.Forbidden:
            await interaction.response.send_message(
                "Botにチャンネル作成権限がありません。（Manage Channels などを確認）",
                ephemeral=True
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Discord側エラーで作成に失敗しました: {e}",
                ephemeral=True
            )
            return

        # ---- 作成完了（ephemeral）----
        summary_lines = [
            f"✅ VCを作成しました: **{vc.name}**",
            f"・カテゴリ: **{category.name}**",
            f"・人数制限: {'なし' if self.user_limit == 0 else str(self.user_limit) + '人'}",
            f"・限定メンバー: {'なし' if not allowed_users else ', '.join([m.display_name for m in allowed_users])}",
        ]
        await interaction.response.send_message("\n".join(summary_lines), ephemeral=True)

        # ---- 公開メッセージで削除ボタンを送信（ワンクリック削除）----
        try:
            channel = interaction.channel
            if channel:
                embed = discord.Embed(
                    title="VC管理パネル",
                    description=f"対象VC: **{vc.name}**\n下のボタンで削除できます。",
                    color=discord.Color.red()
                )
                await channel.send(
                    embed=embed,
                    view=VoiceDeleteView(target_vc_id=vc.id, creator_id=self.creator_id)
                )
        except discord.HTTPException:
            pass


# =========================
# VC削除View
# =========================
class VoiceDeleteView(discord.ui.View):
    def __init__(self, target_vc_id: int, creator_id: int):
        super().__init__(timeout=None)
        self.target_vc_id = target_vc_id
        self.creator_id = creator_id

    @discord.ui.button(label="このVCを削除", style=discord.ButtonStyle.danger, custom_id="voice_delete_channel")
    async def delete_vc(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("サーバー内で実行してください。", ephemeral=True)
            return

        # 作成者 or 管理者のみ
        is_admin = interaction.user.guild_permissions.manage_channels
        if interaction.user.id != self.creator_id and not is_admin:
            await interaction.response.send_message("この削除ボタンは作成者または管理者のみ使用できます。", ephemeral=True)
            return

        vc = guild.get_channel(self.target_vc_id)
        if vc is None or not isinstance(vc, discord.VoiceChannel):
            await interaction.response.send_message("対象VCはすでに存在しません。", ephemeral=True)
            return

        try:
            vc_name = vc.name
            await vc.delete(reason=f"Deleted by {interaction.user}")
            await interaction.response.send_message(f"🗑️ VC **{vc_name}** を削除しました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("VC削除権限がありません。", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Discord側エラーで削除できませんでした。", ephemeral=True)


# =========================
# !voice で最初に出すパネル
# =========================
class VoiceCreateView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="VC作成フォームを開く",
        style=discord.ButtonStyle.primary,
        custom_id="voice_create_open_modal"
    )
    async def open_modal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceCreateModal(self.bot))


# =========================
# Cog本体
# =========================
class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="voice")
    @commands.has_permissions(manage_channels=True)
    async def voice(self, ctx: commands.Context):
        # コマンドメッセージを削除（できなければ無視）
        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        embed = discord.Embed(
            title="VC作成",
            description="下のボタンからフォームを開いて入力してください。",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed, view=VoiceCreateView(self.bot))

    @voice.error
    async def voice_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("このコマンドには `チャンネルの管理` 権限が必要です。")
        else:
            await ctx.send("`!voice` の実行中にエラーが発生しました。")
            print("[voice_error]", repr(error))


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
