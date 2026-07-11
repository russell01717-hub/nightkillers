import os

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7820231987"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "4073-4200-7154-7032")

MIN_PLAYERS = 4
MAX_PLAYERS = 100
NIGHT_TIME = 45
DAY_TIME = 45
MORNING_WAIT = 10

ROLE_PRIORITY = {
    "Transporter": 1,
    "Roleblocker": 2,
    "Blackmailer": 3,
    "Silencer": 3,
    "Consigliere": 4,
    "Spy": 4,
    "Tracker": 5,
    "Watcher": 5,
    "Investigator": 6,
    "Detective": 6,
    "Psychologist": 6,
    "Priest": 6,
    "Oracle": 6,
    "Forger": 7,
    "Janitor": 7,
    "Framer": 7,
    "Doktor": 8,
    "Hamshira": 8,
    "Bodyguard": 8,
    "Mafia": 9,
    "Godfather": 9,
    "Don": 9,
    "Consort": 9,
    "Maniak": 10,
    "Arsonist": 10,
    "Assassin": 10,
    "Poisoner": 10,
    "Bomber": 11,
    "Vigilante": 12,
    "Veteran": 13,
    "Jailor": 14,
}

BOT_NAMES = [
    "Alex", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
    "Hank", "Ivy", "Jack", "Kate", "Leo", "Mia", "Nick", "Olga",
    "Paul", "Quinn", "Rita", "Sam", "Tina", "Uma", "Vince", "Wendy",
    "Xander", "Yara", "Zack",
]
