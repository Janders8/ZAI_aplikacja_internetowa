// Bazowano na:
// https://github.com/sveltejs/realworld/blob/master/src/lib/api.js
// https://stackoverflow.com/questions/38235715/fetch-reject-promise-and-catch-the-error-if-status-is-not-ok

// Wysyłanie zapytania do API backendu i zwracanie odpowiedzi
async function send(method, path, data) {
  const options = { method: method, headers: {} }

  // Dane wysyłane są jako json
  if (data) {
    options.headers['Content-Type'] = 'application/json'
    options.body = JSON.stringify(data)
  }

  // Jeśli jest to zalogowany administrator to dołącz token
  const token = sessionStorage.getItem('token')
  if (token) {
    options.headers['Authorization'] = 'Bearer ' + token
  }

  // W wypadku braku połączenia z serwerem
  let response
  try {
    response = await fetch('/api/' + path, options)
  } catch (error) {
    throw new Error('Brak połączenia z serwerem')
  }

  const text = await response.text()

  // Serwer odpowiedział ale z błędem
  if (!response.ok) {
    let message = 'Błąd serwera (' + response.status + ')'
    const contentType = response.headers.get('Content-Type')
    if (contentType === 'application/problem+json') {
      const problem = JSON.parse(text)
      message = problem.detail
    }
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  // Odpowiedź bez treści, np. po usunięciu danych z kodem 204
  if (text === '') {
    return null
  }
  return JSON.parse(text)
}


// Funkcje przekierowujące zapytania z frontendu do backendu
export function get(path) {
  return send('GET', path)
}

export function post(path, data) {
  return send('POST', path, data)
}

export function put(path, data) {
  return send('PUT', path, data)
}

export function del(path) {
  return send('DELETE', path)
}