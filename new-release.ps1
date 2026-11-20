# ytdlp-studio:new-release-ps1 v1
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
python (Join-Path $here "scripts/new_release.py") @args
