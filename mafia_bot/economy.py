"""Economy system — olmos, evro, shop, daily bonuses"""

import random
import logging
from datetime import datetime, timedelta

from .roles import Role, ROLE_PRICES
from .db import get_profile, save_profile

log = logging.getLogger("MafiaBot.Economy")

DAILY_OLMOS = 25
GAME_WIN_OLMOS = 15
GAME_LOSS_OLMOS = 5
GAME_WIN_EVRO = 3
GAME_LOSS_EVRO = 1
GIVEAWAY_MIN_OLMOS = 10
GIVEAWAY_MAX_OLMOS = 500
REFERRAL_BONUS = 50
WEEKLY_TOP1_OLMOS = 200
WEEKLY_TOP2_OLMOS = 100


def add_olmos(user_id: int, amount: int, name: str = "", username: str = "") -> dict:
    profile = get_profile(user_id, name, username)
    profile["olmos"] = profile.get("olmos", 0) + amount
    save_profile(user_id, profile)
    return profile


def add_evro(user_id: int, amount: int, name: str = "", username: str = "") -> dict:
    profile = get_profile(user_id, name, username)
    profile["evro"] = profile.get("evro", 0) + amount
    save_profile(user_id, profile)
    return profile


def spend_olmos(user_id: int, amount: int) -> bool:
    profile = get_profile(user_id)
    if profile.get("olmos", 0) < amount:
        return False
    profile["olmos"] -= amount
    save_profile(user_id, profile)
    return True


def spend_evro(user_id: int, amount: int) -> bool:
    profile = get_profile(user_id)
    if profile.get("evro", 0) < amount:
        return False
    profile["evro"] -= amount
    save_profile(user_id, profile)
    return True


def transfer_olmos(from_id: int, to_id: int, amount: int,
                   from_name: str = "", from_username: str = "",
                   to_name: str = "", to_username: str = "") -> bool:
    if amount < 1:
        return False
    profile_from = get_profile(from_id, from_name, from_username)
    if profile_from.get("olmos", 0) < amount:
        return False
    profile_to = get_profile(to_id, to_name, to_username)
    profile_from["olmos"] -= amount
    profile_to["olmos"] = profile_to.get("olmos", 0) + amount
    save_profile(from_id, profile_from)
    save_profile(to_id, profile_to)
    return True


def can_claim_daily(user_id: int) -> tuple[bool, int]:
    profile = get_profile(user_id)
    last = profile.get("last_daily")
    if not last:
        return True, 0
    try:
        last_time = datetime.fromisoformat(last)
        elapsed = (datetime.now() - last_time).total_seconds()
        remaining = max(0, 86400 - int(elapsed))
        return remaining == 0, remaining
    except (ValueError, TypeError):
        return True, 0


def claim_daily(user_id: int, name: str = "", username: str = "") -> tuple[int, int]:
    profile = get_profile(user_id, name, username)
    profile["olmos"] = profile.get("olmos", 0) + DAILY_OLMOS
    profile["evro"] = profile.get("evro", 0) + 2
    profile["last_daily"] = datetime.now().isoformat()
    save_profile(user_id, profile)
    return DAILY_OLMOS, 2


def get_role_price(role: Role) -> int:
    return ROLE_PRICES.get(role, 30)


def buy_role(user_id: int, role: Role) -> tuple[bool, str]:
    price = get_role_price(role)
    profile = get_profile(user_id)
    if profile.get("evro", 0) < price:
        return False, f"Sizda yetarli evro yo'q ({price}💶 kerak, sizda: {profile.get('evro', 0)}💶)"
    profile["evro"] -= price
    profile["bought_role"] = role.value
    save_profile(user_id, profile)
    return True, f"Siz {role.value} rolini {price}💶 ga sotib oldingiz!"


def game_reward(user_id: int, won: bool, name: str = "", username: str = "") -> dict:
    profile = get_profile(user_id, name, username)
    profile["games"] = profile.get("games", 0) + 1
    if won:
        profile["wins"] = profile.get("wins", 0) + 1
        profile["olmos"] = profile.get("olmos", 0) + GAME_WIN_OLMOS
        profile["evro"] = profile.get("evro", 0) + GAME_WIN_EVRO
    else:
        profile["losses"] = profile.get("losses", 0) + 1
        profile["olmos"] = profile.get("olmos", 0) + GAME_LOSS_OLMOS
        profile["evro"] = profile.get("evro", 0) + GAME_LOSS_EVRO
    save_profile(user_id, profile)
    return profile


def get_shop_text(user_id: int) -> str:
    profile = get_profile(user_id)
    olmos = profile.get("olmos", 0)
    evro = profile.get("evro", 0)
    bought = profile.get("bought_role")
    bought_text = bought if bought else "Yo'q"
    from .roles import TOWN_ROLES, MAFIA_ROLES, NEUTRAL_ROLES, ROLE_ICON
    lines = [
        "🛒 <b>ROLLAR DO'KONI</b>\n",
        f"💰 Hisobingiz: {olmos}💎 | {evro}💶\n",
        f"🎭 Sotib olingan rol: {bought_text}\n",
        f"\n🎮 <b>43 xil rol mavjud:</b>\n",
        f"🟢 Shahar: {len(TOWN_ROLES)} ta\n",
        f"🔴 Mafia: {len(MAFIA_ROLES)} ta\n",
        f"🟣 Mustaqil: {len(NEUTRAL_ROLES)} ta\n",
        "\n<b>Narxlar:</b>\n",
    ]
    for role in Role:
        price = ROLE_PRICES.get(role, 0)
        icon = "✅" if role.value == bought else ROLE_ICON.get(role, "❓")
        lines.append(f"{icon} {role.value} — {price}💶")
    return "\n".join(lines)
