"""Telegram Stars payment handlers"""

import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, LabeledPrice
from aiogram.filters import Command

from ..config import STARS_PER_OLMOS
from ..db import get_profile
from ..economy import add_olmos
from ..payments.stars import STARS_PACKAGES, get_package_by_stars, format_packages_text
from ..game_engine import safe_edit_message

log = logging.getLogger("MafiaBot.Payments.Stars")

router = Router(name="stars_payments")


@router.message(Command("pay_stars"))
async def cmd_pay_stars(message: Message, bot: Bot):
    if message.chat.type != "private":
        await message.answer("❌ Bu buyruq faqat shaxsiy chatda ishlaydi.")
        return

    text = format_packages_text()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    kb = InlineKeyboardBuilder()
    for pkg in STARS_PACKAGES:
        kb.button(text=f"⭐ {pkg.stars} XTR → {pkg.olmos} olmos", callback_data=f"stars_buy:{pkg.stars}")
    kb.button(text="◀️ Ortga", callback_data="start_back")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data == "pay_stars")
async def callback_pay_stars(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    text = format_packages_text()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton

    kb = InlineKeyboardBuilder()
    for pkg in STARS_PACKAGES:
        kb.button(text=f"⭐ {pkg.stars} XTR → {pkg.olmos} olmos", callback_data=f"stars_buy:{pkg.stars}")
    kb.button(text="◀️ Ortga", callback_data="start_back")
    kb.adjust(1)

    await safe_edit_message(bot, callback.message.chat.id, callback.message.message_id, text, reply_markup=kb.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("stars_buy:"))
async def handle_stars_buy(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    try:
        stars = int(callback.data.split(":")[1])
    except (IndexError, ValueError):
        await callback.message.answer("❌ Noto'g'ri paket.")
        return

    pkg = next((p for p in STARS_PACKAGES if p.stars == stars), None)
    if not pkg:
        await callback.message.answer("❌ Paket topilmadi.")
        return

    prices = [LabeledPrice(label=pkg.label, amount=stars)]

    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"Night Killers — {pkg.olmos} olmos",
        description=f"{pkg.olmos} olmos sotib olish uchun {stars} XTR to'lov",
        payload=f"stars_olmos_{pkg.olmos}_{callback.from_user.id}",
        provider_token="",  # Stars uchun bo'sh
        currency="XTR",
        prices=prices,
        start_parameter=f"stars_{pkg.olmos}",
        need_name=False,
        need_phone_number=False,
        need_email=False,
        need_shipping_address=False,
        is_flexible=False,
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout: PreCheckoutQuery, bot: Bot):
    await pre_checkout.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, bot: Bot):
    payment = message.successful_payment
    if payment.currency != "XTR":
        return

    try:
        payload_parts = payment.invoice_payload.split("_")
        if len(payload_parts) >= 3 and payload_parts[0] == "stars" and payload_parts[1] == "olmos":
            olmos = int(payload_parts[2])
            user_id = int(payload_parts[3]) if len(payload_parts) > 3 else message.from_user.id
        else:
            olmos = payment.total_amount * 100  # fallback
            user_id = message.from_user.id
    except (ValueError, IndexError):
        olmos = payment.total_amount * 100
        user_id = message.from_user.id

    add_olmos(user_id, olmos)
    profile = get_profile(user_id)

    await message.answer(
        f"✅ <b>To'lov muvaffaqiyatli!</b>\n\n"
        f"⭐ {payment.total_amount} XTR to'landi\n"
        f"💎 +{olmos} olmos hisobingizga qo'shildi\n"
        f"💰 Jami: {profile.get('olmos', 0)} olmos",
        parse_mode="HTML"
    )
    log.info(f"Stars payment: user={user_id}, stars={payment.total_amount}, olmos={olmos}")