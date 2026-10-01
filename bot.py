import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import load_config, Config
from database import Database
from keyboards import main_menu
from handlers import start, user, json_market, withdrawals, admin, cards

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

async def main():
    config = load_config()
    db = Database()
    bot = Bot(config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    async def middleware(handler, event, data):
        data['db'] = db
        data['config'] = config
        if getattr(event, 'from_user', None):
            u = db.ensure_user(event.from_user)
            if u['blocked'] and event.from_user.id not in config.admin_ids:
                if isinstance(event, CallbackQuery):
                    await event.answer('⛔ Hisobingiz bloklangan.', show_alert=True)
                elif isinstance(event, Message):
                    await event.answer('⛔ Hisobingiz bloklangan.')
                return
            # The membership-check callback must always reach its own handler.
            is_membership_check = isinstance(event, CallbackQuery) and event.data == 'membership:check'
            is_public_command = isinstance(event, Message) and bool(event.text) and event.text.split()[0].split('@')[0] in ('/start', '/cancel')
            if (event.from_user.id not in config.admin_ids and not is_membership_check and not is_public_command
                    and db.setting('membership_required', '0') == '1'):
                channel = db.setting('official_channel_id', '').strip()
                if channel:
                    try:
                        member = await bot.get_chat_member(channel, event.from_user.id)
                        if member.status in ('left', 'kicked'):
                            link = db.setting('official_channel_link', '').strip()
                            if not link and channel.startswith('@'):
                                link = 'https://t.me/' + channel[1:]
                            buttons = []
                            if link:
                                buttons.append([InlineKeyboardButton(text='📢 Rasmiy kanalga qo‘shilish', url=link)])
                            buttons.append([InlineKeyboardButton(text='🔄 Obunani tekshirish', callback_data='membership:check')])
                            kb = InlineKeyboardMarkup(inline_keyboard=buttons)
                            if isinstance(event, CallbackQuery):
                                await event.message.answer('🔐 Avval rasmiy kanalga obuna bo‘ling.', reply_markup=kb)
                                await event.answer()
                            elif isinstance(event, Message):
                                await event.answer('🔐 Avval rasmiy kanalga obuna bo‘ling.', reply_markup=kb)
                            return
                    except Exception:
                        # Configuration/permission issues are logged but never crash the bot.
                        logger.warning('Majburiy obuna tekshiruvida xato', exc_info=True)
        return await handler(event, data)

    dp.message.middleware(middleware)
    dp.callback_query.middleware(middleware)
    dp.include_router(start.router)
    dp.include_router(user.router)
    dp.include_router(json_market.router)
    dp.include_router(cards.router)
    dp.include_router(withdrawals.router)
    dp.include_router(admin.router)

    @dp.callback_query(F.data == 'membership:check')
    async def membership_check(c: CallbackQuery, db: Database, config: Config):
        if c.from_user.id in config.admin_ids:
            return await c.answer('Admin uchun cheklov yo‘q.')
        channel = db.setting('official_channel_id', '').strip()
        if not channel:
            return await c.answer('⚠️ Kanal hali sozlanmagan.', show_alert=True)
        try:
            member = await c.bot.get_chat_member(channel, c.from_user.id)
            if member.status not in ('left', 'kicked'):
                await c.message.answer('✅ Obuna tasdiqlandi. Endi botdan foydalanishingiz mumkin.', reply_markup=main_menu())
                return await c.answer('✅ Tasdiqlandi')
        except Exception:
            return await c.answer('⚠️ Kanalni tekshirishda xatolik. Bot kanal admini ekanini tekshiring.', show_alert=True)
        await c.answer('❌ Hali obuna aniqlanmadi.', show_alert=True)

    @dp.message(Command('cancel'))
    async def cancel(m: Message, state):
        await state.clear()
        await m.answer('❌ Amal bekor qilindi.', reply_markup=main_menu())

    @dp.callback_query(F.data == 'fsm:cancel')
    async def cancel_callback(c: CallbackQuery, state):
        await state.clear()
        await c.message.answer('❌ Amal bekor qilindi.', reply_markup=main_menu())
        await c.answer('Bekor qilindi')

    await bot.set_my_commands([
        BotCommand(command='start', description='Botni boshlash'),
        BotCommand(command='cancel', description='Joriy amalni bekor qilish'),
        BotCommand(command='admin', description='Admin panel')
    ])
    logger.info('Kiro savdo bot ishga tushmoqda...')
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info('Bot to‘xtatildi.')
    except Exception:
        logger.exception('Fatal error')
        raise
