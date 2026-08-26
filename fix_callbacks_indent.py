with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix line 57 (0-indexed = 56)
if not lines[56].startswith('    '):
    lines[56] = '    ' + lines[56]

with open('D:\\3D\\mafia_bot\\handlers\\callbacks.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed indentation!')