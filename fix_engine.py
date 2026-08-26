# Fix the game_engine.py syntax error
with open('D:\\3D\\mafia_bot\\game_engine.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]
    new_lines.append(line)
    
    # Check for AMNESIAC handler's final 'game.action_ready[player.user_id] = True'
    # followed by 'elif role == Role.MASHUQA:' at main chain level
    if 'game.action_ready[player.user_id] = True' in line and i > 500 and i < 510:
        if i + 1 < len(lines):
            next_line = lines[i + 1]
            if next_line.strip().startswith('elif role == Role.MASHUQA:'):
                # Insert 'else:' before it at main chain level (8 spaces)
                new_lines.append('        else:\n')
                new_lines.append('            await safe_send_message(bot, player.user_id, f"❓ O\'liklar orasida maxsus rol yo\'q.")\n')
                new_lines.append('            game.action_ready[player.user_id] = True\n')
    i += 1

with open('D:\\3D\\mafia_bot\\game_engine.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Fixed!')