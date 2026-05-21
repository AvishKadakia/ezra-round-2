# Artifact Hub Frontend

React + TypeScript + Vite frontend. Deploy this directory to Netlify.

## Local

```bash
npm install
cp .env.example .env
npm run dev
```

## Netlify

`netlify.toml` sets:

- `npm run build`
- publish directory `dist`
- SPA redirect fallback to `/index.html`

Set this environment variable in Netlify:

```env
VITE_API_BASE_URL=https://your-railway-backend.up.railway.app
```
