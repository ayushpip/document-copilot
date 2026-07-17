# Future Project Structure

This is a cleaner reusable version of `docs/todo.md`: use it as the starting order for future projects.

## 1. Define The Product Contract

- [ ] Write a client brief with target user, pain, success criteria, and example questions.
- [ ] Define what the app must refuse to answer.
- [ ] Define what counts as enough evidence.
- [ ] Decide whether answers need citations, calculations, or both.
- [ ] List the exact corpus scope.

## 2. Set Up Project Foundations

- [ ] Create GitHub repo.
- [ ] Add root README.
- [ ] Add `.gitignore` for env files, venvs, node modules, downloads, logs, and build artifacts.
- [ ] Add docs folder.
- [ ] Add architecture doc.
- [ ] Add implementation checklist.
- [ ] Decide backend/frontend/data folder layout.

## 3. Create External Services

- [ ] Create Supabase project.
- [ ] Collect Supabase URL, anon key, service-role key, direct database URL.
- [ ] Create OpenAI project/API key.
- [ ] Create Railway project/services if deploying early.
- [ ] Store secrets only in local `.env` and deployment variables.

## 4. Build Backend Skeleton

- [ ] Add FastAPI app.
- [ ] Add config/settings validation.
- [ ] Add `/health`.
- [ ] Add CORS settings.
- [ ] Add test framework.
- [ ] Add linting.

## 5. Build Database Schema

- [ ] Add SQLAlchemy models.
- [ ] Add Alembic.
- [ ] Add initial migration.
- [ ] Enable needed extensions such as `vector`.
- [ ] Add indexes and RLS policies.
- [ ] Run migrations against Supabase.

## 6. Add Auth

- [ ] Configure Supabase email auth.
- [ ] Add frontend Supabase client.
- [ ] Add backend bearer-token verification.
- [ ] Add protected routes.
- [ ] Confirm unauthenticated API requests fail before costly work.

## 7. Build Minimal Chat

- [ ] Thread list/create/load.
- [ ] Message persistence.
- [ ] Stub streaming endpoint.
- [ ] Frontend chat shell.
- [ ] Reload and confirm history persists.
- [ ] Confirm users cannot access each other's threads.

## 8. Build Ingestion

- [ ] Download or collect source files.
- [ ] Preserve source metadata.
- [ ] Convert files to a stable intermediate format.
- [ ] Insert source documents.
- [ ] Chunk documents.
- [ ] Generate embeddings.
- [ ] Store chunks, embeddings, and search vectors.
- [ ] Make ingest idempotent.
- [ ] Add dry-run and limited-scope options.

## 9. Build Retrieval

- [ ] Add vector search.
- [ ] Add full-text search.
- [ ] Add filters for corpus metadata.
- [ ] Fuse rankings.
- [ ] Return citations and source metadata.
- [ ] Add unit tests for retrieval query assembly.
- [ ] Add real-corpus smoke tests.

## 10. Add LLM And Grounding

- [ ] Add system instructions.
- [ ] Add typed agent boundary.
- [ ] Add evidence/citation output schema.
- [ ] Retrieve before generation.
- [ ] Validate citations.
- [ ] Validate numeric claims where needed.
- [ ] Return "not enough evidence" for unsupported questions.
- [ ] Test hard examples.

## 11. Build Trust UI

- [ ] Citation chips.
- [ ] Source passage panel.
- [ ] Loading/status timeline.
- [ ] Clear error states.
- [ ] Empty states.
- [ ] Keyboard and accessibility checks.

## 12. Deployment

- [ ] Add deployment config files.
- [ ] Set production env vars.
- [ ] Deploy backend.
- [ ] Deploy frontend.
- [ ] Verify backend health URL.
- [ ] Verify frontend loads.
- [ ] Add Supabase Auth redirect URLs.
- [ ] Enable cost controls.

## 13. Production Smoke Test

- [ ] Sign in.
- [ ] Create chat.
- [ ] Ask one simple supported question.
- [ ] Check citations.
- [ ] Refresh and confirm history.
- [ ] Ask an out-of-corpus question.
- [ ] Confirm no crash and no unrelated evidence.

## 14. Future Improvements

- [ ] Record failed questions.
- [ ] Record retrieval/evidence errors separately from deployment errors.
- [ ] Add regression tests for every bad answer.
- [ ] Improve extraction before increasing model complexity.
- [ ] Re-run client brief questions after each retrieval change.

