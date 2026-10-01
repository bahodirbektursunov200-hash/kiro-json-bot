# Kiro Savdo Bot — Final Test

Telegram bot built with Python + aiogram 3.x + SQLite.

## Main features
- JSON Marketplace with Power / Pro / Pro Max and admin-managed plans
- JSON input as text or `.json` document
- Strong JSON validation: duplicate keys, NaN/Infinity, depth and size checks
- Admin-managed payment methods (Click, Payme, Paynet, Uzum or custom)
- Withdrawal flow with Processing / Paid / Rejected states
- User saved cards: add, view, delete; no CVV/PIN/SMS codes are stored
- Transaction history
- Mandatory official-channel subscription switch
- SQLite migrations and backup
- Double-approval protection and status transition checks

## Setup
1. Copy `.env.example` to `.env`.
2. Fill `BOT_TOKEN` and `ADMIN_IDS`.
3. Install:
   `python -m pip install -r requirements.txt`
4. Run:
   `python bot.py`

## Important
The bot does not implement automatic Click/Payme/Uzum gateway APIs. Payment methods are manually configured in the admin panel and payment proofs are reviewed by admins.

For mandatory subscription, configure the official channel ID/link and make the bot an administrator of the channel so `get_chat_member` can verify membership.
