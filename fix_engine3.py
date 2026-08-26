# Fix the game_engine.py syntax error
with open('D:\\3D\\mafia_bot\\game_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''        else:
            await safe_send_message(bot, player.user_id, f"❓ O'liklar orasida maxsus rol yo'q.")
            game.action_ready[player.user_id] = True
elif role == Role.MASHUQA:'''

new = '''            else:
            await safe_send_message(bot, player.user_id, f"❓ O'liklar orasida maxsus rol yo'q.")
            game.action_ready[player.user_id] = True
        elif role == Role.MASHUQA:'''

content = content.replace(old, new)

with open('D:\\3D\\mafia_bot\\game_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')