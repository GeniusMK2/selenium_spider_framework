start %~dp0\env\chrome-win64\chrome --remote-debugging-port=22222 --user-data-dir="./var/chrome_user_data/" --disk-cache-dir="nul"

@REM start %~dp0\env\chrome-win64\chrome --remote-debugging-port=22222 --user-data-dir="./var/chrome_user_data/" --disk-cache-dir="./var/chrome_cache/"

%~dp0/env/python/python.exe ./main.py