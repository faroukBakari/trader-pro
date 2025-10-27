# Authentication & Session Management - SSO Implementation

**Status**: Ready for Implementation  
**Last Updated**: October 27, 2025  
**Approach**: Google SSO + Single Account + Pickle Persistence

## Summary

Google OAuth 2.0-based authentication with lightweight session management:

- **Authentication**: Google SSO (no password management)
- **Storage**: Pickle files (MVP), migrate to Redis later
- **Account Model**: Single account per user
- **Session Delivery**: `X-Session-Id` header (REST), `?sessionId=` param (WebSocket)

## Design Decisions

- **SSO Provider**: Google OAuth 2.0
- **Session Storage**: Pickle files → Redis (production)
- **Account Model**: Single account per user (multi-account deferred)
- **Token Storage**: sessionStorage (cleared on tab close)
- **No email verification** (Google handles it)

## Architecture

```
Frontend                                Backend
━━━━━━━                                 ━━━━━━━
1. Google OAuth → Google ID Token
2. POST /auth/google {token}        →  Validate with Google API
3. Store sessionId                  ←  Create session → sessions.pkl
4. X-Session-Id header (REST)       →  Extract accountId
5. ?sessionId= param (WebSocket)    →  Validate & store in ws.state
```

**Session Structure**:

```python
{
  "session_id": "uuid-v4",
  "user_id": "google-oauth2|123456789",
  "email": "user@gmail.com",
  "account_id": "ACC-{hash}",  # Single account
  "created_at": timestamp,
  "expires_at": timestamp
}
```

**Flow**:

1. User clicks "Sign in with Google" → OAuth flow → ID token
2. Backend validates token → creates session → returns sessionId
3. Frontend stores sessionId (sessionStorage)
4. Auto-inject: REST (`X-Session-Id` header), WebSocket (`?sessionId=` param)
5. Backend validates session → extracts accountId → processes request

## Implementation

### Backend Structure

```
backend/src/trading_api/
├── models/auth/
│   ├── user.py          # User, UserInfo
│   ├── google_auth.py   # GoogleTokenRequest, GoogleUserInfo
│   └── session.py       # Session, SessionInfo, LoginResponse
├── core/
│   └── auth_service.py  # AuthService (pickle persistence)
├── dependencies/
│   └── auth.py          # get_current_session, get_account_id
├── api/
│   └── auth.py          # /auth endpoints
└── plugins/
    └── fastws_adapter.py # ws_auth_handler
```

### Key Models

```python
# user.py
class User(BaseModel):
    id: str                    # "google-oauth2|123456789"
    email: str
    name: str
    picture: str | None = None
    email_verified: bool
    created_at: int
    last_login: int

# session.py
class Session(BaseModel):
    session_id: str            # UUID v4
    user_id: str
    email: str
    account_id: str            # Single account: ACC-{hash}
    created_at: int
    expires_at: int

class LoginResponse(BaseModel):
    session: SessionInfo
    message: str
```

### AuthService (Simplified)

```python
class AuthService:
    """Google SSO + Pickle persistence"""

    def __init__(self):
        self._users: Dict[str, User] = {}
        self._sessions: Dict[str, Session] = {}
        self._load_from_disk()

    def _load_from_disk(self):
        """Load from data/sessions.pkl and data/users.pkl"""

    def _save_to_disk(self):
        """Save to pickle files"""

    async def verify_google_token(self, token: str) -> GoogleUserInfo:
        """Verify with google.oauth2.id_token.verify_oauth2_token"""

    async def login_with_google(self, token_request: GoogleTokenRequest) -> LoginResponse:
        """Validate token → create/update user → create session"""

    async def validate_session(self, session_id: str) -> Session:
        """Validate session exists and not expired"""

    def _generate_account_id(self, user_id: str) -> str:
        """ACC-{sha256(user_id)[:8]}"""
```

### Dependencies & Endpoints

```python
# dependencies/auth.py
async def get_current_session(
    x_session_id: Annotated[str, Header(alias="X-Session-Id")]
) -> Session:
    return await auth_service.validate_session(x_session_id)

async def get_account_id(session: Session = Depends(get_current_session)) -> str:
    return session.account_id

# api/auth.py
@router.post("/auth/google", response_model=LoginResponse)
async def login_with_google(token_request: GoogleTokenRequest):
    return await auth_service.login_with_google(token_request)

@router.post("/auth/logout")
async def logout(session: Session = Depends(get_current_session)):
    await auth_service.logout(session.session_id)

@router.get("/auth/me", response_model=UserInfo)
async def get_current_user_profile(session: Session = Depends(get_current_session)):
    return await auth_service.get_session_info(session.session_id).user
```

### WebSocket Authentication

```python
# plugins/fastws_adapter.py
async def ws_auth_handler(ws: WebSocket) -> bool:
    """Validate ?sessionId= query param"""
    await ws.accept()

    session_id = ws.query_params.get("sessionId")
    if not session_id:
        await ws.close(code=1008, reason="sessionId required")
        return False

    session = await auth_service.get_session(session_id)
    if not session:
        await ws.close(code=1008, reason="Invalid or expired session")
        return False

    # Store in WebSocket state
    ws.state.session = session
    ws.state.account_id = session.account_id
    return True

# Configure in main.py
wsApp = FastWSAdapter(auth_handler=ws_auth_handler, auto_ws_accept=False)
```

### Frontend Implementation

```typescript
// stores/authStore.ts
export const useAuthStore = defineStore("auth", {
  state: () => ({
    session: null as SessionInfo | null,
    isAuthenticated: false,
  }),

  actions: {
    async loginWithGoogle() {
      // Load Google Identity Services
      await this.loadGoogleIdentityServices();

      // Init Google OAuth client
      const client = google.accounts.oauth2.initTokenClient({
        client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
        scope: "openid email profile",
        callback: async (response) => {
          const loginResponse = await apiAdapter.loginWithGoogle({
            token: response.access_token,
          });
          this.session = loginResponse.session;
          this.isAuthenticated = true;
          apiAdapter.setSessionId(this.sessionId!);
        },
      });

      client.requestAccessToken();
    },

    async logout() {
      await apiAdapter.logout();
      this.session = null;
      this.isAuthenticated = false;
      apiAdapter.setSessionId(null);
    },
  },

  persist: {
    storage: sessionStorage,
    paths: ["session"],
  },
});

// services/apiAdapter.ts
class ApiAdapter {
  private sessionId: string | null;

  setSessionId(sessionId: string | null) {
    this.sessionId = sessionId;
    // Recreate config with X-Session-Id header
    this.apiConfig = new Configuration({
      headers: sessionId ? { "X-Session-Id": sessionId } : {},
    });
  }
}

// clients/wsClientBase.ts
class WebSocketBase {
  private getWebSocketUrl(): string {
    const sessionId = useAuthStore().sessionId;
    if (!sessionId) throw new Error("No active session");
    return `${baseUrl}/ws?sessionId=${encodeURIComponent(sessionId)}`;
  }
}
```

## Implementation Plan

**Timeline: 6-8 days**

### Phase 1: Backend Setup (1 day)

- Install `google-auth`, `google-auth-oauthlib`
- Create auth models (user.py, session.py, google_auth.py)
- Setup data directory, add `data/*.pkl` to .gitignore
- Add `GOOGLE_CLIENT_ID` to `.env`

### Phase 2: AuthService (1-2 days)

- Implement AuthService with pickle persistence
- Create dependencies (get_current_session, get_account_id)
- Create /auth endpoints (POST /google, POST /logout, GET /me)
- Generate OpenAPI spec
- Write tests (test_auth_service.py, test_api_auth.py)

### Phase 3: WebSocket Auth (1 day)

- Implement ws_auth_handler (validate sessionId param)
- Update main.py with auth_handler
- Write WebSocket auth tests

### Phase 4: Frontend (1-2 days)

- Generate TypeScript client
- Create/update authStore (Google OAuth integration)
- Update ApiAdapter (X-Session-Id header injection)
- Update WebSocketBase (?sessionId= param)
- Add router guards
- Create login UI with "Sign in with Google"
- Add `VITE_GOOGLE_CLIENT_ID` to .env

### Phase 5: Broker Auth (1 day, optional)

- Add get_account_id dependency to broker endpoints
- E2E testing: login → place order → logout

### Phase 6: Integration & Docs (1 day)

- Manual testing
- Update ARCHITECTURE.md, ENVIRONMENT-CONFIG.md
- Smoke tests

## Security

### Google SSO

- Validate tokens server-side with `google.oauth2.id_token.verify_oauth2_token`
- Never trust client-side validation
- Verify issuer, audience, expiration

### Session Management

- Secure tokens: `secrets.token_urlsafe(32)`
- Session expiration: 7 days (configurable)
- Invalidate on logout

### Pickle Files

- Restrict permissions: `chmod 600 data/*.pkl`
- Add to `.gitignore`
- **Warning**: Pickle can execute arbitrary code if tampered - trusted env only
- Production: Migrate to Redis/PostgreSQL

### CORS

```python
CORS_ORIGINS=http://localhost:5173,https://accounts.google.com
```

### Environment Variables

```bash
# backend/.env
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
SESSION_EXPIRE_DAYS=7

# frontend/.env
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
```

### Production Considerations

1. **Replace Pickle**: Use Redis (sessions) + PostgreSQL (users)
2. **HTTPS Only**: `secure=True` on cookies, HSTS headers
3. **Rate Limiting**: Protect `/auth/google` endpoint
4. **Token Refresh**: Implement Google refresh token flow

## Testing

### Backend Tests

```python
# test_auth_service.py
- test_verify_google_token_valid/invalid
- test_create_session
- test_validate_session (valid/expired/invalid)
- test_logout_invalidates_session
- test_pickle_persistence/loading

# test_api_auth.py
- test_google_auth_endpoint (valid/invalid token)
- test_get_user_info (with/without session)
- test_logout_endpoint

# test_ws_auth.py
- test_websocket_requires_session
- test_websocket_with_valid/invalid_session
- test_websocket_session_in_state
```

### Frontend Tests

```typescript
// authStore.spec.ts
- Google OAuth initialization
- Login flow and session storage
- Logout and session cleanup
- Session persistence/restoration

// apiAdapter.spec.ts
- X-Session-Id header injection
- Session updates

// wsClientBase.spec.ts
- sessionId query param
- Reconnection on session change
```

### Integration Tests

```typescript
// smoke-tests/google-auth-flow.spec.ts
- Full OAuth flow (mock Google response)
- Session creation and storage
- Authenticated API calls
- WebSocket with session
- Logout
```

**Testing Notes**:

- Mock `google.oauth2.id_token.verify_oauth2_token` in unit tests
- Use separate pickle files for tests
- Use `freezegun` for time-based expiration tests

## Dependencies

### Backend

```bash
poetry add google-auth google-auth-oauthlib
```

### Frontend

```html
<!-- index.html -->
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

### Environment Setup

```bash
# backend/.env
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
SESSION_EXPIRE_DAYS=7
CORS_ORIGINS=http://localhost:5173,https://accounts.google.com

# frontend/.env
VITE_GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
```

## Success Criteria

### Functional

- ✅ Users can login with Google SSO
- ✅ Sessions persisted to pickle files
- ✅ Sessions expire after configured duration
- ✅ REST API validates X-Session-Id header
- ✅ WebSocket validates ?sessionId= param
- ✅ Frontend: OAuth flow, session storage, auto-injection

### Security

- ✅ Server-side Google token validation
- ✅ Cryptographically secure session tokens
- ✅ Restricted pickle file permissions (600)
- ✅ CORS configured for Google domains

### Testing

- ✅ Unit tests for AuthService, API endpoints, WebSocket auth
- ✅ Frontend tests for auth store, API adapter, WebSocket client
- ✅ E2E test: login → API call → logout

### Documentation

- ✅ ENVIRONMENT-CONFIG.md updated with Google credentials
- ✅ ARCHITECTURE.md updated with auth flow
- ✅ API docs show authentication requirements

## Questions

1. Google Cloud Console setup needed?
2. Session expiration: 7 days or custom?
3. Pickle location: `data/` directory OK?
4. Add broker auth now or later?
5. Login page or just "Sign in with Google" button?
6. Test Google account or mocked tokens?

Ready to start implementation following TDD methodology.
