$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\Teoman\OneDrive\Desktop\LUXDEEP"
Set-Location -LiteralPath $repoRoot

$env:PYTHONIOENCODING = "utf-8"
python luxcode_server.py
