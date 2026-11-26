<!-- Zarządzanie seriami i czujnikami dla zalogowanego admina -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/component-events
  // https://svelte.dev/playground/7guis-crud
  // https://stackoverflow.com/questions/9334636/how-to-create-a-dialog-with-ok-and-cancel-options
  // https://svelte.dev/tutorial/svelte/select-bindings
  import { get, post, put, del } from './api.js'

  // Funkcja z panelu administratora do wyświetlania błędów
  let { showError } = $props()

  // Serie pobrane z backendu
  let allSeries = $state([])

  // Czujniki pobrane z backendu
  let sensors = $state([])

  // Pola formularza serii
  let name = $state('')
  let minValue = $state(null)
  let maxValue = $state(null)
  let unit = $state('')
  let color = $state('#000000')
  let icon = $state('circle')

  // Id edytowanej serii (jeśli jest null to formularz dodaje nową serię)
  let editId = $state(null)

  // Pola formularza czujnika
  let sensorName = $state('')
  let seriesId = $state(null)

  // Klucz API nowego czujnika
  let apiKey = $state('')


  // Pobranie danych z serwera
  async function load() {
    try {
      allSeries = await get('series')
      sensors = await get('sensors')
    } catch (error) {
        showError(error)
        
    }
  }

  // Wyczyszczenie formularza serii i powrót do dodawania nowej
  function resetForm() {
    editId = null
    name = ''
    minValue = null
    maxValue = null
    unit = ''
    color = '#000000'
    icon = 'circle'
  }

  // Wpisanie danych serii do formularza, aby ją edytować
  function editSeries(series) {
    editId = series.id
    name = series.name
    minValue = series.minValue
    maxValue = series.maxValue
    unit = series.unit
    color = series.color
    icon = series.icon
  }

  // Zapisanie/edytowanie serii i odświeżenie listy
  async function saveSeries(event) {
    event.preventDefault()
    try {
      const data = {
        name: name,
        minValue: minValue,
        maxValue: maxValue,
        unit: unit,
        color: color,
        icon: icon,
      }
      // Jeśli to dodanie serii to post, jak edycja to put
      if (editId === null) {
        await post('series', data)
      } else {
        await put('series/' + editId, data)
      }
      resetForm()
      await load()
    } catch (error) {
      showError(error)
    }
  }

  // Usunięcie serii wraz z czujnikami i ich wynikami
  async function deleteSeries(series) {
    // Pytanie do potwierdzenia usunięcia
    const question = 'Usunąć serię ' + series.name + ' razem z jej wynikami i czujnikami?'
    if (confirm(question)) {
      try {
        await del('series/' + series.id)
        resetForm()
        await load()
      } catch (error) {
                showError(error)
      }
    }
  }

  // Nazwa serii z danym id
  function seriesName(id) {
    for (const series of allSeries) {
      if (series.id === id) {
        return series.name
      }
    }
    return ''
  }

  // Wyrejestrowanie czujnika (wyniki zostają)
  async function deleteSensor(sensor) {
    const question = 'Wyrejestrować czujnik ' + sensor.name +'?'
    if (confirm(question)) {
      try {
        await del('sensors/' + sensor.id)
        await load()
      } catch (error) {
        showError(error)
      }
    }
  }

  // Rejestracja czujnika 
  async function addSensor(event) {
    event.preventDefault()
    try {
      const data = { name: sensorName, seriesId: seriesId }
      const result = await post('sensors', data)
      apiKey = result.apiKey
      sensorName = ''
      await load()
    } catch (error) {
      showError(error)
    }
  }

  load()
</script>

<h3>Serie</h3>
<!-- Lista serii -->
<div class="table-responsive">
  <table class="table table-sm">
    <thead>
      <tr>
        <th>Nazwa</th>
        <th>Zakres</th>
        <th>Kolor</th>
        <th>Kształt</th>
        <th>Akcje</th>
      </tr>
    </thead>
    <tbody>
      {#each allSeries as series}
        <tr>
          <td>{series.name}</td>
          <td>{series.minValue} – {series.maxValue} {series.unit}</td>
          <td>{series.color}</td>
          <td>{series.icon}</td>
          <td>
            <button type="button" class="btn btn-link p-0 me-3" onclick={() => editSeries(series)}>Edytuj</button>
            <button type="button" class="btn btn-link p-0" onclick={() => deleteSeries(series)}>Usuń</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>



<!-- Formularz by dodać nową serię albo edytować istniejącą -->
<form class="mb-3" onsubmit={saveSeries}>
  <label class="me-3">Nazwa <input bind:value={name} maxlength="100" required /></label>
  <label class="me-3">Minimum <input type="number" step="any" bind:value={minValue} max={maxValue} required /></label>
  <label class="me-3">Maksimum <input type="number" step="any" bind:value={maxValue} min={minValue} required /></label>
  <label class="me-3">Jednostka <input bind:value={unit} maxlength="20" /></label>
  <label class="me-3">Kolor <input type="color" bind:value={color} /></label>
  <label class="me-3">Kształt
    <select bind:value={icon}>
      <option value="circle">koło</option>
      <option value="triangle">trójkąt</option>
      <option value="rect">kwadrat</option>
      <option value="rectRot">romb</option>
      <option value="star">gwiazda</option>
      <option value="cross">krzyżyk</option>
    </select>
  </label>
  {#if editId === null}
    <button type="submit" class="btn btn-primary">Dodaj serię</button>
  {:else}
    <button type="submit" class="btn btn-primary me-3">Zapisz zmiany</button>
    <button type="button" class="btn btn-outline-primary" onclick={resetForm}>Anuluj</button>
  {/if}
</form>

<h3>Czujniki</h3>
<!-- Lista czujników -->
<div class="table-responsive">
  <table class="table table-sm">
    <thead>
      <tr>
        <th>Nazwa</th>
        <th>Seria</th>
        <th>Akcje</th>
      </tr>
    </thead>
    <tbody>
      {#each sensors as sensor}
        <tr>
          <td>{sensor.name}</td>
          <td>{seriesName(sensor.seriesId)}</td>
          <td>
            <button type="button" class="btn btn-link p-0" onclick={() => deleteSensor(sensor)}>Wyrejestruj</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<!-- Formularz do rejestrowania nowego czujnika -->
<form class="mb-3" onsubmit={addSensor}>
  <label class="me-3">Nazwa <input bind:value={sensorName} maxlength="100" required /></label>
  <label class="me-3">Seria
    <select bind:value={seriesId} required>
      {#each allSeries as series}
        <option value={series.id}>{series.name}</option>
      {/each}
    </select>
  </label>
  <button type="submit" class="btn btn-primary">Zarejestruj czujnik</button>
</form>

<!-- Klucz API wyświetlany po nowej rejestracji -->
{#if apiKey !== ''}
  <p>Klucz API nowego czujnika (widoczny tylko raz tutaj, zapisz go): <code>{apiKey}</code></p>
{/if}
