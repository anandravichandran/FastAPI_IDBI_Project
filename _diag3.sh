#!/usr/bin/env bash
PORT=$1
echo "=== 1. File readable? ==="
cat /tmp/rag_sample.pdf > /dev/null 2>&1 && echo "YES - cat reads it OK" || echo "NO - cat cannot read"
cat /tmp/rag_sample.pdf | wc -c
echo ""
echo "=== 2. Try with known-good text file ==="
echo "hello world" > /tmp/test_upload.txt
ls -la /tmp/test_upload.txt
curl -v -X POST -F "file=@/tmp/test_upload.txt;type=text/plain" \
  "http://127.0.0.1:${PORT}/rag/api/v1/documents" 2>&1
echo ""
echo "EXIT: $?"
echo ""
echo "=== 3. Check MSYS2 path translation ==="
# Test if MSYS2 converts the path when embedded in -F
/usr/bin/cygpath -w /tmp/rag_sample.pdf 2>/dev/null || echo "no cygpath"
echo "TEMP env: $TEMP"
echo "TMPDIR: $TMPDIR"
echo ""
echo "=== 4. Try with Windows path ==="
WIN_PATH=$(cd /tmp && pwd -W)/rag_sample.pdf 2>/dev/null || echo "pwd -W not supported"
echo "Win path: $WIN_PATH"
if [ -n "$WIN_PATH" ]; then
  curl -v -X POST -F "file=@$WIN_PATH;type=application/pdf" \
    "http://127.0.0.1:${PORT}/rag/api/v1/documents" 2>&1
  echo "EXIT: $?"
fi
