<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte
  // https://getbootstrap.com/docs/5.3/getting-started/introduction/
  import PublicView from './lib/PublicView.svelte'
  import AdminView from './lib/AdminView.svelte'

  // Obecnie widoczny widok
  let view = $state('public')
</script>

<header class="container py-3">
  <h1 class="h4">Poziom morza</h1>
  <nav>
    {#if view === 'public'}
      <button type="button" class="btn btn-outline-primary" onclick={() => (view = 'admin')}>Panel administratora</button>
    {:else}
      <button type="button" class="btn btn-outline-primary" onclick={() => (view = 'public')}>Wróć do wyników</button>
    {/if}
  </nav>
</header>

<!-- Zmiana obecnego widoku -->
<main class="container">
  {#if view === 'public'}
    <PublicView />
  {:else}
    <AdminView />
  {/if}
</main>