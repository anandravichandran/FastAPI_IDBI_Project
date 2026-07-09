$ErrorActionPreference = "Stop"
$port = 9879
$baseUrl = "http://127.0.0.1:$port"
$serverLog = "$env:TEMP\server_curl_test.log"
Remove-Item $serverLog -ErrorAction SilentlyContinue

# Kill any leftover uvicorn
Get-Process -Name "python*" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "uvicorn.*server:app" } | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# Start server
Write-Host "Starting server on port $port..."
$job = Start-Job -ScriptBlock {
    param($p, $log, $dir)
    Set-Location $dir
    $env:PYTHONIOENCODING = "utf-8"
    & "D:\fast-api\.venv\Scripts\python.exe" -m uvicorn server:app --host 127.0.0.1 --port $p --log-level warning *>> $log
} -ArgumentList $port, $serverLog, (Get-Location).Path

Start-Sleep -Seconds 8

# Wait for health
$healthy = $false
for ($i = 1; $i -le 20; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "$baseUrl/health" -Method GET -TimeoutSec 2 -ErrorAction Stop
        if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch {}
    Write-Host "  health check attempt $i..."
    Start-Sleep -Seconds 1
}

if (-not $healthy) {
    Write-Host "Server failed to start. Log:" -ForegroundColor Red
    Get-Content $serverLog -ErrorAction SilentlyContinue | Select-Object -Last 20
    Remove-Job $job -Force -ErrorAction SilentlyContinue
    exit 1
}

Write-Host "Server healthy" -ForegroundColor Green

# Run curl tests
$env:BASE_URL = $baseUrl
$env:PDF = "$env:TEMP\rag_sample.pdf"
& "D:\fast-api\.venv\Scripts\python.exe" -c "
import sys
pdf = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 300 144]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj\n4 0 obj<</Length 74>>stream\nBT /F1 12 Tf 20 100 Td (Emergency fund: 6 months of expenses.) Tj ET\nendstream endobj\n5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF'
with open(sys.argv[1], 'wb') as f:
    f.write(pdf)
print('wrote', sys.argv[1])
" "$env:PDF"

# Check git bash
$gitBash = Get-Command "C:\Program Files\Git\bin\bash.exe" -ErrorAction SilentlyContinue
if (-not $gitBash) { $gitBash = Get-Command "C:\Program Files (x86)\Git\bin\bash.exe" -ErrorAction SilentlyContinue }

if ($gitBash) {
    Write-Host "Running curl_tests.sh via Git Bash..."
    & $gitBash.Source scripts/curl_tests.sh
    $exitCode = $LASTEXITCODE
    Write-Host "Curl tests completed with exit code: $exitCode" -ForegroundColor Yellow
} else {
    Write-Host "Git Bash not found. Skipping curl_tests.sh execution." -ForegroundColor Yellow
    Write-Host "You can run it manually: bash scripts/curl_tests.sh" -ForegroundColor Yellow
    $exitCode = 0
}

# Cleanup
Stop-Job $job -ErrorAction SilentlyContinue
Remove-Job $job -Force -ErrorAction SilentlyContinue
Remove-Item $serverLog -ErrorAction SilentlyContinue
Remove-Item "$env:TEMP\rag_sample.pdf" -ErrorAction SilentlyContinue

exit $exitCode
