# Starts the service with the development console at http://127.0.0.1:8000/console
#
#     .\dev.ps1
#
# The console is a browser page for asking questions and reading the answers
# without launching the Flutter app. It exists because the app takes minutes to
# start and a Windows terminal renders Bangla as boxes.
#
# BHAROSHA_DEV_CONSOLE is set HERE and nowhere else. app/api.py registers the
# /console routes inside an `if` on that variable, so a deployed instance does
# not serve them at all — the Dockerfile never sets it, and Render's
# environment does not either.

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

$env:BHAROSHA_DEV_CONSOLE = 'on'

# --reload so editing safety.py or referrals.py takes effect on the next
# question instead of the next restart. It does mean the corpus is re-embedded
# after each edit, which takes a few seconds; answers that need no corpus —
# every emergency, refusal and social reply — are unaffected.
& .\.venv\Scripts\python.exe -m uvicorn api:app `
    --app-dir app `
    --host 127.0.0.1 `
    --port 8000 `
    --reload `
    --reload-dir app
