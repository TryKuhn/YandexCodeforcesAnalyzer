import { defineConfig } from 'vite'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Which portal to build. Inlined via `define` rather than read from
// import.meta.env at runtime: only a literal lets the bundler drop the other
// portal's routes, so a contestant never downloads the jury pages.
const portal = process.env.VITE_PORTAL === 'participant' ? 'participant' : 'jury'

// https://vite.dev/config/
export default defineConfig({
  define: {
      __PORTAL__: JSON.stringify(portal),
  },
  resolve: {
      alias: {
          // only the chosen portal's routes are ever imported, so the other
          // portal's pages are not in the bundle at all
          '@portal-routes': path.resolve(
              __dirname,
              portal === 'jury' ? 'src/routes/JuryRoutes.tsx' : 'src/routes/ParticipantRoutes.tsx',
          ),
      },
  },
  plugins: [
      react(),
      tailwindcss(),
  ],
  optimizeDeps: {
      include: ['react-syntax-highlighter', 'react-syntax-highlighter/dist/cjs/styles/prism'],
  },
    server: {
        host: '0.0.0.0',
        port: 5173,
        watch: {
            usePolling: true,
        },
    },
})
