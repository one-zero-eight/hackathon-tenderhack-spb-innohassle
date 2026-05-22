# ⚛️ React + TypeScript Front-End Template

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

A clean, modular template for modern front-end development using React, Vite, TypeScript, Tailwind, and TanStack tools. Designed for scalability, feature-based organization, and strong API typing via OpenAPI.

## 🚀 Tech Stack

- **Core**: [Node.js](https://nodejs.org/en), [TypeScript](https://www.typescriptlang.org)
- **Framework**: [React](https://react.dev), [Vite](https://vite.dev)
- **Styling**: [Tailwind CSS](https://tailwindcss.com), [Headless UI](https://headlessui.com)
- **Routing & State**: [Tanstack Router](https://tanstack.com/router/latest) (file-based routing), [Tanstack Query](https://tanstack.com/query/latest) (server state management)
- **API**: [openapi-ts](https://openapi-ts.dev) (OpenAPI-generated client)

## 📁 Project Structure

```graph
/src
├── app/                               # App-wide config, providers, router
│   ├── router/
│   │   ├── routes/                    # Route files (file-based routing)
│   │   │   ├── index.tsx              # /
│   │   │   └── route/
│   │   │       └── index.tsx          # e.g /route
│   │   └── __root.tsx                 # Router context types
│   ├── providers/                     # Global providers
│   ├── main.tsx                       # Entry point
│   └── routeTree.gen.ts               # Generated routeTree
│
├── pages/                             # Module-based domain modules
│   └── auth/
│       ├── components/
│       ├── hooks/
│       ├── pages/
│       ├── api/                       # Module-specific API wrappers
│       └── index.ts
│
├── api/                               # Auto-generated OpenAPI client
│   ├── schemas.ts                     # Generated Zod/TS schemas (if using zod)
│   ├── client.ts                      # API client instance (fetch/axios)
│   ├── endpoints.ts                   # Wrapped endpoint functions
│   └── types.d.ts                     # Generated types
│
├── components/                        # Reusable UI components (global)
│   ├── ui/                            # Design system atoms/molecules
│   └── form/                          # Form components
│
├── hooks/                             # Global cross-feature hooks
├── lib/                               # Core libraries/utilities (non-React)
│   ├── http.ts                        # fetch wrapper, interceptors
│   ├── env.ts                         # environment variables handling
│   ├── storage.ts                     # localStorage/session helpers
│   └── logger.ts
│
├── styles/                            # Global styles, tokens
│   └── index.css
│
└── assets/                            # Static assets
```

## ⚒️ Development:

### 🐋 Using Docker

1. Download [Docker](https://www.docker.com)
2. Run

```bash
docker compose up
```

3. Open application at [http://localhost:8080](http://localhost:8080)

### 🏁 Without Docker

1. Install [Node.js](https://nodejs.org/en) and [pnpm](https://pnpm.io)
2. Clone repository

```bash
git clone https://github.com/PoweredDeveloper/frontend-template.git
cd frontend-template
```

3. Install dependencies

```bash
pnpm install
# or
yarn
```

4. Start dev server

```bash
pnpm run dev --port 8080
# or
yarn dev --port 8080
```

5. Open app [http://localhost:8080](http://localhost:8080)

### OpenAPI types

With the API running (`docker compose up` publishes it on port 8000):

```bash
pnpm gen:api
```

Types are generated from `redocly.yaml` (remote URL `http://localhost:8000/openapi.json`).

> [!IMPORTANT]
> Route files are auto-generated. A system restart may be required after initial setup to ensure the router correctly refreshes its file mapping.

## TO-DO

- [ ] Custom components
  - [ ] General (button, inputs, etc.)
  - [ ] Universal (pop-ups, labels, badges)
- [ ] API
