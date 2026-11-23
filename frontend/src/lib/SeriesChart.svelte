<!-- Wykres -->
<script>
  // Bazowano na:
  // https://svelte.dev/tutorial/svelte/bind-this
  // https://www.chartjs.org/docs/latest/charts/line.html
  // https://www.chartjs.org/docs/latest/samples/legend/point-style.html
  // https://www.chartjs.org/docs/latest/axes/cartesian/time.html
  // https://www.chartjs.org/docs/latest/samples/advanced/programmatic-events.html
  import Chart from 'chart.js/auto'
  import 'chartjs-adapter-date-fns'
  import { pl } from 'date-fns/locale'

  // Dane z widoku wyników
  let { shownSeries, rows } = $props()

  // Canvas, na którym rysowany jest wykres
  let canvas

  // Wykres Chart.js (używany też w funkcji highlight do wyróżnienia wybranego punktu na wykresie)
  let chart


  // Rysowanie wykresu, gdy płótno jest na stronie
  $effect(() => {
    // Jedna linia na każdą serię
    const datasets = []
    // Co ile punktów rysować kształt, bez tego zlewają się w jednolitą linię
    const step = Math.ceil(rows.length / 20)
    for (const series of shownSeries) {
      const points = []
      for (const row of rows) {
        const point = { x: row.timestamp, y: row.values[series.id] }
        points.push(point)
      }
      const dataset = {
        label: series.name,
        data: points,
        borderColor: series.color,
        backgroundColor: series.color,
        pointStyle: series.icon,
        // Kształt tylko na co którymś punkcie, reszta punktów bez kształtu
        pointRadius: function (context) {
          if (context.dataIndex % step === 0) {
            return 5
          }
          return 0
        },
        // Większy punkt po najechaniu i kliknięciu czasu w tabeli
        pointHoverRadius: 8,
      }
      datasets.push(dataset)
    }

    // Wykres liniowy
    chart = new Chart(canvas, {
      type: 'line',
      data: { datasets: datasets },
      options: {
        // by wysokość była brana z własnego CSSa a nie z domyślnych proporcji chart.js
        maintainAspectRatio: false,


        // Wyświetlenie dymka najbliższego myszcze punktu i by zaznaczyły się wszystkie z danego czasu
        interaction: { mode: 'index', intersect: false },

        // By Linia nie przerywała się tam, gdzie seria nie ma wartości
        spanGaps: true,
        // Pokazanie na legendzie kształtu dla danej serii, a nie tylko koloru
        plugins: {
          legend: { labels: { usePointStyle: true } },
        },
        scales: {
          x: {
            type: 'time',
            //By nazwy miesięcy były po polsku
            adapters: { date: { locale: pl } },
            // format godzin 24h i data i czas w dymkach takie jak w tabeli
            time: {
              tooltipFormat: 'd.MM.yyyy, HH:mm:ss',
              displayFormats: {
                minute: 'HH:mm',
                hour: 'HH:mm',
                day: 'd MMM',
              },
            },
          },
        },
      },
    })

    // Usunięcie wykresu, gdy komponent znika ze strony
    return () => {
      chart.destroy()
    }
  })

  // Wyróżnienie na wykresie punktów z wybranego wiersza tabeli
  export function highlight(index) {
    const active = []
    for (let i = 0; i < shownSeries.length; i++) {
      const series = shownSeries[i]
      // Tylko serie, które mają wartość w tym wierszu
      if (rows[index].values[series.id] !== undefined) {
        active.push({ datasetIndex: i, index: index })
      }
    }
    chart.setActiveElements(active)
    chart.tooltip.setActiveElements(active, { x: 0, y: 0 })
    chart.update()
  }
</script>

<!-- Opis wykresu dla czytników -->
<div class="chart" role="img" aria-label="Wykres liniowy wyników pomiarów w czasie">
  <canvas bind:this={canvas}></canvas>
</div>

<style>
  /* Pojemnik wykresu, by wysokość zależała od wysokości ekranu a szerokość dopasowuje sam Chart.js */
  .chart {
    position: relative;
    height: 40vh;
  }
</style>