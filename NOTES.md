# Notes

## Stack

- **Backend:** Python 3.12 + Flask 3 (single `app.py`). State-machine rules live in `service/queue.py` so they're framework-free and trivially testable.
- **Frontend:** Vue 3 loaded via CDN in a single `static/index.html`, Composition API in `static/app.js`. No build step, no npm — reviewer just runs the Flask server and opens a browser.
- **Storage:** in-memory `ItemStore` seeded from `review_items.json` on boot, protected by a `threading.Lock` so Flask's threaded dev server stays consistent under concurrent requests. No persistence beyond process lifetime.
- **Tests:** `unittest` (stdlib) — 18 tests covering sort order, every valid transition, every invalid transition, terminal immutability, and allowed-action derivation.

## How to run

```bash
python3 -m venv .venv
.venv/bin/pip install flask
.venv/bin/python -m unittest discover -s tests    # 18 tests
.venv/bin/python app.py                           # http://127.0.0.1:5000
```

## Assumptions

- **Reviewer identity is hardcoded** to `alex`. Exposed via `GET /api/reviewer` so the frontend can display "Signed in as alex" without duplicating the constant.
- **`in_review` items assigned to someone else are still visible in the queue.**
- **Claim records the reviewer, nothing else.**
- **No pagination.** The seed has 12 items.

## Tradeoffs

- **Flask over stdlib `http.server`:** More dependency, far less boilerplate.
- **Vue via CDN over Vite:** No build step, no `node_modules`, no lockfile. The cost is I can't write true single-file components (`.vue`), so the template lives inside `index.html`.
- **Deepcopy on every action:** Simpler than tracking dirty fields and eliminates aliasing bugs.
- **Queue refresh after action instead of optimistic update:** Less code, correct by construction, slightly more network chatter.

## What I'd do next with more time

1. **Audit log.** Every action should record `{actor, action, from_status, to_status, at}`.
3. **Real persistence.** SQLite with SQLAlchemy.
4. **Per-action notes.** Let the reviewer attach a short justification to approvals, rejections, and especially escalations.
5. **Frontend tests.** I would add Cypress smoke tests covering claim, approve etc.
6. **Auth.** Read the reviewer identity from a session cookie instead of a hardcoded constant.
7. **Pessimistic-lock claims.** If two reviewers hit claim at the same moment, the current code already rejects the second one (the lock serializes the read-modify-write) and returns 409. I'd surface that cleanly in the UI as "Someone else just claimed this — refreshing queue" instead of a generic error toast.

