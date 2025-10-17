# Smoke Tests

This directory contains Playwright smoke tests for the Trader Pro application.

## Purpose

These smoke tests validate that the basic functionality of the full-stack application works correctly:

- Frontend loads properly
- Backend API is accessible
- Status page displays correct information
- API connectivity is working
- Basic user interface elements are present

## Structure

```
smoke-tests/
├── package.json          # Test dependencies
├── playwright.config.ts  # Playwright configuration
├── run-tests.sh          # Test runner script
├── tests/
│   └── status-page.spec.ts  # Status page smoke tests
└── README.md             # This file
```

## Running Tests

### Quick Run

```bash
# From the smoke-tests directory
./run-tests.sh
```

### Manual Setup

```bash
# Install dependencies
npm install

# Install Playwright browsers
npx playwright install

# Run tests (this will start the full-stack environment)
npm test

# Run tests with browser visible (for debugging)
npm run test:headed

# Debug tests interactively
npm run test:debug

# View test report
npm run test:report
```

## Test Configuration

The tests are configured to:

- Use `make -f ../project.mk dev-fullstack` to start the full-stack environment
- Wait up to 2 minutes for the backend and frontend to be ready
- Run against `http://localhost:5173` (frontend) and `http://localhost:8000` (backend)
- Test against multiple browsers (Chrome, Firefox, Safari)
- Generate HTML reports for test results

**Environment Startup Sequence:**

1. Port availability check (ports 8000 and 5173)
2. Backend starts with Uvicorn --reload
3. Health check waits for backend ready (max 60s)
4. Client generation (OpenAPI + AsyncAPI)
5. Frontend starts with Vite
6. File watchers monitor for spec changes
7. Tests run against running services

## Test Scenarios

### Status Page Tests (`status-page.spec.ts`)

1. **Page Loading**: Verifies the status page loads correctly
2. **API Health**: Checks that backend API health status is displayed
3. **Version Information**: Validates version information is shown
4. **Error Handling**: Ensures graceful handling of API connectivity issues
5. **Navigation**: Tests navigation to status-related views
6. **Loading States**: Verifies proper loading indicators during API calls

## Test Data Requirements

The tests expect certain data-testid attributes in the frontend components:

- `api-status`: Main API status component
- `health-status`: Health status display
- `version-info`: Version information display
- `loading`: Loading indicators
- `error`: Error message containers

## CI Integration

These tests can be integrated into CI/CD pipelines to validate deployments:

```yaml
# Example GitHub Actions step
- name: Run Smoke Tests
  run: |
    cd smoke-tests
    ./run-tests.sh
```

## Troubleshooting

### Tests Fail to Start

- Ensure Poetry is installed for backend dependencies
- Ensure Node.js/npm is installed for frontend dependencies
- Check that ports 8000 (backend) and 5173 (frontend) are available

### Tests Timeout

- The full-stack environment takes time to start (up to 2 minutes)
- Increase timeout in `playwright.config.ts` if needed
- Check that both backend and frontend start successfully manually

### Browser Issues

- Run `npx playwright install` to ensure browsers are available
- Use `npm run test:headed` to see what's happening in the browser
- Use `npm run test:debug` for interactive debugging
