// Bazowano na:
// https://vite.dev/config/server-options#server-proxy
import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [svelte()],
  // Do przekazywania zapytań do /api do serwera Flask (przy testowaniu lokalnie)
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
})