$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Find-Python {
  $candidates = @(
    (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"),
    (Join-Path $env:USERPROFILE "scoop\persist\rye\py\cpython@3.12.5\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe")
  )

  foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate) {
      return $candidate
    }
  }

  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) {
    return $cmd.Source
  }

  throw "Python 3.11 ou 3.12 est introuvable. Installez Python puis relancez."
}

$python = Find-Python
& $python .\desktop_app.py
