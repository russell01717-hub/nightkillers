with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 57 (0-indexed = 56) - ensure it starts with 4 spaces
if len(lines) > 56 and not lines[56].startswith('    '):
    lines[56] = '    ' + lines[56].lstrip()

with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed!')