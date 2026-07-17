# Frontend Guide

Use this pattern for an authenticated internal React tool that talks to a separate backend API.

## Use This Stack

- Vite
- React
- TypeScript
- React Router
- Supabase JS
- Tailwind CSS
- shadcn component patterns
- Radix UI primitives
- lucide-react icons
- ESLint
- pnpm

## Folder Shape

```text
frontend/
├── src/
│   ├── components/
│   │   ├── chat/
│   │   └── ui/
│   ├── lib/
│   │   ├── api.ts
│   │   ├── env.ts
│   │   ├── http.ts
│   │   └── supabase.ts
│   ├── pages/
│   └── main.tsx
├── components.json
├── package.json
├── pnpm-lock.yaml
└── vite.config.ts
```

## Rules To Reuse

- Keep browser env vars `VITE_` only.
- Validate env vars at app startup in `src/lib/env.ts`.
- Put Supabase browser client in one shared module.
- Put authenticated backend fetch logic in one shared wrapper.
- Keep service-role/database/OpenAI secrets out of the frontend.
- Use reusable chat primitives: message, composer, citation chip, source panel, status timeline.
- Prefer clear internal-tool UI over marketing-page styling.
- Use icons for common actions and tooltips for icon-only controls.

## Production Reminders

- Vite preview must bind to `0.0.0.0` and `$PORT` on Railway.
- Vite preview may need `preview.allowedHosts` for the Railway domain.
- Run `pnpm build` before deployment changes.
- Check the live app with a normal `GET`, not only `HEAD`, because preview servers can treat methods differently.

