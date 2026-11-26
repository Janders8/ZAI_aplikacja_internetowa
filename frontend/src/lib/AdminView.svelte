<!-- Panel administratora z logowaniem, seriami i czujnikami -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/text-inputs
  // https://web.dev/articles/sign-in-form-best-practices
  // https://stackoverflow.com/questions/77612695/svelte-5-change-component-on-login
  // https://stackoverflow.com/questions/10281962/is-there-a-minlength-validation-attribute-in-html
  import { post, put } from './api.js'
  import SeriesAndSensors from './SeriesAndSensors.svelte'

  // Jeśli token jest już w przeglądarce (czyli użytkownik jest zalogowany) to od razu wyświetl widok dla zalogowanego
  const savedToken = sessionStorage.getItem('token')
  let loggedIn = $state(savedToken !== null)

  // Pola formularza logowania
  let username = $state('')
  let password = $state('')

  // Pola formularza zmiany hasła
  let currentPassword = $state('')
  let newPassword = $state('')

  // Komunikat o błędzie
  let message = $state('')

  // Wyświetlenie błędu z serwera, a w sytuacji wygaśnięcia tokenu (401) powrót do logowania
  function showError(error) {
    if (error.status === 401) {
      sessionStorage.removeItem('token')
      loggedIn = false
      message = error.message
    } else {
      alert(error.message)
    }
  }

  // Logowanie wraz z zapamiętaniem tokenu w przeglądarce
  async function login(event) {
    // by nie przeładować strony przy wysłaniu formularza
    event.preventDefault()
    try {
      const data = { username: username, password: password }
      const result = await post('auth/login', data)
      sessionStorage.setItem('token', result.accessToken)
      loggedIn = true
      // czyszczenie hasła i komunikatu o ewentualnym błędzie
      password = ''
      message = ''
    } catch (error) {
      message = error.message
    }
  }


  // Wylogowanie i usunięcie tokena z przeglądarki
  async function logout() {
    try {
      await post('auth/logout')
    } catch (error) {
      // pusty catch by obsłużyć błąd z backendu o ewentualnym wygasłym tokenie, nic nie trzeba z tym robić
    }
    sessionStorage.removeItem('token')
    loggedIn = false
  }


  // Zmiana hasła zalogowanego administratora
  async function changePassword(event) {
    // by nie przeładować strony przy wysłaniu formularza
    event.preventDefault()
    try {
      const data = { currentPassword: currentPassword, newPassword: newPassword }
      await put('auth/password', data)
      // czyszczenie pól i komunikatu o błędzie po zmianie
      currentPassword = ''
      newPassword = ''
      message = ''
      alert('Hasło zostało zmienione')
    } catch (error) {
      showError(error)
    }
  }


</script>

<h2>Panel administratora</h2>

<!-- widok dla zalogowanego -->
{#if loggedIn}
  <button type="button" class="btn btn-outline-primary mb-3" onclick={logout}>Wyloguj</button>

  <!-- Zarządzanie seriami i czujnikami -->
  <SeriesAndSensors showError={showError} />


  <!-- Formularz zmiany hasła -->
  <h3>Zmiana hasła</h3>
  <form class="mb-3" onsubmit={changePassword}>
    <label class="me-3">Obecne hasło <input type="password" bind:value={currentPassword} autocomplete="current-password" required /></label>
    <label class="me-3">Nowe hasło <input type="password" bind:value={newPassword} autocomplete="new-password" minlength="8" required /></label>
    <button type="submit" class="btn btn-primary">Zmień hasło</button>
  </form>
{:else}
  <!-- Formularz do logowania -->
  <form class="mb-3" onsubmit={login}>
    <label class="me-3">Login <input bind:value={username} autocomplete="username" required /></label>
    <label class="me-3">Hasło <input type="password" bind:value={password} autocomplete="current-password" required /></label>
    <button type="submit" class="btn btn-primary">Zaloguj</button>
  </form>
{/if}

<!-- Komunikat o błędzie -->
{#if message !== ''}
  <p class="text-danger" role="alert">{message}</p>
{/if}