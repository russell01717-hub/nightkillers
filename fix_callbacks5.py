with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix line 57 - ensure it starts with 4 spaces
old = 'dp.callback_query.register(handle_night_professional, F.data.startswith("nv_professional:"))'
new = '    dp.callback_query.register(handle_night_professional, F.data.startswith("nv_professional:"))'
content = content.replace(old, new)

with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')