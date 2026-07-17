# Prompting Guide For Future Projects

This is based on how the Document Copilot build went. Your prompts were useful because you gave real context, terminal output, examples of bad answers, and clear priorities. The main improvement is to separate urgent action from broad investigation so the agent can avoid mixing tasks.

## What Worked Well

- You pasted exact terminal errors.
- You gave actual model outputs, not just "it is wrong."
- You named the desired behavior: "not enough evidence" for unsupported questions.
- You asked for staging/committing, which made progress recoverable.
- You asked for checklists, which made the project easier to manage.
- You pushed back when a doc section was removed incorrectly.
- You cared about cost before running lots of tests.

## What To Do More Often

Use this structure:

```text
Goal:
What I want done:
What not to change:
Context:
Evidence / error:
How to verify:
Commit/push instructions:
Cost limits:
```

Example:

```text
Goal: Fix out-of-corpus questions.
What I want done: If the user asks about a company not in AAPL, AMZN, GOOGL, MSFT, NVDA, return not enough evidence before retrieval/generation.
What not to change: Do not refactor the whole chat orchestrator.
Context: Tesla robotaxi question returned unrelated NVDA/MSFT evidence.
Evidence: paste the bad answer.
How to verify: Add tests and ask a Tesla question locally.
Commit: stage and commit when tests pass.
Cost limits: Do not call OpenAI unless needed; prefer unit tests first.
```

## Good Prompt Patterns

### Review Only

```text
Review only. Do not edit files yet.
Find why [specific behavior] is happening.
Prioritize bugs, risks, and missing tests.
Use file/line references.
```

### Fix Narrowly

```text
Make the smallest safe fix for [specific bug].
Do not change unrelated UI/docs.
Run relevant tests.
Stage and commit only the files you changed.
```

### Deployment Work

```text
Continue deployment from current state.
First inspect status/logs.
Do not redeploy until you know the cause.
Tick the checklist only for verified items.
Tell me anything that requires dashboard-only action.
```

### Cost-Sensitive Work

```text
Cost-sensitive: do not run OpenAI calls.
Use unit tests, database counts, logs, or dry-runs.
Ask before anything that could trigger paid usage.
```

### Documentation Work

```text
Create docs from the actual repo state.
Inspect package files and existing docs first.
Do not invent dependencies.
Keep setup steps separate from architecture notes.
Stage and commit docs only.
```

## Things To Avoid

- Combining "review only" and "go fix it" in one message.
- Saying "all changes" when there are unrelated local edits unless you truly want all of them committed.
- Asking for deployment and product-quality evaluation in the same step if cost matters.
- Asking broad questions like "is it good?" without pasting the answer or expected behavior.

## Strong Verification Prompts

Use these when validating a grounded document app:

```text
Check this answer for correctness and grounding. Tell me:
1. whether it answers the exact question,
2. whether evidence matches the requested company/topic/year,
3. whether numeric units are correct,
4. whether it should have said not enough evidence.
```

```text
Run only read-only checks:
- database corpus counts,
- migration version,
- index presence,
- expected company/year coverage.
Do not call OpenAI.
```

## Best Habit

When something fails, paste:

- the exact question;
- the full answer;
- the expected answer;
- any terminal logs;
- whether spending OpenAI tokens is allowed.

That gives the agent enough context to fix the actual bug instead of guessing.

