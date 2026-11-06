// Bazowano na:
// https://vite.dev/guide/
// https://getbootstrap.com/docs/5.3/getting-started/introduction/
import { mount } from 'svelte'
// style Bootstrap do przycisków formularzy i tabel

import 'bootstrap/dist/css/bootstrap.min.css'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app