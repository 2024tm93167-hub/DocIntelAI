# DocIntel AI — persistent project state

Last audit: 2026-09-14 (editor redesign). Read this before continuing. Inspect actual code; do not assume earlier conversation claims or README completion statements are correct.

## Working rules and continuity
- Preserve the existing Angular/FastAPI application and all existing user data. Many files were already modified/untracked at audit start; do not reset, clean, or discard them.
- Never read/print `.env` or service-account files, bypass ignored-file access restrictions, or send live AI requests without approval. A provider key was exposed in an earlier conversation; user has been advised to rotate it.
- Current agent instructions restrict new plan/report documents. This allowed project-info file consolidates the requested plan, architecture, API/schema inventory, status, changelog, and handoff. Separate PROJECT_PLAN.md, IMPLEMENTATION_STATUS.md, ARCHITECTURE.md, API_REFERENCE.md, DATABASE_SCHEMA.md, NEXT_STEPS.md, CHANGELOG_AI.md and academic docs remain uncreated, not completed.
- Keep statuses and next actions accurate after every meaningful unit of work. Do not claim live collaboration, browser usability, or academic evaluation is verified by mocked unit tests.
- Do not add dependencies/framework upgrades without need. Do not change Firestore rules or security settings to pass checks. Never run migrations/deployments or delete real records without specific approval.

## Audit: existing architecture
- Angular 22.1, standalone lazy-routed components, Angular Material 22, signals for UI state, RxJS 7.8 for HTTP/forms, TypeScript 6. TipTap 3.29. Firebase JS Auth 12.17. Vitest via Angular unit-test builder (only one initial smoke test).
- Routes: `/auth/login`, `/auth/register`, `/dashboard`, `/documents/:id`; auth/guest guards use Firebase readiness. API interceptor adds Firebase ID token. No browser Firestore data access.
- Frontend structure: `core/{models,services,guards,interceptors,pipes}`, `auth`, `dashboard`, `documents/editor`, shared confirmation and diff dialogs. Keep these sensible feature boundaries; do not mass-move folders.
- Editor: TipTap/ProseMirror JSON, rich toolbar (headings, marks, lists, links, tables, image, alignment etc.), debounced autosave, manual versions, AI/results panel, stats/export. `editor.ts` is ~936 lines at audit: toolbar, saving, AI, resize, versions, stats all coupled. Extract by responsibility incrementally with tests.
- UI: existing Material theme and `--docintel-*` design tokens are reusable. Dashboard cards and analytics exist. No search/sort/shared list/sidebar; document list errors are swallowed. Editor has no responsive media rules; canvas can overflow when side panel grows; resize has no keyboard/cancel handling, unclamped persisted width.
- FastAPI 0.141/Pydantic 2.13, Python 3.13 environment, Firebase Admin/Auth and synchronous Firestore client. Routers + domain models + schemas + repositories + provider abstraction already exist.
- Database is **Cloud Firestore**, NOT SQLAlchemy. No SQL migration/Alembic needed. Keep JSON content and Firestore; add compatible fields/transactions rather than replacing storage. Direct client access denied by existing Firestore rules. Composite indexes file empty; existing queries filter one field then sort/materialize all results in Python.
- Auth verifies bearer Firebase ID tokens; all document/version/export access currently owner-only. Sync auth/Firestore calls from async endpoints block event loop. Move synchronous work to threadpool via sync dependencies/routes or explicit offloading.
- Providers: OpenAI-compatible + Ollama, non-stream generation and streaming. Generate streams plain text; rewrite/summarize return JSON. No persistent suggestions/context service, rate limits, evaluation events, or real chat history.

## API reference (audit baseline)
All except `/health` require Firebase bearer token. No `/api` prefix; retain routes for compatibility.
- GET `/health`; GET `/users/me` provisions profile.
- GET/POST `/documents`; GET/PATCH/DELETE `/documents/{id}`.
- GET/POST `/documents/{id}/versions`; GET/DELETE `/documents/{id}/versions/{version_id}`.
- GET `/documents/{id}/versions/{version_id}/diff?compare_to={other_version}`; absent compare_to means current stored document. Highlighted equal/insert/delete/replace chunks, not structured formatting diffs.
- POST `/ai/rewrite` {text, instruction?}, POST `/ai/summarize` {text, max_words?}: {output}.
- POST `/ai/generate` {prompt}: streamed plain text at baseline.
- GET `/analytics`; GET `/documents/{id}/stats`, `/evaluate`, `/export?format=markdown|html|text|docx|pdf`. Export now allows any collaborator (viewer+); stats/evaluate remain owner-only.
- PATCH now requires `base_revision` alongside changes; stale writes return 409. Response adds revision/updated_by/owner_id. Old frontend bundles must reload after deployment. POST `/documents/{id}/versions/{version_id}/restore` requires base_revision and returns updated DocumentOut. No sharing/suggestions/WebSocket endpoints yet.

## Database schema (audit baseline)
Top-level collections (version model docstring incorrectly describes nesting):
- `users/{uid}`: name, email, createdAt, lastLoginAt.
- `documents/{id}`: ownerId, title, content (TipTap JSON), wordCount, createdAt, updatedAt.
- `versions/{id}`: documentId, ownerId, title, content, wordCount, label, createdAt; now also createdBy, authorName, source, documentRevision, restoredFromVersionId. Legacy records use safe defaults.
- `editingSessions`, `evaluationResponses`: accessor stubs only, not implemented workflows.
- No revision/CAS, access-control membership, source/sequence/author display, automatic checkpoints, restoration transactions, or pagination at baseline. Firestore has no foreign keys; application must enforce document/version relationships.

## Findings and priorities
These are audit-baseline findings, not all current defects. See implementation status and handoff for fixes already completed.
P0:
1. Analytics tests contact real Firestore despite README claiming isolation. Initial baseline test run created five `Analytics Test` records under `owner-uid`. User notified. Do not clean up without approval. Block live Firebase in all tests and supply explicit test doubles before any further test execution.
2. HTML export interpolates title and heading level unsafely; link attributes escaped but javascript/data URLs not filtered. Unicode filenames may fail Latin-1 response headers. Fix with allowlists/escaping and regression tests.
3. Save requests can overlap, last writer silently wins, dirty state cleared by old response, no leave guard. Firestore atomic revision checks plus serialized/coalesced autosave and conflict recovery required before collaboration.
P1:
4. Provider failures midstream are swallowed as successful EOF. Unused frontend generate() expects JSON from text endpoint. Streams/subscriptions not always cancelled on destroy/mode changes. AI output inserted as HTML instead of explicit text; selected range not pinned to original request.
5. Content JSON is unconstrained, client supplies word count; payload shape/depth/size need validation before recursive exporters/diff or Firestore 1 MiB limit.
6. Version save may snapshot stale server content before autosave. No restore/automatic snapshots; history lists full content internally and no pagination. Diff uses duplicated text conversion with inconsistent node naming.
7. Sync SDK calls inside async routes; auth interceptor uses raw URL prefix rather than origin/path boundary.
8. No share permissions, live presence, conflict UI, document recommendation persistence, evaluation data or user-testing results.
P2: responsive/accessibility polish; sidebar/dashboard search/sort; toolbar/editor decomposition; pagination/indexes; performance/evaluation methodology.

## Target architecture and ordered phases
Retain Angular signals/Material/TipTap + FastAPI/Firebase Auth + Firestore. Structured JSON is canonical, plain text only for LLM context/diff, safe serializers for export. All LLM calls backend-only. No CRDT for initial prototype.
1. Audit + reliable isolated verification + safe export/auth boundaries.
2. Validated document schema, atomic optimistic revision updates, serialized autosave, local-draft/conflict recovery. Legacy documents default revision 0; additive fields, no destructive migration.
3. Version service: bounded automatic checkpoints, explicit snapshots after save acknowledgment, source/actor/sequence, transactional pre-restore snapshot + restore. Two-version comparison UI and confirmations.
4. Dedicated bounded-context prompt/action service; streamed delta/done/error protocol; AI request lifecycle/range validation; grammar/tone/continue/outline; result copy/regenerate/apply/discard.
5. Contextual recommendation records with accepted/rejected status and stale-range checks.
6. Owner/editor/viewer ACL service across every router; safe UID resolution/sharing UI. Only after ACL tests, add authenticated realtime notifications/presence with revision conflicts (no last-writer-wins).
7. Dashboard/editor SaaS shell redesign with reuse of current tokens/components; keyboard/responsive panels, search/sort/recent/shared, proper loading/error/empty states.
8. Security/performance/accessibility regression suite, bounded pagination/index rollout (approval if configuration needed), academic evaluation instrumentation/methodology and manual user-testing questionnaire.

## Acceptance criteria
- Every write authenticates/authorizes on backend; concurrent writes from same base revision cannot both commit. UI retains rejected local content; no automatic force overwrite.
- Snapshots/restore preserve history and capture actor/time/source; rejected/failed restore leaves current document intact.
- AI results preview only; acceptance applies once to intended content and becomes undoable. Failure/stop distinguish partial output from success.
- Tests never use live Firebase/provider credentials. Build and meaningful unit tests pass. Browser/manual multi-user verification and evaluation results recorded separately.
- Desktop editor and keyboard resize work; mobile no horizontal overflow; user can distinguish unsaved/saving/saved/error/conflict.

## Implementation status
Key: [x] verified unit/build scope, [~] partial/in progress, [ ] not started, [!] blocked.
| Feature | Frontend | Backend | Database | Testing |
|---|---|---|---|---|
| Audit/baseline | [x] build | [x] inspected | [x] mapped | [~] baseline unsafe DB access found |
| Auth + owner CRUD | [~] working existing | [~] owner enforced | [~] existing Firestore | [~] narrow mocks |
| Safe export + isolated tests | [x] export menu/buttons incl. DOCX/PDF | [x] md/html/txt + DOCX (python-docx) + PDF (reportlab) via `utils/exporters.py`; viewer+ access | no migration | [x] backend converter + ACL tests; [ ] open generated files manually |
| Revisions/conflict/autosave | [x] serialized queue, dirty/failed/conflict states, retry/draft download/reload, leave warning | [x] owner-checked transaction CAS | [x] additive revision/updatedBy with legacy revision 0 | [x] unit tests; [ ] live multi-tab/emulator |
| Rich text editor | [~] existing; keyboard/cancel-safe responsive panel | [x] bounded JSON validation | [x] JSON storage | [x] AI range/text and resize tests; [ ] browser usability |
| AI generation/rewrite/summary | [x] failure-aware parser, pinned range, text-only acceptance, cancellation | [x] NDJSON delta/done/error negotiation, legacy text retained | n/a | [x] provider/parser/editor regression tests |
| AI prompt/action service | [x] new modes (grammar, tone, continue, outline, custom) + context-aware prompts | [x] bounded-context `ai_actions` service, unified `/ai/action` + `/ai/actions` endpoints, legacy endpoints preserved | n/a | [x] action service + endpoint tests |
| Persistent suggestions | [x] `SuggestionService` + model + suggestion-list component with filter/accept/reject/delete | [x] create/list/accept/reject/delete with stale-revision checks | [x] `suggestions` collection with documentRevision + status + resolvedBy | [x] backend + frontend service + component tests |
| Contextual recommendations | [~] suggestion persistence + UI done; contextual generation from editor pending | [x] suggestion persistence + stale checks | [x] suggestions collection | [x] service + component tests |
| Versions/diff | [x] extracted history component, two-snapshot comparison | [x] manual snapshots + diff | [x] actor/name/source/document revision fields with legacy defaults | [x] history UI tests; [ ] large-document diff/performance |
| Restore/automatic history | [x] confirmation, editing lock, conflict handling, autosave label rendered | [x] transactional restore + bounded automatic checkpoints | [x] pre/post restore snapshots + autosave checkpoints; lastCheckpointAt on documents | [x] backend + frontend tests; [ ] live transaction verification |
| Sharing/roles | [x] `SharingService` + share dialog with invite/remove | [x] owner/editor/viewer ACLs on every document/version/suggestion endpoint; email-based invite resolves to UID | [x] `documentCollaborators` collection | [x] 16 backend ACL tests + 3 frontend service tests; [ ] live multi-user verification |
| Collaboration/presence | [x] `DocumentWsService` + presence indicator in editor header | [x] WebSocket `/ws/documents/{id}` with token auth + viewer ACL; `ConnectionManager` broadcasts presence/document_updated/version_created; update/restore endpoints broadcast | [x] in-memory connection manager (single-process) | [x] 8 backend WS tests + 6 frontend service tests; [ ] live multi-tab verification |
| Dashboard/polish/accessibility | [~] basic cards/theme | [~] list endpoints | [ ] pagination | [ ] browser |
| Editor redesign (page-first) | [x] gray workspace + centered A4-like white page, compact title/save row, formatting toolbar, AI-first inspector with tabs (AI/Suggestions/History/Stats), collapse, mobile overlay | n/a | n/a | [x] editor/version-history/suggestion-list tests updated; [ ] browser usability |
| AI response cleanup | [x] preview-only AI in inspector, explicit insert/replace/copy/regenerate/discard, stale-document refusal, title-only suggestions | [x] `clean_writing()` strips echoed context labels from provider output; streaming endpoint buffers + cleans before emitting; structured title/analysis JSON validated by Pydantic | n/a | [x] backend AI/action/suggestion tests; [ ] live provider verification |
| Suggestion replacement | [x] accept sends `base_revision`, stale → 409, accept modifies matched text via editor transaction | [x] revision-aware accept in single Firestore transaction; unique-passage match; status guard | [x] `suggestions` collection | [x] backend + frontend tests; [ ] live provider verification |
| Academic evaluation | [ ] | [ ] | [ ] | [ ] no actual results |
| Requested separate docs | [!] restricted by current agent instructions | n/a | n/a | n/a |

## Commands and baseline verification
Run from repo subdirectory as indicated. Existing installed dependencies sufficient; no installation/upgrade required for this session.
- Backend: `cd backend` then `venv/bin/python -m pytest -q`; autouse fixture now blocks live Firebase and analytics uses per-test repository doubles.
- Backend launch: `venv/bin/uvicorn app.main:app --reload --port 8000`. `run.sh` also installs requirements and runs tests. Never use Windows run.bat on macOS.
- Frontend: `cd frontend`, `npm start`; production compile `npm run build`; unit suite `npm test -- --watch=false`.
- Baseline 2026-09-13: backend 36 passed with Starlette/httpx deprecation warning (unsafe live analytics tests); frontend 1 smoke test passed; production build passed (initial bundle ~233 kB, lazy editor ~524 kB). Not E2E evidence.
- Environment examples already exist; no real secret files inspected this audit. Current frontend API host configured as http://127.0.0.1:8000. Production requires deployment-specific API host.
- No database migration command for existing Firestore. Do not run firebase deploy without user approval.

## Next steps / active handoff
Current work: editor redesign + AI response cleanup COMPLETE (unit/build scope). The editor is now a page-first word-processor workspace with a preview-only AI inspector, clean AI output (no context labels), revision-aware suggestion replacement, compact version-history timeline with friendly authors, and a clean production build (no warnings, no budget increase). Backend 202 tests pass; frontend 88 tests pass.
1. Live browser verification is the next priority. Walk through the manual acceptance scenarios below (create → type → select → Improve Writing → replace → analyze → accept suggestion → suggest title → choose title → manual version → compare → restore → collapse panel → refresh). Use the frontend at `http://localhost:4200` and backend at `http://127.0.0.1:8000`. The backend CORS default allows `http://localhost:4200` only; running the frontend on another port causes CORS preflight failures. Expired Firebase tokens cause WebSocket 403s — refresh/login to get a fresh token.
2. Live AI provider verification: with approved credentials, confirm `clean_writing()` strips any echoed labels from real provider output and that title/analysis endpoints return validated JSON. No live provider requests have been sent in this session.
3. Multi-tab collaboration verification: run the 10-test plan below in two browser tabs with two Firebase accounts. Presence, cursors, document updates, revision conflicts, version broadcast/restore, suggestion accept, sharing/ACL, AI cancellation, sidebar/responsive, metrics.
4. Academic evaluation: instruments and scripts are ready; no participant data collected. Do not fabricate results.
5. Optional: multi-process pub/sub for the in-memory `ConnectionManager` (currently single-process only).
1. Completed test isolation and export safety. Modified `backend/tests/{conftest,test_auth,test_analytics}.py`, `backend/app/utils/content.py`, `backend/app/api/routers/analytics.py`. Reproduced 11 export failures first; all now pass. Backend 49 tests passing.
2. Completed revision/autosave unit: `DocumentUpdate.base_revision` now required; response contains revision, updated_by, owner_id. Firestore transaction checks owner and expected revision; derives wordCount server-side. JSON content limited to 750 KB, 20,000 nodes, depth 64. Existing records load at revision 0 without migration. All sync SDK routes/dependency now run in FastAPI threadpool.
3. Frontend adds per-editor `core/services/document-autosave.service.ts` with unit tests; serializes/coalesces saves and blocks retry on 409. Editor queues changes immediately, warns before leaving, offers draft JSON download and confirmed reload, disables snapshot while unsaved. No persistent browser draft storage or automatic merge; refresh/crash recovery beyond leave warning not implemented.
4. Earlier revision/autosave checkpoint: backend 60 tests passed, frontend 8 tests passed, production build passed. Transaction tests exercise callback logic with doubles; no claim of live emulator concurrency verification.
5. Completed AI/auth boundary reliability: `Accept: application/x-ndjson` negotiates delta/done/error generation frames. Frontend requires done, rejects partial failure, captures the original document/selection, inserts AI output as text, cancels obsolete calls. Provider readers detect missing termination/errors and ignore reasoning chunks. Auth interceptor checks URL origin/path boundaries. SDK initialization now guarded by RLock for concurrent threadpool requests.
6. Installed versions verified: Node 24.15, Angular 22.1.1, TipTap 3.29.2, TypeScript 6.0.3, Vitest 4.1.10. Earlier 52-byte editor stylesheet warning resolved by extracting history styles; no budget increase.
7. Backend restore completed; 80 backend tests passing. New POST `/documents/{id}/versions/{version_id}/restore` requires `base_revision`. Transaction validates owner, revision, version linkage/content; preserves current snapshot (`before_restore`), updates document revision, writes resulting snapshot (`restore`) with actor, author name, source revision and restored version ID. Existing versions default to manual source and owner actor. No real records restored/deleted during tests.
8. Completed history UI extraction to `frontend/src/app/documents/version-history/`. Supports choosing a comparison target, current-vs-snapshot or two-snapshot diff, actor/source/revision metadata, restore and delete confirmations, busy/empty/error/unsaved states. Restore locks title, editor, formatting and AI requests; pending changes/cancel/conflict leave content intact. Do not replace component-injected MatDialog with a root-only spy in editor tests; standalone Material imports use a distinct injector.
9. Completed bounded automatic checkpoints: `DocumentRepository.update()` now detects no-op saves (unchanged title+content) and returns without advancing revision or writing history. On a changed save, when `_checkpoint_due(lastCheckpointAt, now)` is true (None, >=5 min elapsed, or clock moved backwards), it writes an `autosave` version capturing the pre-edit document via `transaction.set` BEFORE `transaction.update`, then sets `lastCheckpointAt`. A `set` failure propagates before `update`, so no orphaned history. `VersionRepository.restore()` now resets `lastCheckpointAt` to the restore time. `VersionCreate` accepts optional `base_revision` (ge=0, strict int); the create-version route returns 409 when it does not match the current document revision. `autosave` added to `VersionModel`/`VersionSummary` source literals and the frontend `VersionSummary` type + `sourceLabels`. New backend tests: first-changed-save checkpoint, 5-minute interval boundaries (0/299/300/600s), frequent saves produce one checkpoint, no-op save produces none, checkpoint failure prevents update, stale save produces none, clock-moving-backwards does not disable checkpoints, manual snapshot stale-revision rejection, manual snapshot revision capture, invalid base_revision validation. New frontend test: autosave source label renders distinctly.
10. Latest verified checkpoint (automatic checkpoints): backend **97 tests passed**, frontend **34 tests passed**, production build passed without budget warning. `git diff --check` clean.
11. Completed AI prompt/action service: `app/services/ai_actions.py` centralizes system prompts and prompt assembly for 11 actions (rewrite, improve, expand, condense, summarize, grammar, tone, continue, outline, custom, generate). Each action has a `ActionSpec` (system prompt, needs_text flag, label). `build_prompt()` validates input sizes, tone values, and assembles context (document title, before/after selection text trimmed to 4000 chars). New endpoints: `GET /ai/actions` (discovery), `POST /ai/action` (unified). Legacy `/ai/rewrite`, `/ai/summarize`, `/ai/generate` preserved and now delegate to the action service. Frontend `AiService.action()` + `listActions()` added; `AiActionRequest`/`AiActionInfo` models added. Editor `runAi()` refactored to use `/ai/action` with surrounding context (before/after paragraphs, document title) for all non-generate modes. New AI panel modes: Grammar, Tone (with tone selector), Continue, Outline, Custom. `AI_TONES` exported from the model. Editor tests updated to mock `aiService.action`.
12. Completed persistent AI suggestions: `app/models/suggestion.py` (`SuggestionModel` with type/status/document_revision/resolved_by), `app/schemas/suggestion.py` (`SuggestionCreate`/`SuggestionUpdate`/`SuggestionOut`), `app/repositories/suggestion_repository.py` (create/get/list_by_document/update_status/delete). Accept requires `base_revision` and checks the current document revision — stale suggestions return 409. Rejecting does not require it. Already-resolved suggestions return 409. Ownership enforced on every operation. New router `app/api/routers/suggestions.py`: `POST/GET /documents/{id}/suggestions`, `PATCH/DELETE /documents/{id}/suggestions/{suggestion_id}`. Frontend `SuggestionService` + `Suggestion` model added with unit tests. Backend does NOT auto-apply suggested text to the document.
13. Latest verified checkpoint: backend **127 tests passed**, frontend **39 tests passed**, production build passed without budget warning. `git diff --check` clean. No live emulator concurrency, browser screenshot review, multi-user testing or academic measurements performed.
14. Completed suggestion list UI: extracted `frontend/src/app/documents/suggestion-list/` component with pending/accepted/rejected/all filter chips, counts, type labels, original/suggested/reason display, accept/reject/delete actions, unsaved-notice blocking accept, empty state, error/reload. Editor side panel gains a "Suggestions" tab; `loadSuggestions()` loads on tab open, `acceptSuggestion()` sends `base_revision` (stale → 409 error message), `rejectSuggestion()` doesn't require revision, `deleteSuggestion()` removes. 6 new component tests.
15. Latest verified checkpoint: backend **127 tests passed**, frontend **45 tests passed**, production build passed without budget warning. `git diff --check` clean. No live emulator concurrency, browser screenshot review, multi-user testing or academic measurements performed.
16. Exact next task: implement backend sharing/ACLs (owner/editor/viewer) with Firestore `documentCollaborators` collection, permission checks on every document/version/suggestion endpoint, and a sharing UI. Then realtime notifications/presence. Dashboard/sidebar redesign and academic evaluation remain pending. Do not add placeholder shared lists or fabricate metrics.
17. Completed backend sharing/ACLs: `app/models/collaborator.py` (`CollaboratorModel` with role: owner/editor/viewer), `app/schemas/collaborator.py` (`CollaboratorInvite` validates email + rejects owner role; `CollaboratorOut`), `app/repositories/collaborator_repository.py` (list_by_document/list_by_user/find/upsert/delete/delete_all_for_document), `app/repositories/base.py` (`collaborators_collection`), `app/services/permissions.py` (`get_document_with_role` with role-rank check; `require_owner`/`require_editor`/`require_viewer`; `list_accessible_documents` merges owned + shared). `app/api/routers/documents.py` now uses role-aware access: GET requires viewer, PATCH requires editor, DELETE requires owner (also cleans up collaborators). List endpoint includes shared documents. `app/api/routers/sharing.py`: `GET/POST /documents/{id}/collaborators`, `DELETE /documents/{id}/collaborators/{collab_id}`. Email-based invite resolves UID via users collection; rejects self-share, owner-role, unknown user, invalid email. Existing `_get_owned_document` preserved as backward-compat alias for version/suggestion routers.
18. Completed frontend sharing UI: `SharingService` + `Collaborator` model + 3 service tests. `ShareDialog` component with email+role invite form, collaborator list with remove buttons, loading/error states. Editor top bar gains a "Share" button that opens the dialog; `openShareDialog()` loads collaborators, `inviteCollaborator()`/`removeCollaborator()` call the service and update the list. Updated existing document tests to patch `app.services.permissions` instead of `app.api.routers.documents._get_owned_document`.
19. Latest verified checkpoint: backend **143 tests passed**, frontend **48 tests passed**, production build passed without budget warning. `git diff --check` clean. No live emulator concurrency, browser screenshot review, multi-user testing or academic measurements performed.
20. Exact next task: apply ACL checks to versions and suggestions routers (currently use `_get_owned_document` owner-only alias). Then realtime notifications/presence (WebSocket presence + document_updated broadcast with revision check). Dashboard/sidebar redesign and academic evaluation remain pending. Do not add placeholder shared lists or fabricate metrics.
21. Completed versions/suggestions ACLs: versions router now uses `require_viewer` (list/get/diff), `require_editor` (create/restore), `require_owner` (delete). Suggestions router uses `require_viewer` (list), `require_editor` (create/update/delete). Removed the `_get_owned_document` import from both routers. Updated existing tests to patch `require_*` functions. Added 12 new ACL tests (`test_version_suggestion_acls.py`) covering viewer-can-read/editor-can-write/stranger-denied for both routers.
22. Completed realtime presence/notifications: `app/services/connection_manager.py` (in-memory `ConnectionManager` tracking connections per document; broadcasts `presence`/`presence_list`/`document_updated`/`version_created` events). `app/api/routers/ws.py` (WebSocket `/ws/documents/{id}` with token query param auth + viewer ACL check). `update_document` and `restore_version` endpoints now `async` and broadcast `document_updated`; `create_version` broadcasts `version_created`. Frontend `DocumentWsService` connects on document load, exposes `presenceUsers`/`connected`/`lastUpdate`/`lastVersion` signals, auto-reconnects on close. Editor header shows a presence indicator (online dot + count) when collaborators are connected. 8 backend WS tests + 6 frontend service tests.
23. Latest verified checkpoint: backend **163 tests passed**, frontend **54 tests passed**, production build passed without budget warning. `git diff --check` clean. No live emulator concurrency, browser screenshot review, multi-tab testing or academic measurements performed.
24. Exact next task: dashboard/sidebar redesign (search, sort, filters, recent/shared/owned views, empty/loading/error states). Then academic evaluation documentation. Realtime cursor/selection sharing and multi-process pub/sub remain optional. Do not add placeholder shared lists or fabricate metrics.

### Most recently modified files
AI prompt/action + suggestions unit:
- Backend: `app/services/ai_actions.py` (NEW — prompt templates + assembly), `app/schemas/ai.py` (`AiActionRequest`/`AiActionInfo`), `app/api/routers/ai.py` (unified `/ai/action` + `/ai/actions`, legacy endpoints delegate to action service), `app/models/suggestion.py` (NEW), `app/schemas/suggestion.py` (NEW), `app/repositories/suggestion_repository.py` (NEW), `app/repositories/base.py` (`suggestions_collection`), `app/api/routers/suggestions.py` (NEW), `app/main.py` (register suggestions router), `tests/test_ai_actions.py` (NEW), `tests/test_suggestions.py` (NEW).
- Frontend: `src/app/core/models/ai.model.ts` (`AiAction`, `AiActionRequest`, `AiActionInfo`, `AI_TONES`), `src/app/core/services/ai.service.ts` (`action()`, `listActions()`), `src/app/core/models/suggestion.model.ts` (NEW), `src/app/core/services/suggestion.service.ts` (NEW), `src/app/core/services/suggestion.service.spec.ts` (NEW), `src/app/documents/suggestion-list/suggestion-list.{ts,html,scss,spec.ts}` (NEW — filter/accept/reject/delete UI), `src/app/documents/editor/editor.{ts,html}` (new AI modes, tone selector, context-aware `runAi`, `MatSelectModule`/`TitleCasePipe` imports, suggestions tab + signals + methods), `src/app/documents/editor/editor.spec.ts` (mock `aiService.action`).
Sharing/ACL unit:
- Backend: `app/models/collaborator.py` (NEW), `app/schemas/collaborator.py` (NEW), `app/repositories/collaborator_repository.py` (NEW), `app/repositories/base.py` (`collaborators_collection`), `app/services/permissions.py` (NEW — role-aware access), `app/api/routers/documents.py` (role-aware GET/PATCH/DELETE + shared docs in list), `app/api/routers/sharing.py` (NEW), `app/main.py` (register sharing router), `tests/test_sharing.py` (NEW — 16 tests), `tests/test_documents.py` (updated to patch permissions module), `tests/test_document_revisions.py` (updated conflict test).
- Frontend: `src/app/core/models/collaborator.model.ts` (NEW), `src/app/core/services/sharing.service.ts` (NEW), `src/app/core/services/sharing.service.spec.ts` (NEW), `src/app/documents/share-dialog/share-dialog.{ts,html}` (NEW), `src/app/documents/editor/editor.{ts,html}` (Share button + `openShareDialog`/`inviteCollaborator`/`removeCollaborator`).
Versions/suggestions ACL unit:
- Backend: `app/api/routers/versions.py` (uses `require_viewer`/`require_editor`/`require_owner`), `app/api/routers/suggestions.py` (uses `require_viewer`/`require_editor`), `tests/test_versions.py` (updated to patch `require_*`), `tests/test_suggestions.py` (updated), `tests/test_version_restore.py` (updated), `tests/test_version_suggestion_acls.py` (NEW — 12 ACL tests).
Realtime presence unit:
- Backend: `app/services/connection_manager.py` (NEW — `ConnectionManager` with presence/broadcast), `app/api/routers/ws.py` (NEW — WebSocket endpoint with token auth + viewer ACL), `app/api/routers/documents.py` (`update_document` async + broadcast), `app/api/routers/versions.py` (`create_version`/`restore_version` async + broadcast), `app/main.py` (register ws router), `tests/test_websocket.py` (NEW — 8 tests).
- Frontend: `src/app/core/services/document-ws.service.ts` (NEW), `src/app/core/services/document-ws.service.spec.ts` (NEW — 6 tests), `src/app/documents/editor/editor.{ts,html,scss}` (presence indicator + `connectPresence`/`disconnect`).
Automatic checkpoint unit:
- Backend: `app/models/document.py` (added `last_checkpoint_at`), `app/models/version.py` (`autosave` source), `app/schemas/version.py` (`autosave` source, optional `base_revision` on `VersionCreate`), `app/repositories/document_repository.py` (`CHECKPOINT_INTERVAL`, `_checkpoint_due`, `_checkpoint_payload`, no-op detection, checkpoint-before-update in transaction, `lastCheckpointAt` read/write), `app/repositories/version_repository.py` (restore resets `lastCheckpointAt`), `app/api/routers/versions.py` (stale `base_revision` → 409), `tests/test_document_revisions.py` (checkpoint tests), `tests/test_versions.py` (revision-aware manual snapshot tests).
- Frontend: `src/app/core/models/version.model.ts` (`autosave` source), `src/app/documents/version-history/version-history.ts` (`autosave` label), `src/app/documents/version-history/version-history.spec.ts` (autosave label test).
Restore/history unit:
- Backend: `app/models/version.py`, `app/schemas/version.py`, `app/repositories/version_repository.py`, `app/api/routers/versions.py`, `tests/test_version_restore.py`.
- Frontend: `src/app/core/models/version.model.ts`, `src/app/core/services/version.service.ts`, `src/app/documents/version-history/version-history.{ts,html,scss,spec.ts}`, `src/app/documents/editor/editor.{ts,html,scss,spec.ts}`.
Earlier foundation unit in this work session:
- Backend: `app/api/deps.py`, `app/api/routers/{users,documents,analytics,ai}.py`, `app/firebase/admin.py`, `app/models/document.py`, `app/schemas/{document,ai}.py`, `app/repositories/document_repository.py`, `app/services/ai_provider.py`, `app/utils/content.py`, `tests/{conftest,test_auth,test_analytics,test_documents,test_document_revisions,test_ai,test_ai_provider}.py`.
- Frontend: `src/app/core/interceptors/auth.interceptor{,.spec}.ts`, `src/app/core/models/document.model.ts`, `src/app/core/services/{document.service,document-autosave.service,document-autosave.service.spec,ai.service,ai.service.spec}.ts`, `src/app/documents/documents.routes.ts`, editor files above.
- Persistent project memory: root `AGENTS.md`.

### Manual acceptance scenarios still to run
Use approved test accounts/documents, not production data. No deletion needed.
1. Two tabs open the same document revision: save in A, then B. B must display conflict, retain its local draft, permit download, and never overwrite A automatically.
2. Save two named snapshots, compare both directions, verify added/deleted text is highlighted. With unsaved edits, restore must be disabled.
3. Restore a snapshot after confirmation; verify current document revision increases, pre-restore and restored snapshots appear with actor/time/source, and the prior document can itself be restored.
4. Simulate network failure during save/restore/generation. Local text survives save/restore errors; AI does not label partial failure complete.
5. Move cursor during AI generation (apply stays anchored); edit document during generation (apply refuses stale result); model HTML appears literally as text; undo works after acceptance.
6. Keyboard resize with arrows/Home/End, mouse/touch cancel, storage unavailable, and phone/tablet panel layout. Full visual/usability signoff is pending.
Known blockers: exposed key rotation requires user; real test-record cleanup requires explicit approval; multi-user live tests need approved test accounts/emulator. No records deleted, no deployments/migrations performed.

## AI changelog
- 2026-09-13 audit: inventoried Angular/FastAPI/Firestore architecture and gaps; baseline build/tests run; identified unsafe analytics test database access and notified user. Created this consolidated persistent project memory before major implementation.
- 2026-09-13 foundation: blocked live Firebase/provider access in tests, isolated analytics, fixed export escaping/link safety/heading validation/Unicode filenames. Added validated document revisions and atomic conflict checks, server word counts, serialized/coalesced autosave and explicit draft recovery/leave warnings. Offloaded synchronous SDK operations and made SDK initialization thread-safe.
- 2026-09-13 AI/security: added negotiated delta/done/error generation framing, completion checks/cancellation, anchored text-only AI acceptance with stale-document rejection, and exact-origin token scoping; added provider/service/editor regression coverage.
- 2026-09-13 UI: keyboard/cancel-safe resizing with safe storage/clamping and narrow-screen overlay; canvas no longer prevents flex shrinking. Visual review still pending.
- 2026-09-13 continuation: added atomic version restore with pre/post snapshots and actor/source metadata; extracted version-history UI with two-version comparison and confirmation controls; resolved stylesheet warning by decomposition. Verification: 82 backend and 33 frontend tests pass; production build passes. Remaining roadmap is not declared complete.
- 2026-09-14 automatic checkpoints: implemented bounded automatic version checkpoints inside the document update transaction (first changed save preserves pre-edit state, then at most once per 5 minutes; no-op saves skipped; checkpoint `set` before `update` so failures cannot orphan history; restore resets timer). Made manual snapshot creation revision-aware via optional `base_revision` (409 on stale). Added `autosave` source to backend/frontend version types and history UI. Verification: 97 backend and 34 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 AI actions + suggestions: extracted bounded-context `ai_actions` prompt service (11 actions with centralized system prompts, context-aware prompt assembly with before/after/title, input validation). Added unified `POST /ai/action` + `GET /ai/actions` endpoints; legacy `/ai/rewrite`/`/ai/summarize`/`/ai/generate` preserved and delegate to the service. Frontend editor gains Grammar, Tone (with selector), Continue, Outline, Custom modes; `runAi()` sends surrounding context. Implemented persistent AI suggestions (Firestore `suggestions` collection) with create/list/accept/reject/delete; accepting requires `base_revision` and rejects stale documents (409); backend never auto-applies suggested text. Verification: 127 backend and 39 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 suggestion list UI: extracted `suggestion-list` component (pending/accepted/rejected/all filter chips, counts, type labels, original/suggested/reason display, accept/reject/delete, unsaved-notice, empty/error states). Editor side panel gains a "Suggestions" tab; accept sends `base_revision` (stale → 409), reject doesn't require revision. 6 new component tests. Verification: 127 backend and 45 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 sharing/ACLs: implemented role-based access control (owner/editor/viewer) with Firestore `documentCollaborators` collection. `permissions.py` service provides `require_owner`/`require_editor`/`require_viewer` with role-rank checks; `list_accessible_documents` merges owned + shared. Documents router now enforces roles on GET/PATCH/DELETE; list includes shared docs. New sharing router: list/invite/remove collaborators; email-based invite resolves UID via users collection, rejects self-share/owner-role/unknown-user/invalid-email. Frontend `SharingService` + `ShareDialog` with invite form and collaborator list. 16 backend + 3 frontend service tests. Verification: 143 backend and 48 frontend tests pass; production build passes; `git diff --check` clean. Versions/suggestions routers still use the owner-only `_get_owned_document` alias — applying role-aware checks there is the next task.
- 2026-09-14 versions/suggestions ACLs: versions router now uses `require_viewer` (list/get/diff), `require_editor` (create/restore), `require_owner` (delete). Suggestions router uses `require_viewer` (list), `require_editor` (create/update/delete). Removed `_get_owned_document` import from both. Updated existing tests to patch `require_*`. Added 12 new ACL tests. Verification: 155 backend tests pass.
- 2026-09-14 realtime presence: `ConnectionManager` (in-memory, single-process) tracks WebSocket connections per document and broadcasts `presence`/`presence_list`/`document_updated`/`version_created`. WebSocket `/ws/documents/{id}` authenticates via token query param and checks viewer ACL. `update_document`/`create_version`/`restore_version` endpoints now async and broadcast. Frontend `DocumentWsService` connects on document load, auto-reconnects, exposes presence/update signals. Editor header shows presence indicator. 8 backend + 6 frontend tests. Verification: 163 backend and 54 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 dashboard redesign: added search (signal-reactive via `toSignal`), All/Owned/Shared filter tabs with counts, sort by Updated/Title/Words with toggle direction, shared-document badges and icons, "no matching documents" empty state with clear-filters action, delete-button hidden on shared docs. Added `owner_id` to backend `DocumentSummary` schema and frontend model. 9 new dashboard tests. Verification: 163 backend and 63 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 sidebar + evaluation instrumentation: `AppShell` layout component wraps authenticated routes with a collapsible sidebar (brand, dashboard nav, new-doc, account menu with logout). Sidebar state persists in `localStorage`. Dashboard header simplified (brand/account moved to sidebar). Routes restructured: auth routes outside shell, dashboard/documents inside. Backend `MetricsMiddleware` records per-request latency (normalized endpoint, method, status code); `MetricsCollector` service provides p50/p95 per endpoint, recent records, and reset. `GET /metrics/summary`, `GET /metrics/recent`, `POST /metrics/reset` endpoints (auth-required). Metrics endpoint excluded from its own recording. Frontend `MetricsCollector` service: opt-in keystroke/AI-action/suggestion/version/document/share/export counters, session duration, `exportJson()`/`downloadJson()`/`reset()`. 5 app-shell + 11 backend metrics + 12 frontend metrics tests. Verification: 174 backend and 80 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 metrics wiring + UI: Wired `MetricsCollector` into the editor (`onUpdate` keystroke counting, `runAi` action recording, `acceptSuggestion`/`rejectSuggestion` hooks, `createVersion`/`restoreVersion` hooks, `exportDocument` hook, `loadDocument` opened hook, `inviteCollaborator` share hook). Wired into dashboard (`createDocument` created hook). Added metrics toggle/export methods to `AppShell` and `Dashboard`. Sidebar gains an "Evaluation metrics" section with a toggle (radio button icon, "Recording"/"Disabled" state) and an "Export data" button (visible when enabled). 2 new app-shell metrics tests. Verification: 174 backend and 82 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 evaluation scripts: Created `backend/scripts/eval/` with 4 scripts + README + 2 template data files. `load_test.py` (Locust config testing 6 endpoints: list/get/save/versions/diff/AI action; cross-references `/metrics/summary`). `quality_analysis.py` (readability via textstat + grammar via language_tool_python; computes deltas and % change; supports single pairs or batch). `sus_scoring.py` (SUS 10-item questionnaire scoring with positive/negative item adjustment; aggregate stats with mean/median/std/min/max; warns if n < 15). `productivity_analysis.py` (paired t-test for WPM and perceived productivity; Cohen's d; handles zero-variance edge case; uses scipy if available, normal approximation otherwise). All scripts verified with template data. Prerequisites documented in README (locust, textstat, language-tool-python, scipy). No dependencies installed without approval. Verification: 174 backend and 82 frontend tests pass; all 4 scripts pass syntax validation and run correctly with template data; `git diff --check` clean.
- 2026-09-14 cursor/selection sharing: Backend `ConnectionManager.broadcast_cursor()` sends cursor updates to all other connected users (excludes sender). WS router now parses incoming `{"type":"cursor","from":N,"to":N,"empty":bool}` messages and broadcasts. Frontend `DocumentWsService` exposes `remoteCursors` signal (Record<uid, RemoteCursor>) and `sendCursor()` method; auto-removes cursors for users no longer present. `RemoteCursors` TipTap extension renders remote cursors as ProseMirror widget decorations (caret + name label) and selections as inline decorations with per-user colors. Editor `onSelectionUpdate` broadcasts local cursor via WS; effect syncs `remoteCursors` signal to the extension. 2 backend + 5 frontend WS service tests. Verification: 176 backend and 87 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 responsive polish + multi-tab test plan: Sidebar gains mobile overlay with floating menu button and backdrop (visible < 768px). Dashboard responsive: single-column grid, smaller padding, full-width search, 2-column analytics on tablet. Editor: touch-friendly 40px toolbar buttons on mobile, tighter padding at 480px. Mobile menu toggle/close methods on AppShell. 1 new app-shell mobile test. Multi-tab verification test plan documented in AGENTS.md (10 tests covering presence, cursors, document updates, revision conflicts, version broadcast/restore, suggestion accept, sharing/ACL, AI cancellation, sidebar/responsive, metrics). Verification: 176 backend and 88 frontend tests pass; production build passes; `git diff --check` clean.
- 2026-09-14 editor redesign (page-first + AI cleanup): Replaced the dashboard-card editor with a word-processor workspace: subtle gray canvas, centered white A4-like page (≈794–850px wide, ≥1120px min height, ~80–90px margins), very subtle shadow, near-square corners. The document page is the visual hero; AI/suggestions/history/stats live in a lighter 320–360px inspector that defaults to AI and can collapse so the page reclaims the space. Compact title/save row replaces the cluster of large pill buttons; formatting toolbar sits above the workspace with grouped controls and tooltips. AI output is preview-only in the inspector until the user explicitly chooses Insert at cursor / Insert below / Replace selection / Copy / Regenerate / Discard; the original selection is pinned and a stale-document check refuses to apply output if the doc changed during generation. Title suggestions return 3–5 clean options via validated JSON and update only the document title (autosaved), never the body. Backend `ai_actions.clean_writing()` strips echoed context labels (`Document title:`, `Text before selection:`, `Text:`, `Selected text:`, `Context:`, `Previous text:`, `Following text:`) from provider output; the streaming `/ai/generate` endpoint now buffers the stream and cleans the joined text before emitting a single delta (with a 50k-char safety cap), so partial/labelled chunks can no longer reach the editor. Suggestion acceptance now replaces the matched passage in the editor via a ProseMirror transaction and persists through autosave; backend accept runs in a single Firestore transaction with a unique-passage match and revision guard. Version history uses a compact timeline with friendly author names (display name → email → "You"), source labels (Manual snapshot / Automatic checkpoint / Before restore / Restored), and per-version compare/restore actions inside the selected row instead of repeated giant buttons. Suggestion list has an explanatory empty state and cleaner accept/dismiss actions. Mobile: side panel becomes a full-width overlay, page margins tighten, toolbar buttons stay touch-friendly. Verification: 202 backend tests pass, 88 frontend tests pass, production build passes with no warnings and no stylesheet budget increase; `git diff --check` clean. NOT claimed: live browser usability, live AI provider responses, multi-tab collaboration, or academic evaluation — these remain pending manual verification.

## Academic evaluation plan
This section documents the evaluation framework for the dissertation. No live measurements have been performed yet; this is the plan and instrument set. Do not fabricate results.

### Evaluation dimensions
1. **Usability** — System Usability Scale (SUS) questionnaire (10 items, 5-point Likert) administered after a scripted task set. Target: SUS ≥ 68 (above average). Tasks: register, create a document, write 200+ words, use 3 AI actions, accept/reject a suggestion, save a named version, restore a version, share with a collaborator, view shared document.
2. **Performance** — Backend endpoint latency under load (p50/p95) for: document list, document get, document save, AI action (non-stream), version list, version diff. Frontend Time-to-Interactive (TTI) for dashboard and editor. Tool: `locust` or `k6` for backend; Lighthouse for frontend. Target: p95 < 500ms for read endpoints, < 1500ms for AI actions.
3. **Editing effort** — Keystroke count and time-to-completion for a standardized writing task (rewrite a 500-word passage) with and without AI assistance. Measure via editor instrumentation (keystroke counter already feasible in TipTap; add a toggleable metrics collector). Target: ≥ 20% reduction in keystrokes with AI assistance.
4. **Document-quality improvement** — Compare pre-AI and post-AI versions using: (a) word count delta, (b) readability score (Flesch-Kincaid via `textstat`), (c) grammar error count (via `language_tool_python`). Run on 10 sample documents before/after AI actions. Target: readability improvement ≥ 10%, grammar errors reduced ≥ 30%.
5. **Productivity** — Words produced per minute (WPM) in a 10-minute free-writing session with vs. without AI suggestions available. Self-reported perceived productivity (7-point scale). Target: WPM increase ≥ 15% with AI.

### Instrumentation requirements
- Backend: `MetricsMiddleware` + `MetricsCollector` (in `app/services/metrics_collector.py`) record per-request latency (normalized endpoint, method, status code, timestamp). `GET /metrics/summary` returns p50/p95 per endpoint; `GET /metrics/recent` returns recent records; `POST /metrics/reset` clears. No document content or user-identifiable data recorded. 11 tests in `test_metrics.py`.
- Frontend: `MetricsCollector` service (in `src/app/core/services/metrics-collector.service.ts`) is opt-in (disabled by default). Counts keystrokes, AI actions by type, suggestion accept/reject, version save/restore, document create/open, share invites, exports, session duration. `exportJson()` returns JSON string; `downloadJson()` triggers a browser download; `reset()` clears counters. 12 tests in `metrics-collector.service.spec.ts`.
- Evaluation scripts: `backend/scripts/eval/` for load-test configs and quality-analysis scripts. Do not create until measurements are approved.

### Statistical analysis
- Paired t-test for within-subject comparisons (with/without AI). Wilcoxon signed-rank if normality fails (n < 30).
- Report effect size (Cohen's d). Significance threshold α = 0.05.
- Minimum sample size: n = 15 participants for usability; n = 30 documents for quality analysis.

### Current status
- Backend metrics collection and `/metrics` endpoints are implemented and tested.
- Frontend `MetricsCollector` service is implemented, tested, and wired into the editor and dashboard.
- Sidebar has a metrics toggle/export UI.
- Evaluation scripts are created in `backend/scripts/eval/`: `load_test.py` (Locust), `quality_analysis.py` (readability + grammar), `sus_scoring.py` (SUS questionnaire), `productivity_analysis.py` (WPM + perceived productivity). All verified with template data.
- No evaluation dependencies (locust, textstat, language-tool-python, scipy) have been installed yet.
- No participant data has been collected.
- The plan and instruments above are ready to execute when the user approves live evaluation.
- Do not claim any evaluation results without actual measurements.

## Multi-tab verification test plan
This is a scripted manual test plan for verifying realtime collaboration features in a browser with two tabs. It has NOT been executed yet. Run it when the backend and frontend are both running locally.

### Prerequisites
- Backend running: `cd backend && venv/bin/uvicorn app.main:app --reload --port 8000`
- Frontend running: `cd frontend && npm start`
- Two Firebase user accounts (User A and User B) with different emails.
- A document created by User A, shared with User B as editor.

### Test 1: Presence and cursor sharing
1. Tab 1: Log in as User A, open the shared document.
2. Tab 2: Log in as User B, open the same document.
3. **Expected**: Tab 1 shows User B in the presence indicator (green dot + count). Tab 2 shows User A.
4. Tab 1: Place cursor in the middle of the text.
5. **Expected**: Tab 2 shows User A's cursor as a colored caret with a name label.
6. Tab 2: Select a range of text.
7. **Expected**: Tab 1 shows User B's selection as a semi-transparent highlight.

### Test 2: Realtime document update
1. Tab 1: Type and autosave (wait for the "Saved" indicator).
2. **Expected**: Tab 2 receives a `document_updated` event and the content refreshes (or shows an update notification).
3. Tab 2: Type and save.
4. **Expected**: Tab 1 receives the update.

### Test 3: Revision conflict
1. Tab 1 and Tab 2: Both start editing (make unsaved changes).
2. Tab 1: Save first (wait for autosave).
3. Tab 2: Save second.
4. **Expected**: Tab 2 gets a 409 conflict. The editor keeps the local draft and offers retry or recovery. Tab 2 does NOT silently overwrite Tab 1's changes.

### Test 4: Version creation broadcast
1. Tab 1: Save a named version ("v1").
2. **Expected**: Tab 2 receives a `version_created` event. The version history panel refreshes when opened.

### Test 5: Version restore
1. Tab 1: Restore an earlier version.
2. **Expected**: Tab 1 shows the restored content. A pre-restore snapshot is saved to history.
3. Tab 2: Reload the document.
4. **Expected**: Tab 2 sees the restored content.

### Test 6: Suggestion accept
1. Tab 1: Create a suggestion (via AI action).
2. Tab 2: Open the suggestions panel, accept the suggestion.
3. **Expected**: The suggestion status changes to "accepted" in both tabs (after refresh or via WS event).
4. Tab 1: Try to accept the same suggestion.
5. **Expected**: 409 — suggestion already resolved.

### Test 7: Sharing and ACL
1. Tab 1 (owner): Invite a viewer via the Share dialog.
2. Tab 3: Log in as the viewer, open the document.
3. **Expected**: Viewer can read but cannot edit (save returns 403). Editor toolbar may be read-only or disabled.
4. Tab 1: Remove the viewer from collaborators.
5. **Expected**: Tab 3 loses access on next API call (403 or 404).

### Test 8: AI action cancellation
1. Tab 1: Start a long AI generation (e.g. "generate 500 words about...").
2. While streaming, click "Stop".
3. **Expected**: The stream stops. No partial result is applied as a "success". The editor keeps its previous content.
4. Start another AI action, then immediately navigate away and back.
5. **Expected**: The orphaned stream does not overwrite the document.

### Test 9: Sidebar and responsive
1. Tab 1: Collapse the sidebar (chevron button). **Expected**: Sidebar shrinks to 64px, labels hidden.
2. Expand it again. **Expected**: Sidebar returns to 240px.
3. Resize the browser to < 768px width. **Expected**: Sidebar becomes an overlay. A floating menu button appears. Tapping it opens the sidebar with a backdrop.
4. Tap the backdrop. **Expected**: Sidebar closes.

### Test 10: Metrics collection
1. Tab 1: Enable metrics via the sidebar toggle.
2. Write some text, run an AI action, accept a suggestion, save a version.
3. Click "Export data". **Expected**: A JSON file downloads with keystroke, AI action, suggestion, and version counts.
4. Disable metrics. **Expected**: Further actions are not counted.
