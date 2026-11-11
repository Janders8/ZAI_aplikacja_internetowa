<!-- Widok użytkownika z filtrami, wykresami oraz z tabelą wyników -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/await-blocks
  // https://svelte.dev/tutorial/svelte/group-inputs
  // https://getbootstrap.com/docs/5.3/content/tables/
  // https://date-fns.org/docs/format
  import { get } from './api.js'
  import { format, subDays } from 'date-fns'

  // Wszystkie serie do wyboru w filtrze
  let allSeries = $state([])

  // Pola filtra
  let selected = $state([])
  let from = $state('')
  let to = $state('')

   // Tabela wyników, gdzie kolumny to serie i wiersze to czas
  let shownSeries = $state([])
  let rows = $state([])

  // dane w trakcie pobierania (do informacji o pobieraniu i o błędach)
  let loading = $state(start())

  // Pierwsze otwarcie widoku ze wszystkimi zaznaczonymi domyślnie seriami
  async function start() {
    allSeries = await get('series')
    for (const series of allSeries) {
      selected.push(series.id)
    }

    // Ustawienie filtra "Od" na dobę przed najnowszym pomiarem
    const newest = await get('measurements?sort=-timestamp&limit=1')
    if (newest.length > 0) {
      const newestTime = new Date(newest[0].timestamp)
      const yesterday = subDays(newestTime, 1)
      from = format(yesterday, "yyyy-MM-dd'T'HH:mm")
    }
    await load()
  }

  // Pobranie z serwera wybranych danych
  async function load() {
    if (selected.length === 0) {
      throw new Error('Wybierz co najmniej jedną serię w checkboxie')
    }
    // limit 10000 bo bez tego domyąślnie zwraca tylko 1000 wyników
    let path = 'measurements?limit=10000&series=' + selected.join(',')
    // Zamiana czasu na czas UTC ze strefą
    if (from !== '') {
      const fromUtc = new Date(from).toISOString()
      path = path + '&from=' + fromUtc
    }
    if (to !== '') {
      const toUtc = new Date(to).toISOString()
      path = path + '&to=' + toUtc
    }
        const measurements = await get(path)

    // Kolumny tabeli, czyli serie zaznaczone w chwili wysłania zapytania do api
    const columns = []
    for (const series of allSeries) {
        // Tylko serie zaznaczone w filtrze
      if (selected.includes(series.id)) {
        columns.push(series)
      }
    }

    // Wiersze tabeli, jeden wiersz to jeden moment w czasie, a kolumny to osobne serie
    const newRows = []
    const rowByTime = {}
    for (const m of measurements) {
      // Dodanie pustego wiersza jeśli jeszcze go nie ma dla danego czasu
      if (rowByTime[m.timestamp] === undefined) {
        const newRow = { timestamp: m.timestamp, values: {} }
        rowByTime[m.timestamp] = newRow
        newRows.push(newRow)
      }
      // Wpisanie wartości pomiaru do wiersza tego czasu, w kolumnie tej serii
      const row = rowByTime[m.timestamp]
      row.values[m.seriesId] = m.value
    }

    // podmienienie nowych danych do samej tabeli
    shownSeries = columns
    rows = newRows
  }

  // Nowe zapytanie do api z obecnymi filtrami
  function show(event) {
    // by nie przeładować całej strony przy nowym zapytaniu do api
    event.preventDefault()
    loading = load()
  }
</script>

<h2>Wyniki pomiarów</h2>

<!-- Filtry do wyboru serii i przedziału czasu -->
<form class="mb-3" onsubmit={show}>
  <fieldset>
    <legend>Serie</legend>
    {#each allSeries as series}
      <label class="me-3">
        <input type="checkbox" value={series.id} bind:group={selected} />
        {series.name}
      </label>
    {/each}
  </fieldset>
  <label class="me-3">Od <input type="datetime-local" bind:value={from} max={to} /></label>
  <label class="me-3">Do <input type="datetime-local" bind:value={to} min={from} /></label>
  <button type="submit" class="btn btn-primary">Pokaż</button>
</form>

{#await loading}
  <p>Ładowanie...</p>
{:then}
  {#if rows.length === 0}
    <p>Brak wyników w wybranym przedziale czasu.</p>
  {:else}
  <!-- Tabela wyników, gdzie wiersz to czas, kolumna to seria -->
  <div class="table-responsive">
    <table class="table table-sm">
      <thead>
        <tr>
          <th>Czas</th>
          {#each shownSeries as series}
            <th>{series.name}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row}
          <tr>
            <td>{new Date(row.timestamp).toLocaleString('pl-PL')}</td>
            {#each shownSeries as series}
              <td>{row.values[series.id]}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
   {/if}
{:catch error}
  <p class="text-danger" role="alert">{error.message}</p>
{/await}