import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
import os
from dotenv import load_dotenv

# Load token dan MongoDB URI dari .env
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
GUILD_ID = int(os.getenv("GUILD_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

# Role ID untuk Rank & Sekolah
WRETCH_ROLE_ID = int(os.getenv("WRETCH_ROLE_ID"))
GRIMWARD_ROLE_ID = int(os.getenv("GRIMWARD_ROLE_ID"))
RAVENSHIRE_ROLE_ID = int(os.getenv("RAVENSHIRE_ROLE_ID"))
GRAHANTA_ROLE_ID = int(os.getenv("GRAHANTA_ROLE_ID"))

# Koneksi MongoDB
client = MongoClient(MONGO_URI)
db = client["school_of_rebels"]
collection = db["students"]

RANKS = [
    ("Wretch", 0, 1355387300166766702),
    ("Ember", 50, 1355654614019477695),
    ("Seeker", 150, 1355654906723307601),
    ("Adept", 400, 1355655113946955899),
    ("Harbinger", 1000, 1355655268058402856),
    ("Sentinel", 2000, 1355655434194911303),
    ("Dominion", 4000, 1355655562947461320),
    ("Sovereign", 8000, 1355655788944949520),
    ("Ace", 500000, 1354566441101168640),
]

# Fungsi untuk mendapatkan kasta berdasarkan Student Points
def get_rank(points):
    for rank, min_points, _ in reversed(RANKS):
        if points >= min_points:
            return rank
    return "Wretch"

# Fungsi untuk mendapatkan nama role berdasarkan kasta
def get_role(rank):
    for r, _, role_name in RANKS:
        if r == rank:
            return role_name
    return None

# Aktifkan intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.members = True  # Untuk melihat member di server
intents.message_content = True  # Untuk membaca isi pesan

bot = commands.Bot(command_prefix="!", intents=intents)

# Saat bot siap
@bot.event
async def on_ready():
    print(f"✅ {bot.user} is now online!")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} commands!")
    except Exception as e:
        print(f"❌ Sync error: {e}")

# 📌 Fungsi untuk update role user saat naik kasta
async def update_role(member: discord.Member, new_rank: str):
    guild = member.guild
    new_role_name = get_role(new_rank)

    if new_role_name:
        new_role = discord.utils.get(guild.roles, name=new_role_name)
        if new_role:
            for r, _, role_name in RANKS:
                old_role = discord.utils.get(guild.roles, name=role_name)
                if old_role and old_role in member.roles and old_role != new_role:
                    await member.remove_roles(old_role)

            await member.add_roles(new_role)
            print(f"✅ {member.name} naik kasta menjadi {new_rank}, role {new_role_name} ditambahkan!")

# 📌 Command untuk menambahkan Student Points (Admin Only)
@bot.tree.command(name="add_points", description="Tambahkan Student Points ke pengguna (Admin Only)")
@app_commands.describe(member="Pilih pengguna", points="Jumlah Student Points yang akan ditambahkan")
async def add_points(interaction: discord.Interaction, member: discord.Member, points: int):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Kamu tidak memiliki izin untuk menggunakan perintah ini!", ephemeral=True)
        return

    user_data = collection.find_one({"user_id": member.id})
    if not user_data:
        await interaction.response.send_message("⚠️ Pengguna belum terdaftar dalam sistem!", ephemeral=True)
        return

    new_points = user_data["student_points"] + points
    new_rank = get_rank(new_points)
    collection.update_one({"user_id": member.id}, {"$set": {"student_points": new_points, "rank": new_rank}})
    await update_role(member, new_rank)

    await interaction.response.send_message(
        f"✅ **{points} Student Points** telah ditambahkan untuk {member.mention}!\n"
        f"📊 Total Student Points: **{new_points}**\n"
        f"🎖️ School Rank: **{new_rank}**"
    )

# 📌 Slash command untuk membuat sesi belajar (Admin Only)
@bot.tree.command(name="study", description="Buat atau selesaikan sesi belajar (Admin Only)")
@app_commands.describe(action="create (membuat) atau complete (menyelesaikan)", member="Pilih pengguna")
async def study(interaction: discord.Interaction, action: str, member: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Kamu tidak memiliki izin untuk menggunakan perintah ini!", ephemeral=True)
        return

    user_data = collection.find_one({"user_id": member.id})

    if not user_data:
        collection.insert_one({
            "user_id": member.id,
            "name": member.name,
            "student_points": 0,
            "rank": "Wretch",
            "active_study": False
        })
        user_data = collection.find_one({"user_id": member.id})

    if action.lower() == "create":
        if user_data["active_study"]:
            await interaction.response.send_message(f"⚠️ {member.mention} sudah memiliki sesi belajar yang aktif!", ephemeral=True)
            return
        
        collection.update_one({"user_id": member.id}, {"$set": {"active_study": True}})
        await interaction.response.send_message(f"📚 {member.mention} telah memulai sesi belajar!")

    elif action.lower() == "complete":
        if not user_data["active_study"]:
            await interaction.response.send_message(f"⚠️ {member.mention} belum memulai sesi belajar!", ephemeral=True)
            return

        points_gained = 10
        new_points = user_data["student_points"] + points_gained
        new_rank = get_rank(new_points)
        collection.update_one({"user_id": member.id}, {
            "$set": {"active_study": False, "student_points": new_points, "rank": new_rank}
        })

        await update_role(member, new_rank)

        await interaction.response.send_message(
            f"🎉 {member.mention} menyelesaikan sesi belajar dan mendapatkan **{points_gained} Student Points**!\n"
            f"📊 Total Student Points: **{new_points}**\n"
            f"🎖️ School Rank: **{new_rank}**"
        )

# 📌 Slash command untuk melihat leaderboard
@bot.tree.command(name="leaderboard", description="Lihat peringkat Student Points tertinggi")
async def leaderboard(interaction: discord.Interaction):
    top_students = collection.find().sort("student_points", -1).limit(10)
    leaderboard_text = "**🏆 Leaderboard Student Points 🏆**\n"

    rank = 1
    for student in top_students:
        leaderboard_text += f"**{rank}. {student['name']}** - {student['student_points']} Student Points ({student['rank']})\n"
        rank += 1

    await interaction.response.send_message(leaderboard_text)

# Slash Command: Register
@bot.tree.command(name="register", description="Daftar sebagai siswa baru")
@app_commands.describe(
    name="Masukkan nama karakter",
    gender="Pilih gender",
    age="Masukkan umur",
    school="Pilih sekolah"
)
@app_commands.choices(gender=[
    app_commands.Choice(name="Laki-laki", value="Laki-laki"),
    app_commands.Choice(name="Perempuan", value="Perempuan"),
    app_commands.Choice(name="Non-biner", value="Non-biner")
])
@app_commands.choices(school=[
    app_commands.Choice(name="Grimward Highschool", value="Grimward"),
    app_commands.Choice(name="Ravenshire Academy", value="Ravenshire"),
    app_commands.Choice(name="Grahanta Highschool", value="Grahanta")
])
async def register(interaction: discord.Interaction, name: str, gender: app_commands.Choice[str], age: int, school: app_commands.Choice[str]):
    user_id = interaction.user.id
    guild = interaction.guild
    member = guild.get_member(user_id)

    # Cek apakah sudah terdaftar
    existing_user = collection.find_one({"_id": user_id})
    if existing_user:
        await interaction.response.send_message("⚠ Kamu sudah terdaftar!", ephemeral=True)
        return

    # Simpan ke MongoDB
    collection.insert_one({
        "_id": user_id,
        "name": name,
        "gender": gender.value,
        "age": age,
        "school": school.value,
        "rank": "Wretch"
    })

    # Role Sekolah
    school_role = None
    if school.value == "Grimward":
        school_role = guild.get_role(GRIMWARD_ROLE_ID)
    elif school.value == "Ravenshire":
        school_role = guild.get_role(RAVENSHIRE_ROLE_ID)
    elif school.value == "Grahanta":
        school_role = guild.get_role(GRAHANTA_ROLE_ID)

    # Role Wretch (Rank Pemula)
    wretch_role = guild.get_role(WRETCH_ROLE_ID)

    # Tambahkan Role
    if school_role:
        await member.add_roles(school_role)
    await member.add_roles(wretch_role)

    # Kirim pesan ke channel umum
    channel = guild.get_channel(CHANNEL_ID)
    embed = discord.Embed(
        title="📜 Pendaftaran Siswa Baru",
        description=f"Selamat datang **{name}** di School of Rebels!\n\n"
                    f"**Nama:** {name}\n"
                    f"**Gender:** {gender.value}\n"
                    f"**Umur:** {age} tahun\n"
                    f"**Sekolah:** {school.value}\n"
                    f"**Rank:** Wretch\n\n"
                    f"**Semoga sukses dalam perjalananmu di sekolah ini!**",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Selamat datang di School of Rebels!")

    await channel.send(embed=embed)
    await interaction.response.send_message(f"✅ Pendaftaran berhasil, {interaction.user.mention}! Cek {channel.mention} untuk melihat pendaftaranmu.", ephemeral=True)

# Jalankan bot
bot.run(TOKEN)
