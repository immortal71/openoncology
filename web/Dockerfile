# ── deps ──────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app

# The lockfile, and `npm ci` rather than `npm install`. This stage used to copy
# package.json alone and run `npm install`, which re-resolved every `^` range at
# build time: the image could not be reproduced, and it was free to contain
# versions no test in this repository had ever run against. `npm ci` fails
# outright when the lockfile and the manifest disagree, which is the behaviour
# wanted in an image build.
COPY package.json package-lock.json ./
RUN npm ci

# ── dev ───────────────────────────────────────────────────────────────────────
# What docker-compose builds. It bind-mounts the source over /app and runs
# `next dev`, so it needs the full node_modules and nothing else; the anonymous
# volume on /app/node_modules is populated from this stage. Targeting `builder`
# instead would make every `docker-compose up --build` run a full production
# build first, and targeting `runner` would shadow a tree that has no `next`
# CLI in it at all.
FROM node:20-alpine AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
ENV NEXT_TELEMETRY_DISABLED=1
CMD ["npm", "run", "dev"]

# ── builder ───────────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# No NEXT_PUBLIC_* build args, deliberately. They are compile-time
# substitutions, so accepting them here would produce an image valid only for
# the hostnames it was built for, and the same commit would need rebuilding to
# be promoted from staging to production. The values are served at request time
# instead — see lib/runtime-config.ts and app/env.js/route.ts.
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── runner ────────────────────────────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# 1001, matching `runAsUser` in infra/helm/templates/web.yaml. The image ran as
# root, and the chart overrode that with a uid the image had never heard of, so
# every path the app wrote to was owned by someone else. Alpine's node:20 image
# already uses 1000 for `node`, hence a second user rather than reusing it.
RUN addgroup -g 1001 -S nextjs && adduser -u 1001 -S nextjs -G nextjs

# `output: 'standalone'` in next.config.js traces the modules the server
# actually imports and copies them into .next/standalone. What shipped before
# was the builder's entire node_modules, devDependencies included: the test
# runners, the TypeScript compiler and the Playwright driver were all in the
# production image.
COPY --from=builder --chown=1001:1001 /app/public ./public
COPY --from=builder --chown=1001:1001 /app/.next/standalone ./
COPY --from=builder --chown=1001:1001 /app/.next/static ./.next/static

USER 1001
EXPOSE 3000
ENV PORT=3000
# Not localhost. The standalone server binds HOSTNAME, and its default leaves
# the container unreachable from the kubelet's probes and from the Service.
ENV HOSTNAME=0.0.0.0

# The health endpoint the chart's probes request. Also declared here so
# `docker run` and compose see the same liveness answer Kubernetes does.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD wget -qO- http://127.0.0.1:3000/api/health || exit 1

CMD ["node", "server.js"]
