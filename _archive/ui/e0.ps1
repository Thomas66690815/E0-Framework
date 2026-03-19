# E0 Start — Shortcut
# Usage: .\e0   or   .\e0 --lang en   or   .\e0 --port 3001
Set-Location $PSScriptRoot
& py "$PSScriptRoot\e0_start.py" --web @args
