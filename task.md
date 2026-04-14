# Production Upgrade Task List

## Phase 1: Dependencies & Auth Backend
- [/] Update `requirements.txt` (add bcrypt, PyJWT)
- [/] Create `auth.py` (register, login, logout, JWT, SQLite, history saving)

## Phase 2: Core App Logic
- [ ] Rewrite `app.py` (auth integration, role eligibility engine, LinkedIn URLs, history route)

## Phase 3: Design System
- [ ] Rewrite `static/style.css` (premium glassmorphism, animated background, responsive)
- [ ] Create `templates/base.html` (shared navbar, footer, scripts)

## Phase 4: Auth Templates
- [ ] Create `templates/login.html`
- [ ] Create `templates/register.html`
- [ ] Create `templates/history.html`

## Phase 5: Core Templates
- [ ] Rewrite `templates/index.html`
- [ ] Rewrite `templates/upload.html`
- [ ] Rewrite `templates/result.html`

## Phase 6: Verification
- [ ] Check all templates render correctly
- [ ] Confirm auth flow works
- [ ] Confirm LinkedIn links generate correctly
