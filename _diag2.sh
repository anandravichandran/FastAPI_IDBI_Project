#!/usr/bin/env bash
PORT=$1
echo "Testing from Git Bash..."
echo "PDF exists:"
ls -la /tmp/rag_sample.pdf 2>&1
echo ""
echo "=== UPLOAD VERBOSE ==="
curl -v -X POST -F "file=@/tmp/rag_sample.pdf;type=application/pdf" \
  "http://127.0.0.1:${PORT}/rag/api/v1/documents" 2>&1
echo ""
echo "EXIT: $?"
