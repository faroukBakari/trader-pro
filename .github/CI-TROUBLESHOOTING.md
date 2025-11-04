# CI/CD Troubleshooting Guide

## Common Issues and Solutions

### 1. Poetry not finding pyproject.toml

**Error**: `Poetry could not find a pyproject.toml file`

**Solution**: Ensure the workflow uses `working-directory: backend` for all Poetry commands:

```yaml
- name: Install dependencies
  working-directory: backend
  run: poetry install --no-interaction
```

### 2. npm cache miss or node_modules issues

**Error**: `Cannot find module` or npm install failures

**Solutions**:

- Check `cache-dependency-path: frontend/package-lock.json`
- Use `npm ci` instead of `npm install` in CI
- Ensure `package-lock.json` is committed

### 3. Git hooks not running in CI

**Error**: Hooks don't execute or permission denied

**Solution**: Add hook installation step:

```yaml
- name: Install Git hooks
  run: |
    git config core.hooksPath .githooks
    chmod +x .githooks/*
```

### 4. Test failures in CI but pass locally

**Common causes**:

- Environment differences (CI=true vs local)
- Missing dependencies
- Path issues with new directory structure
- Timezone/locale differences

**Solutions**:

- Check environment variables
- Use absolute paths in tests
- Ensure all deps are in lock files
- Set consistent locale in CI

### 5. Coverage upload issues

**Error**: Coverage file not found

**Solution**: Ensure coverage file path matches workflow:

```yaml
- name: Upload coverage
  uses: codecov/codecov-action@v3
  with:
    file: backend/coverage.xml # Note: backend/ prefix
```

### 6. Matrix build failures

**Error**: Some Python/Node versions fail

**Solutions**:

- Check compatibility in pyproject.toml and package.json
- Use appropriate Python/Node setup actions
- Consider reducing matrix for faster CI

### 7. API endpoint 404 errors in integration tests

**Error**: `curl: (22) The requested URL returned error: 404`

**Common causes**:

- Incorrect API endpoint URLs
- Server not fully started
- Wrong base URL or missing API prefix

**Solutions**:

- Verify endpoint URLs match the FastAPI router configuration
- Check `/api/v1/health` not `/health`
- Check `/api/v1/version` not `/api/v1/api/v1/version`
- Increase sleep time after starting server
- Use health check with retry logic

**Debug API endpoints**:

```bash
# Check what endpoints are available
curl http://localhost:8000/api/v1/docs
# Or check the root endpoint for available routes
curl http://localhost:8000/
```

## Best Practices

### For Backend (Python)

- Pin Poetry version in CI
- Use virtual environments (`virtualenvs-in-project: true`)
- Cache .venv directory with proper key
- Run tests with coverage
- Use `--no-interaction` for Poetry commands

### For Frontend (Node.js)

- Use `npm ci` for reproducible installs
- Cache node_modules properly
- Run build to catch build-time errors
- Use headless mode for browser tests

### For Integration Tests

- Start services in background with `&`
- Use `sleep` or health checks before testing
- Set appropriate timeouts
- Clean up processes after tests

## Local CI Testing

Test CI-like conditions locally:

```bash
# Test backend CI steps
cd backend
poetry install --no-interaction
poetry run pytest --cov=trading_api
poetry run black --check src/ tests/
poetry run isort --check-only src/ tests/
poetry run flake8 src/ tests/
poetry run mypy src/

# Test frontend CI steps
cd frontend
npm ci
npm run lint
npx prettier --check src/
npm run type-check
npm run test:unit run
npm run build

# Test integration
cd backend && poetry run uvicorn "trading_api.main:$BACKEND_APP_NAME" --port 8000 &
sleep 5
curl -f http://localhost:8000/api/v1/health
curl -f http://localhost:8000/api/v1/version
```

## Monitoring CI

- Check GitHub Actions tab for detailed logs
- Monitor build times and optimize slow steps
- Set up notifications for build failures
- Review dependency updates that might break CI

## WebSocket-Specific Issues

### 8. WebSocket Test Failures

**Error**: WebSocket integration tests fail or timeout

**Common causes**:

- Backend not broadcasting WebSocket updates
- WebSocket connection not established
- Subscription not confirmed by backend
- AsyncAPI type generation failed
- Topic builder mismatch between frontend/backend

**Solutions**:

- **Backend Broadcasting**: Verify backend implements broadcasting in `broker_service.py`
- **Connection Check**: Ensure WebSocket endpoint is accessible (`ws://localhost:8000/api/v1/ws`)
- **Subscription Confirmation**: Check backend sends `.subscribe.response` messages
- **Type Generation**: Verify AsyncAPI types generated correctly in `frontend/src/clients/ws-types-generated/`
- **Topic Compliance**: Ensure topic builders match in backend and frontend

**Debug WebSocket tests**:

```bash
# Check if WebSocket endpoint is available
curl --include \
     --no-buffer \
     --header "Connection: Upgrade" \
     --header "Upgrade: websocket" \
     --header "Sec-WebSocket-Version: 13" \
     --header "Sec-WebSocket-Key: $(echo -n 'test' | base64)" \
     http://localhost:8000/api/v1/ws

# Test AsyncAPI spec generation
curl http://localhost:8000/api/v1/ws/asyncapi.json

# Check if backend routers are registered
curl http://localhost:8000/api/v1/ws/asyncapi | jq '.channels'
```

### 9. AsyncAPI Type Generation Errors

**Error**: `make generate-asyncapi-types` fails

**Common causes**:

- Backend not running or AsyncAPI spec not available
- Script permissions issue
- AsyncAPI spec malformed
- Network connectivity issues

**Solutions**:

```bash
# Ensure backend is running first
cd backend && make dev &
sleep 5

# Verify AsyncAPI spec is available
curl http://localhost:8000/api/v1/ws/asyncapi.json

# Check script permissions
chmod +x frontend/scripts/generate-asyncapi-types.sh

# Run generation manually
cd frontend
npm run generate-asyncapi-types
```

### 10. WebSocket Router Generation Failures

**Error**: `make generate` fails in backend

**Common causes**:

- Router type aliases not following pattern
- Python script errors
- Generated directory not writable

**Solutions**:

```bash
# Check router type aliases
grep "TypeAlias = WsRouter" backend/src/trading_api/modules/*/ws.py

# Run generation (uses unified generation command)
cd backend
make generate

# Verify generated routers
ls -la src/trading_api/modules/*/ws_generated/

# Check for syntax errors in generated files
cd backend && make lint
```

### 11. WebSocket Client Fallback Issues

**Error**: Frontend WebSocket clients not using correct mode (mock vs real)

**Common causes**:

- WsFallback not initialized properly
- Mock functions not provided
- Client selection logic broken

**Solutions**:

```typescript
// Verify client selection in tests
describe("WebSocket Client Selection", () => {
  it("should use WsFallback when mock=true", () => {
    const broker = new BrokerTerminalService(host, datafeed, true);
    // Verify internal _getWsAdapter() returns WsFallback
  });

  it("should use WsAdapter when mock=false", () => {
    const broker = new BrokerTerminalService(host, datafeed, false);
    // Verify internal _getWsAdapter() returns WsAdapter
  });
});
```

### 12. Phase 5 TDD Red Phase (Expected Failures)

**Error**: Broker WebSocket integration tests fail

**Status**: ✅ **This is expected!**

These tests are in **TDD Red Phase** and will fail until Phase 5 (Backend Broadcasting) is implemented:

```bash
# Tests currently skipped (expected)
npm run test:unit src/services/__tests__/brokerTerminalService.spec.ts
# Output: ⏭️ 10 tests skipped
```

**Not a failure if**:

- Tests are properly skipped with `.skip()`
- Test infrastructure is in place
- Mocks are correctly implemented

**Actual failure if**:

- Tests run and crash (not gracefully skip)
- Type errors in test code
- Mock setup broken

### 13. Per-Module Spec Generation Issues (Phase 4)

**Error**: Module specs not found or artifacts missing

**Common causes**:

- Backend specs not exported correctly
- Artifact download path mismatch
- Module discovery failed

**Solutions**:

```bash
# Verify per-module specs are generated
cd backend
make generate  # Unified: generates OpenAPI, AsyncAPI, Python clients
ls -la src/trading_api/modules/*/specs_generated/*.json

# Should see:
# broker/specs_generated/broker_openapi.json
# broker/specs_generated/broker_asyncapi.json
# datafeed/specs_generated/datafeed_openapi.json
# datafeed/specs_generated/datafeed_asyncapi.json
```

**Debug artifact paths**:

```yaml
# In CI, artifacts are uploaded from:
path: backend/src/trading_api/modules/*/specs_generated/*.json

# Downloaded to:
path: backend/src/trading_api/modules/
# This recreates the directory structure
```

### 14. Python Client Generation Failures (Phase 4)

**Error**: Backend Python clients not generated or type checks fail

**Common causes**:

- Specs not available (missing artifact download)
- Jinja2 template errors
- Model import issues
- Type annotation problems

**Solutions**:

```bash
# Test locally
cd backend
make generate  # Includes Python client generation

# Should see:
# ✅ Generated broker_client.py
# ✅ Generated datafeed_client.py
# ✅ All type checks pass

# Verify clients exist
ls -la src/trading_api/clients/
# broker_client.py
# datafeed_client.py
# __init__.py
```

**Debug type checking**:

```bash
cd backend
poetry run mypy src/trading_api/clients/
poetry run pyright src/trading_api/clients/
```

### 15. Frontend Per-Module Client Generation Issues (Phase 4)

**Error**: Frontend clients not generated correctly

**Common causes**:

- Backend specs not downloaded
- Script fails to find module specs
- Client directory naming mismatch
- Type generation errors

**Solutions**:

```bash
# Test locally
cd frontend
make generate-openapi-client
make generate-asyncapi-types

# Verify clients exist
ls -la src/clients/
# Should see:
# trader-client-broker/
# trader-client-datafeed/
# ws-types-broker/
# ws-types-datafeed/

# Run type checks
make type-check
```

**Debug CI verification**:

```yaml
# CI checks for these directories
if [ ! -d "src/clients/trader-client-broker" ]; then
echo "❌ Broker client generation failed"
exit 1
fi
```

---

## Emergency Procedures

### Skip CI temporarily

```bash
git commit -m "fix: urgent fix [skip ci]"
```

### Debug CI failures

1. Check the full logs in GitHub Actions
2. Look for the first failure in the workflow
3. Test the failing command locally
4. Check if dependencies changed
5. Verify directory structure matches workflow

### Debug WebSocket CI failures

1. Check if backend WebSocket endpoint is accessible
2. Verify AsyncAPI spec generation works
3. Test WebSocket router generation
4. Check frontend type generation
5. Verify Phase 5 TDD status (tests should be skipped, not failing)

### Rollback problematic changes

```bash
git revert HEAD
git push
```
