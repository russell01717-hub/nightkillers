"""Telegram Stars payment integration"""

from dataclasses import dataclass
from typing import Optional
from aiogram.types import LabeledPrice


@dataclass
class StarsPackage:
    olmos: int
    stars: int
    label: str

    def to_labeled_price(self) -> LabeledPrice:
        return LabeledPrice(label=self.label, amount=self.stars)


# 1 olmos = 3 Stars (base rate) with bulk discounts
STARS_PACKAGES = [
    StarsPackage(100, 300, "100 olmos"),
    StarsPackage(500, 1400, "500 olmos (7% bonus)"),
    StarsPackage(1000, 2700, "1000 olmos (10% bonus)"),
    StarsPackage(2500, 6000, "2500 olmos (20% bonus)"),
    StarsPackage(5000, 11000, "5000 olmos (27% bonus)"),
    StarsPackage(10000, 20000, "10000 olmos (33% bonus)"),
]


def get_package_by_stars(stars: int) -> Optional[StarsPackage]:
    for pkg in STARS_PACKAGES:
        if pkg.stars == stars:
            return pkg
    return None


def get_package_by_olmos(olmos: int) -> Optional[StarsPackage]:
    for pkg in STARS_PACKAGES:
        if pkg.olmos == olmos:
            return pkg
    return None


def calc_stars_for_olmos(olmos: int) -> int:
    """Base rate: 1 olmos = 3 Stars"""
    return max(3, olmos * 3)


def format_packages_text() -> str:
    lines = ["⭐ <b>Stars bilan to'lov paketlari</b>\n"]
    for pkg in STARS_PACKAGES:
        base_stars = pkg.olmos * 3  # 1 olmos = 3 Stars base
        if pkg.stars < base_stars:
            bonus_pct = int((base_stars - pkg.stars) / base_stars * 100)
            bonus = f" <b>-{bonus_pct}% chegirma</b>"
        elif pkg.stars > base_stars:
            bonus_pct = int((pkg.stars - base_stars) / base_stars * 100)
            bonus = f" <b>+{bonus_pct}% ortiqcha</b>"
        else:
            bonus = ""
        lines.append(f"⭐ {pkg.stars} XTR → {pkg.olmos} olmos{bonus}")
    lines.append("\n💡 To'lov uchun paketni tanlang va \"To'lash\" tugmasini bosing.")
    return "\n".join(lines)