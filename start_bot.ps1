$env:BOT_TOKEN = "8928310354:AAHQ_jAuUqxfWH3Zz5NRAyqBs9YnShmo2CQ"
$env:CARD_NUMBER = "4073-4200-7154-7032"
$env:PYTHONPATH = "D:\pylibs"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& 'C:\Users\RZ\AppData\Local\Python\bin\python.exe' D:\3D\run_bot.py" -WindowStyle Hidden
