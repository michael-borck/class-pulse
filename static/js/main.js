// ClassPulse Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
  // Initialize chart rendering for results pages
  initializeCharts();
  
  // Setup any automatic refresh/polling functionality
  setupPolling();
  
  // Add event listeners for theme toggle if implemented
  setupThemeToggle();
});

function initializeCharts() {
  // Find chart containers and initialize them
  const chartContainer = document.getElementById('chart-container');
  
  if (chartContainer) {
    const chartType = chartContainer.getAttribute('data-chart-type');
    const chartData = JSON.parse(chartContainer.getAttribute('data-chart-data'));
    
    if (chartType === 'wordCloud') {
      // Initialize word cloud with jQCloud
      $('#word-cloud-container').jQCloud(chartData, {
        width: chartContainer.offsetWidth,
        height: 400,
        colors: ['#36a2eb', '#ff6384', '#4bc0c0', '#ffcd56', '#9966ff']
      });
    } else {
      // Initialize Chart.js charts
      const ctx = document.createElement('canvas');
      chartContainer.appendChild(ctx);
      
      new Chart(ctx, {
        type: chartType,
        data: chartData,
        options: {
          responsive: true,
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                precision: 0
              }
            }
          }
        }
      });
    }
  }
}

function setupPolling() {
  // This would be used if not using WebSockets
  // Currently, we're using WebSockets for real-time updates
}

function setupThemeToggle() {
  // Implement theme toggle (light/dark mode) if needed
  const themeToggle = document.getElementById('theme-toggle');
  
  if (themeToggle) {
    themeToggle.addEventListener('click', function() {
      document.body.classList.toggle('dark-theme');
      
      // Save preference to localStorage
      const isDarkMode = document.body.classList.contains('dark-theme');
      localStorage.setItem('darkMode', isDarkMode);
    });
    
    // Check for saved theme preference
    const savedDarkMode = localStorage.getItem('darkMode') === 'true';
    if (savedDarkMode) {
      document.body.classList.add('dark-theme');
    }
  }
}
