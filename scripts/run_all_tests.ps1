<#
.SYNOPSIS
    Run the full test suite: start server, run pytest, run coverage, run curl tests.
.DESCRIPTION
    Validates the environment, starts the FastAPI server, waits for it to be
    healthy, runs unit tests with coverage, and optionally executes the
    integration curl test suite via Git Bash or WSL.
.EXIT CODE
    0 on success, 1 if any step fails.
#>

$ErrorActionPreference = "Stop"
$originalLocation = Get-Location

# Track overall result
$overallPass = $true

function Write-Step($message) {
    Write-Host "[STEP] $message" -ForegroundColor Cyan
}

function Write-Pass($message) {
    Write-Host "[PASS] $message" -ForegroundColor Green
}

function Write-Fail($message) {
    Write-Host "[FAIL] $message" -ForegroundColor Red
    $script:overallPass = $false
}

function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# Step 1: Verify virtual environment and activate it
# ---------------------------------------------------------------------------
Write-Step "1. Verify virtual environment"

if (-not $env:VIRTUAL_ENV) {
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        Write-Info "Activating .venv\Scripts\Activate.ps1 ..."
        & .venv\Scripts\Activate.ps1
        Write-Pass "Virtual environment activated."
    } else {
        Write-Fail "No virtual environment found at .venv. Please create one first."
        exit 1
    }
} else {
    Write-Pass "Virtual environment is active: $env:VIRTUAL_ENV"
}

# ---------------------------------------------------------------------------
# Step 2: Verify Python (after venv activation so we get the venv's python)
# ---------------------------------------------------------------------------
Write-Step "2. Verify Python"

$python = $null
try {
    $python = (Get-Command python -ErrorAction Stop).Source
    $pythonVersion = & $python --version 2>&1
    Write-Pass "Python found: $python ($pythonVersion)"
} catch {
    Write-Fail "Python not found. Please install Python and ensure it is on your PATH."
    exit 1
}

# ---------------------------------------------------------------------------
# Step 3: Verify pytest is installed
# ---------------------------------------------------------------------------
Write-Step "3. Verify pytest"

try {
    $pytestVersion = & $python -m pytest --version 2>&1
    Write-Pass "pytest installed: $pytestVersion"
} catch {
    Write-Fail "pytest is not installed. Run: pip install -r requirements-dev.txt"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 4: Start the FastAPI server if not already running
# ---------------------------------------------------------------------------
Write-Step "4. Start FastAPI server"

$serverProcess = $null
$serverPort = 9876
$healthUrl = "http://127.0.0.1:${serverPort}/health"

# Check if server is already running
$serverAlreadyRunning = $false
try {
    $response = Invoke-WebRequest -Uri $healthUrl -Method GET -TimeoutSec 3 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $serverAlreadyRunning = $true
        Write-Info "Server is already running at $healthUrl"
    }
} catch {
    # Server is not running, we will start it
}

if (-not $serverAlreadyRunning) {
    Write-Info "Starting uvicorn server on port $serverPort ..."
    $serverOut = Join-Path -Path (Get-Location) -ChildPath "server_stdout.log"
    $serverErr = Join-Path -Path (Get-Location) -ChildPath "server_stderr.log"
    try {
        $uvicornArgs = @("-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", $serverPort, "--log-level", "warning")
        $serverProcess = Start-Process -FilePath $python -ArgumentList $uvicornArgs -NoNewWindow -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr -PassThru -WorkingDirectory (Get-Location).Path
        Write-Info "Server process started with PID $($serverProcess.Id). Stdout: $serverOut  Stderr: $serverErr"
    } catch {
        Write-Fail "Could not start uvicorn server: $_"
        exit 1
    }
}

# ---------------------------------------------------------------------------
# Step 5: Wait until /health returns HTTP 200
# ---------------------------------------------------------------------------
Write-Step "5. Wait for server health"

$maxRetries = 30
$retryDelaySeconds = 2
$healthy = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -Method GET -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Pass "Server is healthy after ${i} retries."
            $healthy = $true
            break
        }
    } catch {
        # Still waiting
    }
    Write-Info "Waiting for server... attempt $i of $maxRetries (waiting ${retryDelaySeconds}s)"
    Start-Sleep -Seconds $retryDelaySeconds
}

if (-not $healthy) {
    Write-Fail "Server did not become healthy within $maxRetries retries."
    if ($serverProcess -and (-not $serverProcess.HasExited)) {
        $serverProcess.Kill()
    }
    exit 1
}

# ---------------------------------------------------------------------------
# Step 6: Run python -m pytest -v
# ---------------------------------------------------------------------------
Write-Step "6. Run unit tests (pytest -v)"

try {
    & $python -m pytest -v
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "All unit tests passed."
    } else {
        Write-Fail "Some unit tests failed (exit code: $LASTEXITCODE)."
    }
} catch {
    Write-Fail "Unit tests threw an exception: $_"
}

# ---------------------------------------------------------------------------
# Step 7: Run python -m pytest --cov=. --cov-report=html
# ---------------------------------------------------------------------------
Write-Step "7. Run coverage (pytest --cov=.)"

try {
    & $python -m pytest --cov=. --cov-report=html
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Coverage report generated (htmlcov/index.html)."
    } else {
        Write-Fail "Coverage run failed (exit code: $LASTEXITCODE)."
    }
} catch {
    Write-Fail "Coverage run threw an exception: $_"
}

# ---------------------------------------------------------------------------
# Step 8: Run curl_tests.sh if it exists
# ---------------------------------------------------------------------------
Write-Step "8. Run integration curl tests"

$curlScript = Join-Path -Path (Get-Location) -ChildPath "scripts\curl_tests.sh"
if (-not (Test-Path $curlScript)) {
    Write-Info "curl_tests.sh not found at $curlScript. Skipping integration tests."
} else {
    $shellFound = $false
    $shellPath = $null

    # Try Git Bash
    $gitBashCandidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files (x86)\Git\bin\bash.exe",
        "${env:ProgramFiles}\Git\bin\bash.exe",
        "${env:ProgramFiles(x86)}\Git\bin\bash.exe"
    )
    foreach ($candidate in $gitBashCandidates) {
        if (Test-Path $candidate) {
            $shellPath = $candidate
            $shellFound = $true
            Write-Info "Found Git Bash at: $shellPath"
            break
        }
    }

    # Try WSL if Git Bash not found
    if (-not $shellFound) {
        $wslExe = Get-Command "wsl.exe" -ErrorAction SilentlyContinue
        if ($wslExe) {
            $shellPath = "wsl.exe"
            $shellFound = $true
            Write-Info "Found WSL: $shellPath"
        }
    }

    if ($shellFound) {
        Write-Info "Running: $curlScript via $shellPath"
        try {
            if ($shellPath -eq "wsl.exe") {
                & $shellPath bash $curlScript
            } else {
                $env:BASE_URL = "http://127.0.0.1:${serverPort}"
                & $shellPath $curlScript
                Remove-Item env:BASE_URL -ErrorAction SilentlyContinue
            }
            if ($LASTEXITCODE -eq 0) {
                Write-Pass "All curl integration tests passed."
            } else {
                Write-Fail "Some curl integration tests failed (exit code: $LASTEXITCODE)."
            }
        } catch {
            Write-Fail "Curl tests threw an exception: $_"
        }
    } else {
        Write-Info "Neither Git Bash nor WSL found. Skipping curl integration tests."
    }
}

# ---------------------------------------------------------------------------
# Step 9: Print PASS/FAIL summary
# ---------------------------------------------------------------------------
Write-Step "9. Summary"

if ($overallPass) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  ALL TESTS PASSED" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  SOME TESTS FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
}

# ---------------------------------------------------------------------------
# Cleanup: stop the server if we started it
# ---------------------------------------------------------------------------
if ($serverProcess -and (-not $serverProcess.HasExited)) {
    Write-Info "Stopping server (PID $($serverProcess.Id))..."
    $serverProcess.Kill()
    Write-Info "Server stopped."
}

# ---------------------------------------------------------------------------
# Step 10: Exit with proper exit code
# ---------------------------------------------------------------------------
Set-Location $originalLocation
if ($overallPass) {
    exit 0
} else {
    exit 1
}
