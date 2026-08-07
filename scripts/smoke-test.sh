#!/usr/bin/env bash
# End-to-end smoke test (requires PostgreSQL on localhost:5432)
set -euo pipefail

API="http://localhost:8000/api"
EMAIL="test-$(date +%s)@example.com"
PASS="testpass123"

echo "==> Register"
TOKEN=$(curl -sf -X POST "$API/auth/register" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"full_name\":\"Test User\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "==> Create project"
PROJECT=$(curl -sf -X POST "$API/projects" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Bot","system_prompt":"You are a helpful assistant."}')
PROJECT_ID=$(echo "$PROJECT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "==> Add prompt"
curl -sf -X POST "$API/projects/$PROJECT_ID/prompts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Greeting","content":"Always greet users warmly."}' > /dev/null

echo "==> Send chat message"
curl -sf -X POST "$API/projects/$PROJECT_ID/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Hello, who are you?"}' | python3 -m json.tool

echo "==> All tests passed"
