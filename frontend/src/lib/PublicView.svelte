<!-- Widok użytkownika z filtrami, wykresami oraz z tabelą wyników -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/await-blocks
  import { get } from './api.js'
</script>

<h2>Wyniki pomiarów</h2>

<!-- Lista serii pobrana z API -->
{#await get('series')}
  <p>Ładowanie...</p>
{:then allSeries}
  <ul>
    {#each allSeries as series}
      <li>{series.name}</li>
    {/each}
  </ul>
{:catch error}
  <p class="text-danger" role="alert">{error.message}</p>
{/await}