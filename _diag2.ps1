$ErrorActionPreference = "Stop"
$port = 9911

# Start server
$proc = Start-Process -FilePath "D:\fast-api\.venv\Scripts\python.exe" `
    -ArgumentList "-m uvicorn server:app --host 127.0.0.1 --port $port --log-level warning" `
    -WorkingDirectory "D:\fast-api" -PassThru -NoNewWindow

# Wait for health
for ($i = 1; $i -le 20; $i++) {
    try { $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -TimeoutSec 3; if ($r.StatusCode -eq 200) { Write-Host "Healthy after ${i}s"; break } } catch {}
    Start-Sleep -Seconds 2
}

# Test upload via Git Bash curl
Write-Host "`n=== Test via Git Bash (MSYS2 curl) ==="
& "C:\Program Files\Git\bin\bash.exe" -c @"
cd /d/fast-api
echo 'Testing from Git Bash...'
echo "PDF exists:"
ls -la /tmp/rag_sample.pdf 2>&1
echo ''
echo '=== UPLOAD VERBOSE ==='
curl -v -X POST -F 'file=@/tmp/rag_sample.pdf;type=application/pdf' \
  http://127.0.0.1:$port/rag/api/v1/documents 2>&1
echo ''
echo 'EXIT: '$?
"@

$proc.Kill()
