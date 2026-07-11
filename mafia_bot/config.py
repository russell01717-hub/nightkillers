import os

TOKEN = os.environ["BOT_TOKEN"]
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7820231987"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "4073-4200-7154-7032")

MIN_PLAYERS = 4
MAX_PLAYERS = 100
NIGHT_TIME = 45
DAY_TIME = 45
MORNING_WAIT = 10

BOT_NAMES = [
    "Alex", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace",
    "Hank", "Ivy", "Jack", "Kate", "Leo", "Mia", "Nick", "Olga",
    "Paul", "Quinn", "Rita", "Sam", "Tina", "Uma", "Vince", "Wendy",
    "Xander", "Yara", "Zack",
]
