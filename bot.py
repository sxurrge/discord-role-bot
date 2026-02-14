import discord
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== ロールID =====
ROLE_IDS = [
    138778843503190158,
    1387816535434858637,
    1388039425279135795,
    1390003299834396699,
    1390003760197271762,
    1390004720499818496,
    1392820295068422245,
    1392837215171776633,
    1392871383230320800,
    1392871928200433737,
    1445846746319032424,
    1392872271588102246,
    1392872788246663379,
    1393275761179361290,
    1393276526501302382,
    1398246536802209812,
    1426283298921119815,
]

# =============================

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        for index, role_id in enumerate(ROLE_IDS):
            button = discord.ui.Button(
                label="loading...",
                style=discord.ButtonStyle.secondary,
                custom_id=f"role_button_{role_id}",
                row=index // 5
            )

            button.callback = self.generate_callback(role_id)
            self.add_item(button)

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        for index, role_id in enumerate(ROLE_IDS):
            button = discord.ui.Button(
                label="loading...",
                style=discord.ButtonStyle.secondary,
                custom_id=f"role_button_{role_id}",
                row=index // 5
            )
            button.callback = self.generate_callback(role_id)
            self.add_item(button)

    # ← ここがクラスの中に入ってるのが超重要
    def generate_callback(self, role_id):

        async def callback(interaction: discord.Interaction):

            guild = interaction.guild
            member = interaction.user

            selected_role = guild.get_role(role_id)
            if not selected_role:
                return

            # 🔥 今持っている対象ロールを全部削除（選択以外）
            roles_to_remove = [
                role for role in member.roles
                if role.id in ROLE_IDS and role.id != role_id
            ]

            if roles_to_remove:
                await member.remove_roles(*roles_to_remove)

            # 🔥 選択ロール付与
            if selected_role not in member.roles:
                await member.add_roles(selected_role)

            # 🔥 無言処理
            await interaction.response.defer()

        return callback


@bot.event
async def on_ready():
    bot.add_view(RoleView())
    print(f"ログインしました: {bot.user}")


# ===== コマンド =====
@bot.command()
async def arise(ctx):

    await ctx.message.delete()

    embed = discord.Embed(
        title="ロール選択",
        description="下のボタンを押してロールを切り替えてください。",
        color=discord.Color.blue()
    )

    view = RoleView()

    # ボタンラベルをロール名に変更
    for item in view.children:
        role_id = int(item.custom_id.split("_")[-1])
        role = ctx.guild.get_role(role_id)
        if role:
            item.label = role.name

    await ctx.send(embed=embed, view=view)


import os
bot.run(os.getenv("DISCORD_TOKEN"))

