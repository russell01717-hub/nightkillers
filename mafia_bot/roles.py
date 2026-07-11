from enum import Enum


class GamePhase(str, Enum):
    WAITING = "waiting"
    STARTING = "starting"
    ROLE_ASSIGN = "role_assign"
    NIGHT = "night"
    MORNING = "morning"
    VOTING = "voting"
    EXECUTION = "execution"
    ENDED = "ended"


class Team(str, Enum):
    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"

    @property
    def display(self) -> str:
        return {"town": "🟢 Shahar", "mafia": "🔴 Mafia", "neutral": "🟣 Mustaqil"}[self.value]


class Role(str, Enum):
    # ── Town ──
    TINCH = "Tinch aholi"
    KOMISSAR = "Komissar"
    DOKTOR = "Doktor"
    QORIQCHI = "Qo'riqchi"
    KUZATUVCHI = "Kuzatuvchi"
    IZQUVAR = "Izquvar"
    TERGOVCHI = "Tergovchi"
    MER = "Mer"
    VETERAN = "Veteran"
    VIGILANTE = "Vigilante"
    HAMSHIRA = "Hamshira"
    MEDIUM = "Medium"
    PSIXOLOG = "Psixolog"
    MUHANDIS = "Muhandis"
    DETEKTIV = "Detektiv"
    SPY = "Spy"
    JAILOR = "Jailor"
    ORACLE = "Oracle"
    PRIEST = "Priest"
    TRANSPORTER = "Transporter"
    ADVOKAT = "Advokat"
    SHERIF = "Sherif"

    # ── Mafia ──
    MAFIA = "Mafia"
    DON = "Don"
    CONSIGLIERE = "Consigliere"
    FRAMER = "Framer"
    JANITOR = "Janitor"
    SILENCER = "Silencer"
    BLACKMAILER = "Blackmailer"
    ROLEBLOCKER = "Roleblocker"
    FORGER = "Forger"
    GODFATHER = "Godfather"

    # ── Neutral ──
    MANIYAK = "Maniyak"
    JOKER = "Joker"
    ARSONIST = "Arsonist"
    EXECUTIONER = "Executioner"
    WITCH = "Witch"
    SURVIVOR = "Survivor"
    AMNESIAC = "Amnesiac"
    ASSASSIN = "Assassin"
    BOMBER = "Bomber"
    POISONER = "Poisoner"
    PROFESSIONAL = "Professional"


ROLE_ICON = {
    Role.TINCH: "👤", Role.KOMISSAR: "🔍", Role.DOKTOR: "💊",
    Role.QORIQCHI: "🛡", Role.KUZATUVCHI: "👁", Role.IZQUVAR: "🔎",
    Role.TERGOVCHI: "📋", Role.MER: "👔", Role.VETERAN: "🎖",
    Role.VIGILANTE: "🔫", Role.HAMSHIRA: "🏥", Role.MEDIUM: "🔮",
    Role.PSIXOLOG: "🧠", Role.MUHANDIS: "⚙️", Role.DETEKTIV: "🕵️",
    Role.SPY: "🕶", Role.JAILOR: "⛓", Role.ORACLE: "🔯",
    Role.PRIEST: "✝️", Role.TRANSPORTER: "🔄", Role.ADVOKAT: "⚖️",
    Role.SHERIF: "⭐",
    Role.MAFIA: "🔪", Role.DON: "👑", Role.CONSIGLIERE: "📜",
    Role.FRAMER: "🎭", Role.JANITOR: "🧹", Role.SILENCER: "🤐",
    Role.BLACKMAILER: "📨", Role.ROLEBLOCKER: "🔒", Role.FORGER: "✒️",
    Role.GODFATHER: "💀",
    Role.MANIYAK: "🪓", Role.JOKER: "🃏", Role.ARSONIST: "🔥",
    Role.EXECUTIONER: "🪓", Role.WITCH: "🧙", Role.SURVIVOR: "⛺",
    Role.AMNESIAC: "❓", Role.ASSASSIN: "🗡", Role.BOMBER: "💣",
    Role.POISONER: "☠️", Role.PROFESSIONAL: "🎯",
}

ROLE_DISPLAY = {r: f"{ROLE_ICON.get(r, '❓')} {r.value}" for r in Role}

ROLE_TEAM = {
    Role.TINCH: "town", Role.KOMISSAR: "town", Role.DOKTOR: "town",
    Role.QORIQCHI: "town", Role.KUZATUVCHI: "town", Role.IZQUVAR: "town",
    Role.TERGOVCHI: "town", Role.MER: "town", Role.VETERAN: "town",
    Role.VIGILANTE: "town", Role.HAMSHIRA: "town", Role.MEDIUM: "town",
    Role.PSIXOLOG: "town", Role.MUHANDIS: "town", Role.DETEKTIV: "town",
    Role.SPY: "town", Role.JAILOR: "town", Role.ORACLE: "town",
    Role.PRIEST: "town", Role.TRANSPORTER: "town", Role.ADVOKAT: "town",
    Role.SHERIF: "town",
    Role.MAFIA: "mafia", Role.DON: "mafia", Role.CONSIGLIERE: "mafia",
    Role.FRAMER: "mafia", Role.JANITOR: "mafia", Role.SILENCER: "mafia",
    Role.BLACKMAILER: "mafia", Role.ROLEBLOCKER: "mafia", Role.FORGER: "mafia",
    Role.GODFATHER: "mafia",
    Role.MANIYAK: "neutral", Role.JOKER: "neutral", Role.ARSONIST: "neutral",
    Role.EXECUTIONER: "neutral", Role.WITCH: "neutral", Role.SURVIVOR: "neutral",
    Role.AMNESIAC: "neutral", Role.ASSASSIN: "neutral", Role.BOMBER: "neutral",
    Role.POISONER: "neutral", Role.PROFESSIONAL: "neutral",
}

ROLE_DESC = {
    Role.TINCH: "Tun bo'yi uxlaysiz. Kunning yorishini kutasiz.",
    Role.KOMISSAR: "Tun bo'yi bir o'yinchini tekshirib, mafiya yoki tinch ekanligini bilasiz.",
    Role.DOKTOR: "Tun bo'yi bir o'yinchini davolaysiz. Mafiya o'sha odamni otsa tirik qoladi.",
    Role.QORIQCHI: "Tun bo'yi bir o'yinchini himoya qilasiz. Agar hujum bo'lsa, siz o'lasiz.",
    Role.KUZATUVCHI: "Kechasi kim sizning nishoningizga tashrif buyurganini kuzatasiz.",
    Role.IZQUVAR: "Kechasi bir o'yinchini kuzatib, u kimga borganini bilasiz.",
    Role.TERGOVCHI: "Kechasi bir o'yinchining rolini aniqlaysiz (3 xil natija).",
    Role.MER: "Ovozingiz 3 ta hisoblanadi. Kechasi himoyasiz.",
    Role.VETERAN: "Kechasi hujum rejimiga o'tishingiz mumkin. Sizga hujum qilgan o'ladi.",
    Role.VIGILANTE: "Kechasi bir o'yinchini otishingiz mumkin. Agar begunoh bo'lsa, o'zingiz o'lasiz.",
    Role.HAMSHIRA: "Doktorga yordamchi. Bir marta o'lgan o'yinchini tiriltira oladi.",
    Role.MEDIUM: "O'lgan o'yinchilar bilan kechasi gaplasha olasiz.",
    Role.PSIXOLOG: "Bir o'yinchining psixologik holatini tekshirib, uning roli haqida ma'lumot olasiz.",
    Role.MUHANDIS: "Kechasi bir o'yinchining uyiga kuzatuv qurilmasi o'rnatasiz.",
    Role.DETEKTIV: "Kechasi bir o'yinchining aybdor yoki begunoh ekanligini bilasiz.",
    Role.SPY: "Mafiya a'zolarining kim bilan gaplashayotganini eshitasiz.",
    Role.JAILOR: "Kechasi bir o'yinchini qamoqqa tashlaysiz va ular bilan gaplashasiz.",
    Role.ORACLE: "Kechasi bir o'yinchining o'lim haqidagi ma'lumotini olasiz.",
    Role.PRIEST: "Kechasi bir o'yinchini himoya qilasiz. U sehrli himoyada bo'ladi.",
    Role.TRANSPORTER: "Kechasi ikki o'yinchining o'rnini almashtirasiz.",
    Role.ADVOKAT: "Kunduzi bir o'yinchini himoya qilib, uni ovoz berishdan qutqarasiz.",
    Role.SHERIF: "Mafiya sizni otmoqchi bo'lsa, ulardan biri ham o'ladi.",
    Role.MAFIA: "Kechasi mafiya a'zolari bilan birgalikda kimni o'ldirishni tanlaysiz.",
    Role.DON: "Mafiya boshlig'i. Ovozingiz hal qiluvchi. Komissar sizni tekshirganda begunoh ko'rinasiz.",
    Role.CONSIGLIERE: "Kechasi bir o'yinchining rolini bilib olasiz va mafiyaga xabar berasiz.",
    Role.FRAMER: "Kechasi bir o'yinchini framer qilib, tergovchiga yolg'on natija ko'rsatasiz.",
    Role.JANITOR: "Kechasi o'lgan o'yinchining rolini yashirasiz.",
    Role.SILENCER: "Kechasi bir o'yinchini ovozsiz qoldirasiz (kunduzi gapira olmaydi).",
    Role.BLACKMAILER: "Kechasi bir o'yinchini shantaj qilib, uni ovoz berishdan to'xtatasiz.",
    Role.ROLEBLOCKER: "Kechasi bir o'yinchining harakatini bloklaysiz.",
    Role.FORGER: "Kechasi bir o'yinchining rol ma'lumotini o'zgartiradi.",
    Role.GODFATHER: "Mafiya rahbari. Komissar va tergovchi sizni begunoh deb topadi.",
    Role.MANIYAK: "Kechasi bir o'yinchini o'ldirasiz. Yolg'iz qolish orqali yutasiz.",
    Role.JOKER: "Kunduzi ovoz berish orqali chiqarilishni xohlaysiz. Chiqarilsangiz yutasiz.",
    Role.ARSONIST: "Kechasi o'yinchilarni benzin bilan sepib, keyingi tun yoqib yuborasiz.",
    Role.EXECUTIONER: "Kunduzi bir o'yinchini chiqarilishiga erishishingiz kerak.",
    Role.WITCH: "Kechasi bir o'yinchini boshqarib, uning harakatini o'zgartirasiz.",
    Role.SURVIVOR: "Maqsadingiz — tirik qolish. Hech kim sizni o'ldira olmaydi.",
    Role.AMNESIAC: "Kechasi bir o'lgan o'yinchining rolini eslab, shu rolga aylanasiz.",
    Role.ASSASSIN: "Kechasi bir o'yinchini o'ldirasiz. Har 2 tunda 1 marta.",
    Role.BOMBER: "Kechasi bir o'yinchining uyiga bomba o'rnatasiz. Keyingi tun portlaydi.",
    Role.POISONER: "Kechasi bir o'yinchini zaharlaysiz. U ertasi kuni o'ladi.",
    Role.PROFESSIONAL: "Kechasi bir o'yinchini o'ldirasiz. Agar noto'g'ri o'ldirsangiz, o'zingiz o'lasiz.",
}

ROLE_PRICES = {
    Role.TINCH: 5, Role.KOMISSAR: 60, Role.DOKTOR: 50, Role.QORIQCHI: 55,
    Role.KUZATUVCHI: 40, Role.IZQUVAR: 45, Role.TERGOVCHI: 50, Role.MER: 80,
    Role.VETERAN: 65, Role.VIGILANTE: 60, Role.HAMSHIRA: 45, Role.MEDIUM: 35,
    Role.PSIXOLOG: 40, Role.MUHANDIS: 50, Role.DETEKTIV: 55, Role.SPY: 50,
    Role.JAILOR: 75, Role.ORACLE: 45, Role.PRIEST: 50, Role.TRANSPORTER: 60,
    Role.ADVOKAT: 40, Role.SHERIF: 55,
    Role.MAFIA: 30, Role.DON: 80, Role.CONSIGLIERE: 60, Role.FRAMER: 35,
    Role.JANITOR: 40, Role.SILENCER: 40, Role.BLACKMAILER: 45, Role.ROLEBLOCKER: 50,
    Role.FORGER: 45, Role.GODFATHER: 100,
    Role.MANIYAK: 100, Role.JOKER: 20, Role.ARSONIST: 90, Role.EXECUTIONER: 30,
    Role.WITCH: 70, Role.SURVIVOR: 25, Role.AMNESIAC: 40, Role.ASSASSIN: 80,
    Role.BOMBER: 75, Role.POISONER: 70, Role.PROFESSIONAL: 85,
}

TOWN_ROLES = [r for r in Role if ROLE_TEAM[r] == "town"]
MAFIA_ROLES = [r for r in Role if ROLE_TEAM[r] == "mafia"]
NEUTRAL_ROLES = [r for r in Role if ROLE_TEAM[r] == "neutral"]

IS_NIGHT_ACTIVE = {
    Role.TINCH: False, Role.KOMISSAR: True, Role.DOKTOR: True,
    Role.QORIQCHI: True, Role.KUZATUVCHI: True, Role.IZQUVAR: True,
    Role.TERGOVCHI: True, Role.MER: False, Role.VETERAN: True,
    Role.VIGILANTE: True, Role.HAMSHIRA: True, Role.MEDIUM: True,
    Role.PSIXOLOG: True, Role.MUHANDIS: True, Role.DETEKTIV: True,
    Role.SPY: True, Role.JAILOR: True, Role.ORACLE: True,
    Role.PRIEST: True, Role.TRANSPORTER: True, Role.ADVOKAT: False,
    Role.SHERIF: False,
    Role.MAFIA: True, Role.DON: True, Role.CONSIGLIERE: True,
    Role.FRAMER: True, Role.JANITOR: True, Role.SILENCER: True,
    Role.BLACKMAILER: True, Role.ROLEBLOCKER: True, Role.FORGER: True,
    Role.GODFATHER: True,
    Role.MANIYAK: True, Role.JOKER: False, Role.ARSONIST: True,
    Role.EXECUTIONER: False, Role.WITCH: True, Role.SURVIVOR: False,
    Role.AMNESIAC: True, Role.ASSASSIN: True, Role.BOMBER: True,
    Role.POISONER: True, Role.PROFESSIONAL: True,
}


def distribute_roles(player_count: int, role_pool: list[Role] | None = None) -> list[Role]:
    import random
    if role_pool:
        random.shuffle(role_pool)
        return role_pool[:player_count]

    roles = []
    if player_count <= 4:
        mafia_count, town_specials = 1, [Role.KOMISSAR]
    elif player_count <= 6:
        mafia_count, town_specials = 1, [Role.KOMISSAR, Role.DOKTOR]
    elif player_count <= 8:
        mafia_count, town_specials = 2, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI]
    elif player_count <= 10:
        mafia_count, town_specials = 2, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI, Role.TERGOVCHI]
    elif player_count <= 13:
        mafia_count, town_specials = 3, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI, Role.TERGOVCHI, Role.MER]
    elif player_count <= 16:
        mafia_count, town_specials = 3, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI, Role.TERGOVCHI, Role.MER, Role.VETERAN, Role.MUHANDIS]
    elif player_count <= 20:
        mafia_count, town_specials = 4, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI, Role.TERGOVCHI, Role.MER, Role.VETERAN, Role.MUHANDIS, Role.SPY, Role.JAILOR]
    else:
        mafia_count, town_specials = 5, [Role.KOMISSAR, Role.DOKTOR, Role.QORIQCHI, Role.TERGOVCHI, Role.MER, Role.VETERAN, Role.MUHANDIS, Role.SPY, Role.JAILOR, Role.TRANSPORTER, Role.KUZATUVCHI, Role.IZQUVAR]

    roles.extend([Role.MAFIA] * mafia_count)
    roles.extend(town_specials)
    has_don = player_count >= 6
    if has_don:
        roles.append(Role.DON)
    neutral_count = 1 if player_count >= 7 else 0
    if neutral_count:
        neutral_pool = [Role.MANIYAK, Role.JOKER, Role.ARSONIST, Role.WITCH, Role.SURVIVOR, Role.EXECUTIONER]
        random.shuffle(neutral_pool)
        roles.append(neutral_pool[0])

    while len(roles) < player_count:
        roles.append(Role.TINCH)

    random.shuffle(roles)
    return roles


class ActionPriority(int, Enum):
    TRANSPORT = 1
    ROLEBLOCK = 2
    BLACKMAIL_SILENCE = 3
    INVESTIGATE = 4
    PROTECT = 5
    KILL = 6
    VENGEFUL = 7
    LAST = 8
