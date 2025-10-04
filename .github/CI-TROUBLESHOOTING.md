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
    file: backend/coverage.xml  # Note: backend/ prefix
```

### 6. Matrix build failures

**Error**: Some Python/Node versions fail

**Solutions**:
- Check compatibility in pyproject.toml and package.json
- Use appropriate Python/Node setup actions
- Consider reducing matrix for faster CI

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
cd backend && poetry run uvicorn trading_api.main:app --port 8000 &
sleep 5
curl -f http://localhost:8000/health
```

## Monitoring CI

- Check GitHub Actions tab for detailed logs
- Monitor build times and optimize slow steps
- Set up notifications for build failures
- Review dependency updates that might break CI

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

### Rollback problematic changes
```bash
git revert HEAD
git push
```