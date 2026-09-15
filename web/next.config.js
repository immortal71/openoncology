/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Copies the server and the minimal node_modules it actually imports into
  // .next/standalone, so the runtime image carries neither the build toolchain
  // nor devDependencies. See web/Dockerfile.
  output: 'standalone',

  // There was an `env` block here mapping NEXT_PUBLIC_API_URL and
  // NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY through `process.env.X || '<default>'`.
  //
  // `env` is a compile-time substitution: every literal read of those names,
  // server and client alike, was replaced with whatever the build machine held.
  // Inside `docker build` it held nothing, so the published image had
  // 'http://localhost:8000' compiled in as the API address for every visitor,
  // and the ConfigMap that sets the real hostname could not reach it.
  //
  // Public settings are resolved at request time now — lib/runtime-config.ts
  // has the mechanism and the reasoning. Reinstating a block here would put the
  // build-time value back in front of it.

  images: {
    remotePatterns: [],
  },
};

module.exports = nextConfig;
