# SyllabusSync backend launcher
# First run: creates the virtual environment and installs libraries.
# Every run: starts the API at http://127.0.0.1:8000

Set-Location $PSScriptRoot

function Find-Python {
    # 1. The Python launcher (py), installed with python.org Python
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Args = @("-3") }
    }
    # 2. A real python on PATH (skip the Microsoft Store shortcut)
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike "*WindowsApps*") {
        return @{ Exe = $cmd.Source; Args = @() }
    }
    # 3. The default python.org install folder
    $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\python.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) {
        return @{ Exe = $found.FullName; Args = @() }
    }
    return $null
}

$venvPython = ".\venv\Scripts\python.exe"

# Remove a half-created venv from an earlier failed run
if ((Test-Path "venv") -and -not (Test-Path $venvPython)) {
    Remove-Item "venv" -Recurse -Force
}

if (-not (Test-Path $venvPython)) {
    $py = Find-Python
    if (-not $py) {
        Write-Host "Could not find Python. Install it from python.org and check 'Add python.exe to PATH'." -ForegroundColor Red
        exit 1
    }
    Write-Host "Using Python at: $($py.Exe)"
    Write-Host "Creating virtual environment (first time only)..."
    & $py.Exe @($py.Args) -m venv venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

Write-Host ""
Write-Host "Starting SyllabusSync API... open http://127.0.0.1:8000/docs" -ForegroundColor Green
& ".\venv\Scripts\fastapi.exe" dev main.py
