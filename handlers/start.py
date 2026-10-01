from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import Database
from keyboards import main_menu

router = Router()

def membership_keyboard(db: Database):
    channel = db.setting('official_channel_id', '')
    link = db.setting('official_channel_link', '')
    if not link and channel.startswith('@'):
        link = 'https://t.me/' + channel[1:]
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text='📢 Rasmiy kanalga qo‘shilish', url=link)])
    rows.append([InlineKeyboardButton(text='🔄 Obunani tekshirish', callback_data='membership:check')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def is_member(message: Message, db: Database):
    if db.setting('membership_required', '0') != '1': return True
    channel = db.setting('official_channel_id', '').strip()
    if not channel: return True
    try:
        member = await message.bot.get_chat_member(channel, message.from_user.id)
        return member.status not in ('left', 'kicked')
    except Exception:
        # If mandatory membership is enabled, fail closed rather than bypassing it.
        return False

@router.message(CommandStart())
async def start(message: Message, db: Database):
    u = db.ensure_user(message.from_user)
    if u['blocked']:
        return await message.answer('⛔ Sizning hisobingiz bloklangan.')
    if not await is_member(message, db):
        return await message.answer(
            '🔐 <b>Botdan foydalanishdan oldin rasmiy kanalga obuna bo‘ling.</b>\n\n'
            '1️⃣ Kanalga qo‘shiling\n2️⃣ “Obunani tekshirish”ni bosing\n3️⃣ Shundan keyin barcha bo‘limlar ochiladi.',
            reply_markup=membership_keyboard(db), parse_mode='HTML')
    text = (
        f'🤖 <b>Kiro savdo bot</b> ga xush kelibsiz, {message.from_user.first_name}! 👋\n\n'
        '🛒 <b>JSON Market</b> — tayyor JSON mahsulotlaringizni sotish uchun\n'
        '💰 <b>Balans</b> — daromad va tranzaksiyalarni kuzating\n'
        '💸 <b>Pul chiqarish</b> — karta yoki telefon raqamiga pul oling\n'        '📦 <b>Sotuvlarim</b> — barcha JSON buyurtmalaringiz\n'
        '📜 <b>Tarix</b> — pul harakatlari\n'
        '💳 <b>Kartalarim</b> — kartani bir marta saqlang\n\n'
        '📌 <b>Qoidalar:</b> faqat o‘zingizga tegishli va sotishga haqqingiz bor JSON yuboring.\n\n'
        '👇 Kerakli bo‘limni tanlang:'
    )
    await message.answer(text, reply_markup=main_menu(), parse_mode='HTML')
