import os
from dotenv import load_dotenv

load_dotenv()
import discord
from discord.ext import commands

import sqlite3
import random
import smtplib
import asyncio

from email.mime.text import MIMEText

# =====================
# 기본 설정
# =====================

TOKEN = os.getenv("DISCORD_TOKEN")
EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# 인증 코드 저장 (메모리)
verify_codes = {}

# =====================
# DB 설정
# =====================

conn = sqlite3.connect("settings.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    role_id INTEGER
)
""")

conn.commit()

# =====================
# 이메일 전송 함수
# =====================

def send_email(to_email, code):
    try:
        msg = MIMEText(f"""
안녕하세요.

Discord 인증 코드입니다.

인증 코드: {code}

감사합니다.
""")

        msg["Subject"] = "Discord 인증 코드"
        msg["From"] = EMAIL
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL, EMAIL_PASSWORD)

        server.sendmail(EMAIL, to_email, msg.as_string())
        server.quit()

        print(f"[메일 전송 성공] {to_email}")
        return True

    except Exception as e:
        print(f"[메일 전송 실패] {e}")
        return False


# =====================
# 슬래시 명령어: 역할 설정
# =====================

@bot.tree.command(name="설정", description="인증 역할 설정")
async def set_role(interaction: discord.Interaction, role: discord.Role):

    cursor.execute("""
        REPLACE INTO guild_settings (guild_id, role_id)
        VALUES (?, ?)
    """, (interaction.guild.id, role.id))

    conn.commit()

    await interaction.response.send_message(
        f"인증 역할이 {role.mention} 로 설정되었습니다.",
        ephemeral=True
    )


# =====================
# 슬래시 명령어: 인증 요청
# =====================

@bot.tree.command(name="인증", description="이메일 인증")
async def verify(interaction: discord.Interaction, email: str):

    await interaction.response.defer(ephemeral=True)

    code = str(random.randint(100000, 999999))

    success = await asyncio.to_thread(send_email, email, code)

    if not success:
        await interaction.followup.send(
            "이메일 전송 실패",
            ephemeral=True
        )
        return

    verify_codes[interaction.user.id] = (code, email)

    await interaction.followup.send(
        "인증 코드가 이메일로 전송되었습니다.",
        ephemeral=True
    )


# =====================
# 슬래시 명령어: 인증 확인
# =====================

@bot.tree.command(name="확인", description="인증 코드 확인")
async def check(interaction: discord.Interaction, code: str):

    if interaction.user.id not in verify_codes:
        await interaction.response.send_message(
            "먼저 /인증 을 진행해주세요.",
            ephemeral=True
        )
        return

    saved_code, email = verify_codes[interaction.user.id]

    if code != saved_code:
        await interaction.response.send_message(
            "인증 코드가 틀렸습니다.",
            ephemeral=True
        )
        return

    cursor.execute("""
        SELECT role_id FROM guild_settings
        WHERE guild_id = ?
    """, (interaction.guild.id,))

    result = cursor.fetchone()

    if result is None:
        await interaction.response.send_message(
            "관리자가 인증 역할을 설정하지 않았습니다.",
            ephemeral=True
        )
        return

    role = interaction.guild.get_role(result[0])

    if role is None:
        await interaction.response.send_message(
            "설정된 역할을 찾을 수 없습니다.",
            ephemeral=True
        )
        return

    try:
        await interaction.user.add_roles(role, reason="이메일 인증 완료")

        del verify_codes[interaction.user.id]

        await interaction.response.send_message(
            "✅ 인증 완료!",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.response.send_message(
            "봇 권한이 부족합니다. 역할 순서를 확인하세요.",
            ephemeral=True
        )

    except Exception as e:
        await interaction.response.send_message(
            f"오류 발생: {e}",
            ephemeral=True
        )


# =====================
# 봇 준비 완료
# =====================

@bot.event
async def on_ready():
    try:
        synced = await bot.tree.sync()
        print(f"{bot.user} 로그인 완료")
        print(f"슬래시 명령어 {len(synced)}개 동기화 완료")

    except Exception as e:
        print(f"동기화 실패: {e}")


# =====================
# 실행
# =====================

bot.run(TOKEN)