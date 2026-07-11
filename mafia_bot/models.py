"""Game data models"""

import asyncio
import json
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, List

from .roles import Role, GamePhase, ROLE_ICON, ROLE_TEAM, ROLE_DISPLAY
from .config import NIGHT_TIME, DAY_TIME, MIN_PLAYERS


@dataclass
class Player:
    user_id: int
    name: str
    username: str = ""
    is_bot: bool = False
    role: Optional[Role] = None
    team: str = ""
    alive: bool = True
    vote: Optional[int] = None
    protected: bool = False
    hero_attack: int = 0
    hero_defense: int = 0
    jailed: bool = False
    poisoned: bool = False
    bombed: bool = False
    doused: bool = False
    silenced: bool = False
    blackmailed: bool = False
    roleblocked: bool = False
    framed: bool = False
    forger_role: Optional[str] = None
    transported_with: Optional[int] = None
    joined_at: float = field(default_factory=lambda: datetime.now().timestamp())
    night_target: Optional[int] = None
    has_acted: bool = False
    last_words: Optional[str] = None
    afk_rounds: int = 0
    last_action_round: int = 0

    @property
    def display(self) -> str:
        return f"@{self.username}" if self.username else self.name

    @property
    def role_display(self) -> str:
        if not self.role:
            return "❓ Noma'lum"
        return f"{ROLE_ICON.get(self.role, '❓')} {self.role.value}"

    def status_icon(self) -> str:
        return "🟢" if self.alive else "💀"

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id, "name": self.name, "username": self.username,
            "is_bot": self.is_bot, "role": self.role.value if self.role else None,
            "team": self.team, "alive": self.alive, "vote": self.vote,
            "protected": self.protected, "hero_attack": self.hero_attack,
            "hero_defense": self.hero_defense, "jailed": self.jailed,
            "poisoned": self.poisoned, "bombed": self.bombed, "doused": self.doused,
            "silenced": self.silenced, "blackmailed": self.blackmailed,
            "roleblocked": self.roleblocked, "framed": self.framed,
            "forger_role": self.forger_role, "transported_with": self.transported_with,
            "night_target": self.night_target, "has_acted": self.has_acted,
            "last_words": self.last_words, "afk_rounds": self.afk_rounds,
            "last_action_round": self.last_action_round,
        }

    @staticmethod
    def from_dict(data: dict) -> 'Player':
        return Player(
            user_id=data["user_id"], name=data["name"], username=data.get("username", ""),
            is_bot=data.get("is_bot", False),
            role=Role(data["role"]) if data.get("role") else None,
            team=data.get("team", ""), alive=data.get("alive", True),
            vote=data.get("vote"), protected=data.get("protected", False),
            hero_attack=data.get("hero_attack", 0),
            hero_defense=data.get("hero_defense", 0),
            jailed=data.get("jailed", False), poisoned=data.get("poisoned", False),
            bombed=data.get("bombed", False), doused=data.get("doused", False),
            silenced=data.get("silenced", False), blackmailed=data.get("blackmailed", False),
            roleblocked=data.get("roleblocked", False), framed=data.get("framed", False),
            forger_role=data.get("forger_role"), transported_with=data.get("transported_with"),
            night_target=data.get("night_target"), has_acted=data.get("has_acted", False),
            last_words=data.get("last_words"),
            afk_rounds=data.get("afk_rounds", 0),
            last_action_round=data.get("last_action_round", 0),
        )


@dataclass
class MafiaGame:
    chat_id: int
    phase: GamePhase = GamePhase.WAITING
    day: int = 0
    players: Dict[int, Player] = field(default_factory=dict)
    action_ready: Dict[int, bool] = field(default_factory=dict)
    night_task: Optional[asyncio.Task] = None
    day_task: Optional[asyncio.Task] = None
    game_msg_id: Optional[int] = None
    death_msg_id: Optional[int] = None
    winner: Optional[str] = None
    start_time: Optional[float] = None
    night_time: int = NIGHT_TIME
    vote_time: int = DAY_TIME
    min_players: int = MIN_PLAYERS
    game_id: str = ""

    # Night vote tracking
    mafia_votes: Dict[int, int] = field(default_factory=dict)
    don_target: Optional[int] = None
    consigliere_target: Optional[int] = None
    komissar_target: Optional[int] = None
    doktor_target: Optional[int] = None
    hamshira_target: Optional[int] = None
    qoriqchi_target: Optional[int] = None
    kuzatuvchi_target: Optional[int] = None
    izquvar_target: Optional[int] = None
    tergovchi_target: Optional[int] = None
    detective_target: Optional[int] = None
    spy_target: Optional[int] = None
    psychologist_target: Optional[int] = None
    engineer_target: Optional[int] = None
    priest_target: Optional[int] = None
    oracle_target: Optional[int] = None
    transporter_target1: Optional[int] = None
    transporter_target2: Optional[int] = None
    jailor_target: Optional[int] = None
    vigilante_target: Optional[int] = None
    vigilante_bullets: int = 2
    veteran_active: bool = False
    maniyak_target: Optional[int] = None
    arsonist_targets: List[int] = field(default_factory=list)
    arsonist_ignite: bool = False
    assassin_target: Optional[int] = None
    bomber_target: Optional[int] = None
    poisoner_target: Optional[int] = None
    professional_target: Optional[int] = None
    witch_control: Dict[int, int] = field(default_factory=dict)
    roleblocker_target: Optional[int] = None
    silencer_target: Optional[int] = None
    blackmailer_target: Optional[int] = None
    framer_target: Optional[int] = None
    janitor_target: Optional[int] = None
    forger_target: Optional[int] = None
    kill_targets: List[int] = field(default_factory=list)
    healed_player: Optional[int] = None
    revived_player: Optional[int] = None
    advokat_protect: Optional[int] = None
    elo_k: int = 32
    vote_round: int = 1

    def __post_init__(self):
        self.game_id = f"G{self.chat_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        from .db import get_chat_setting
        self.night_time = get_chat_setting(self.chat_id, "night_time", NIGHT_TIME)
        self.vote_time = get_chat_setting(self.chat_id, "vote_time", DAY_TIME)
        self.min_players = get_chat_setting(self.chat_id, "min_players", MIN_PLAYERS)

    @property
    def alive_players(self) -> List[Player]:
        return [p for p in self.players.values() if p.alive]

    @property
    def dead_players(self) -> List[Player]:
        return [p for p in self.players.values() if not p.alive]

    @property
    def mafia_players(self) -> List[Player]:
        return [p for p in self.alive_players if p.team == "mafia"]

    @property
    def town_players(self) -> List[Player]:
        return [p for p in self.alive_players if p.team == "town"]

    @property
    def neutral_players(self) -> List[Player]:
        return [p for p in self.alive_players if p.team == "neutral"]

    @property
    def mafia_votes_received(self) -> Dict[int, int]:
        votes = {}
        for target in self.mafia_votes.values():
            if target > 0:
                votes[target] = votes.get(target, 0) + 1
        if self.don_target is not None:
            votes[self.don_target] = votes.get(self.don_target, 0) + 2
        return votes

    def get_player(self, user_id: int) -> Optional[Player]:
        return self.players.get(user_id)

    def cancel_timers(self):
        for t in [self.night_task, self.day_task]:
            if t and not t.done():
                t.cancel()
        self.night_task = None
        self.day_task = None

    def reset_night(self):
        for p in self.players.values():
            p.protected = False
            p.has_acted = False
            p.night_target = None
        self.action_ready = {}
        self.mafia_votes = {}
        self.don_target = None
        self.consigliere_target = None
        self.komissar_target = None
        self.doktor_target = None
        self.hamshira_target = None
        self.qoriqchi_target = None
        self.kuzatuvchi_target = None
        self.izquvar_target = None
        self.tergovchi_target = None
        self.detective_target = None
        self.spy_target = None
        self.psychologist_target = None
        self.engineer_target = None
        self.priest_target = None
        self.oracle_target = None
        self.transporter_target1 = None
        self.transporter_target2 = None
        self.jailor_target = None
        self.vigilante_target = None
        self.veteran_active = False
        self.maniyak_target = None
        self.arsonist_targets = []
        self.arsonist_ignite = False
        self.assassin_target = None
        self.bomber_target = None
        self.poisoner_target = None
        self.professional_target = None
        self.witch_control = {}
        self.roleblocker_target = None
        self.silencer_target = None
        self.blackmailer_target = None
        self.framer_target = None
        self.janitor_target = None
        self.forger_target = None
        self.kill_targets = []
        self.healed_player = None
        self.revived_player = None
        self.advokat_protect = None

    def reset_day(self):
        for p in self.players.values():
            p.vote = None
            p.last_words = None
        self.action_ready = {}
        self.vote_round = 1

    def get_roles_text(self) -> str:
        lines = []
        for p in self.players.values():
            icon = ROLE_ICON.get(p.role, "❓") if p.role else "❓"
            status = "✅" if p.alive else "💀"
            unknown = "Noma'lum"
            lines.append(f"{status} {p.display}: {icon} {p.role.value if p.role else unknown}")
        return "\n".join(lines)

    def player_list_text(self, show_roles: bool = False) -> str:
        parts = []
        for p in self.players.values():
            if p.alive:
                team_icon = "🔪" if p.team == "mafia" else "👤"
                role_part = f" ({p.role_display})" if show_roles and p.role else ""
                parts.append(f"{team_icon} {p.display}{role_part}")
        return "\n".join(parts)

    def log(self, event: str, data: str = ""):
        from .db import log_event, save_active_game
        log_event(self.chat_id, self.game_id, event, data)
        save_active_game(self)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value, "day": self.day,
            "game_msg_id": self.game_msg_id, "death_msg_id": self.death_msg_id,
            "night_time": self.night_time, "vote_time": self.vote_time,
            "min_players": self.min_players, "game_id": self.game_id,
            "players": {str(k): v.to_dict() for k, v in self.players.items()},
            "mafia_votes": {str(k): v for k, v in self.mafia_votes.items()},
            "don_target": self.don_target, "consigliere_target": self.consigliere_target,
            "komissar_target": self.komissar_target, "doktor_target": self.doktor_target,
            "hamshira_target": self.hamshira_target, "qoriqchi_target": self.qoriqchi_target,
            "kuzatuvchi_target": self.kuzatuvchi_target, "izquvar_target": self.izquvar_target,
            "tergovchi_target": self.tergovchi_target, "detective_target": self.detective_target,
            "spy_target": self.spy_target, "psychologist_target": self.psychologist_target,
            "engineer_target": self.engineer_target, "priest_target": self.priest_target,
            "oracle_target": self.oracle_target,
            "transporter_target1": self.transporter_target1,
            "transporter_target2": self.transporter_target2,
            "jailor_target": self.jailor_target, "vigilante_target": self.vigilante_target,
            "vigilante_bullets": self.vigilante_bullets,
            "veteran_active": self.veteran_active, "maniyak_target": self.maniyak_target,
            "arsonist_targets": self.arsonist_targets, "arsonist_ignite": self.arsonist_ignite,
            "assassin_target": self.assassin_target, "bomber_target": self.bomber_target,
            "poisoner_target": self.poisoner_target, "professional_target": self.professional_target,
            "witch_control": {str(k): v for k, v in self.witch_control.items()},
            "roleblocker_target": self.roleblocker_target, "silencer_target": self.silencer_target,
            "blackmailer_target": self.blackmailer_target, "framer_target": self.framer_target,
            "janitor_target": self.janitor_target, "forger_target": self.forger_target,
            "kill_targets": self.kill_targets, "healed_player": self.healed_player,
            "revived_player": self.revived_player, "advokat_protect": self.advokat_protect,
            "elo_k": self.elo_k, "vote_round": self.vote_round,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'MafiaGame':
        game = cls(chat_id=data.get("chat_id", 0))
        game.phase = GamePhase(data["phase"])
        game.day = data["day"]
        game.game_msg_id = data.get("game_msg_id")
        game.death_msg_id = data.get("death_msg_id")
        game.night_time = data.get("night_time", NIGHT_TIME)
        game.vote_time = data.get("vote_time", DAY_TIME)
        game.min_players = data.get("min_players", MIN_PLAYERS)
        game.game_id = data.get("game_id", "")
        for uid_str, pdata in data.get("players", {}).items():
            p = Player.from_dict(pdata)
            game.players[p.user_id] = p
        game.mafia_votes = {int(k): v for k, v in data.get("mafia_votes", {}).items()}
        game.don_target = data.get("don_target")
        game.consigliere_target = data.get("consigliere_target")
        game.komissar_target = data.get("komissar_target")
        game.doktor_target = data.get("doktor_target")
        game.hamshira_target = data.get("hamshira_target")
        game.qoriqchi_target = data.get("qoriqchi_target")
        game.kuzatuvchi_target = data.get("kuzatuvchi_target")
        game.izquvar_target = data.get("izquvar_target")
        game.tergovchi_target = data.get("tergovchi_target")
        game.detective_target = data.get("detective_target")
        game.spy_target = data.get("spy_target")
        game.psychologist_target = data.get("psychologist_target")
        game.engineer_target = data.get("engineer_target")
        game.priest_target = data.get("priest_target")
        game.oracle_target = data.get("oracle_target")
        game.transporter_target1 = data.get("transporter_target1")
        game.transporter_target2 = data.get("transporter_target2")
        game.jailor_target = data.get("jailor_target")
        game.vigilante_target = data.get("vigilante_target")
        game.vigilante_bullets = data.get("vigilante_bullets", 2)
        game.veteran_active = data.get("veteran_active", False)
        game.maniyak_target = data.get("maniyak_target")
        game.arsonist_targets = data.get("arsonist_targets", [])
        game.arsonist_ignite = data.get("arsonist_ignite", False)
        game.assassin_target = data.get("assassin_target")
        game.bomber_target = data.get("bomber_target")
        game.poisoner_target = data.get("poisoner_target")
        game.professional_target = data.get("professional_target")
        game.witch_control = {int(k): v for k, v in data.get("witch_control", {}).items()}
        game.roleblocker_target = data.get("roleblocker_target")
        game.silencer_target = data.get("silencer_target")
        game.blackmailer_target = data.get("blackmailer_target")
        game.framer_target = data.get("framer_target")
        game.janitor_target = data.get("janitor_target")
        game.forger_target = data.get("forger_target")
        game.kill_targets = data.get("kill_targets", [])
        game.healed_player = data.get("healed_player")
        game.revived_player = data.get("revived_player")
        game.advokat_protect = data.get("advokat_protect")
        game.elo_k = data.get("elo_k", 32)
        game.vote_round = data.get("vote_round", 1)
        return game


games: Dict[int, MafiaGame] = {}
