$env:BOT_TOKEN = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
$env:CARD_NUMBER = "4073-4200-7154-7032"
$env:PYTHONPATH = "D:\pylibs"

# Kill any conflicting bot processes (old monoliths using same token)
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" | Where-Object {
    $_.CommandLine -match "mafia_bot\.py" -or $_.CommandLine -match "run_bot\.py"
} | ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force
    Write-Output "Killed conflicting bot PID $($_.ProcessId)"
}
Start-Sleep 1

Start-Process powershell -ArgumentList "-NoExit", "-Command", "& 'C:\Users\RZ\AppData\Local\Python\bin\python.exe' D:\3D\run_bot.py 2>&1 | Tee-Object -FilePath D:\3D\bot.log" -WindowStyle Hidden
Write-Output "Modular bot started. Logs: D:\3D\bot.log"
