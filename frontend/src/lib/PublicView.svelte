<!-- Widok użytkownika z filtrami, wykresami oraz z tabelą wyników -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/await-blocks
  // https://svelte.dev/tutorial/svelte/group-inputs
  // https://getbootstrap.com/docs/5.3/content/tables/
  // https://date-fns.org/docs/format
  // https://stackoverflow.com/questions/355313/how-do-i-hide-an-element-when-printing-a-web-page
  import { get } from './api.js'
  import { format, subDays } from 'date-fns'
  import SeriesChart from './SeriesChart.svelte'

  // Wszystkie serie do wyboru w filtrze
  let allSeries = $state([])

  // Pola filtra
  let selected = $state([])
  let from = $state('')
  let to = $state('')

   // Tabela wyników, gdzie kolumny to serie i wiersze to czas
  let shownSeries = $state([])
  let rows = $state([])

   // Wykres, na którym wyróżniane są punkty klikniętego wiersza tabeli
  let seriesChart = $state()

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
<form class="mb-3 d-print-none" onsubmit={show}>
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
  <!-- Wykres i tabela, obok siebie na szerokim ekranie, jedno pod drugim na telefonie -->
  <div class="results">
  <!-- Wykres z wynikami -->
  <div class="chart-box">
    <SeriesChart bind:this={seriesChart} shownSeries={shownSeries} rows={rows} />
  </div>
  <!-- Tabela wyników, gdzie wiersz to czas, kolumna to seria -->
  <div class="table-responsive table-box">
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
        {#each rows as row, index}
          <tr>
            <td>
              <!-- Kliknięcie czasu wyróżnia punkty tego wiersza na wykresie -->
              <button type="button" class="btn btn-link p-0" onclick={() => seriesChart.highlight(index)}>
                {new Date(row.timestamp).toLocaleString('pl-PL')}
              </button>
            </td>
            {#each shownSeries as series}
              <td>{row.values[series.id]}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  </div>
   {/if}
{:catch error}
  <p class="text-danger" role="alert">{error.message}</p>
{/await}


<style>
  /* Wykres i tabela obok siebie */
  .results {
    display: flex;
    gap: 1rem;
  }

  /* Wykres i tabela po połowie szerokości*/
  .chart-box,
  .table-box {
    flex: 1;
    /* bez tego wykres w układzie flex nie zwęża się przy zmniejszaniu okna */
    min-width: 0;
  }

  /* Tabela najwyżej na pół ekranu, potem przewija się w obrębie swojego pola */
  .table-box {
    max-height: 50vh;
  }

  /* by na telefonie/wąskim ekranie wykres i tabela były jedno pod drugim */
  @media (max-width: 1000px) {
    .results {
      flex-direction: column;
    }
  }

    /* Styl do wydruku*/
  @media print {
    /* By widać było całą tabelę bez przewijania */
    .table-box {
      max-height: none;
    }
    /* by czas w tabeli był zwyczajny, a nie jak do kliknięcia */
    .btn-link {
      color: inherit;
      text-decoration: none;
    }
  }

</style>