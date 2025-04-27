/**
 * Theme toggling functionality for ClassPulse
 * Supports light/dark mode switching with localStorage persistence
 */

document.addEventListener('DOMContentLoaded', function() {
    const themeToggleBtn = document.getElementById('theme-toggle');
    const htmlElement = document.documentElement;
    const THEME_KEY = 'classpulse_theme';
    
    // Check for saved theme preference or use device preference
    const savedTheme = localStorage.getItem(THEME_KEY);
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    // Apply initial theme
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        applyDarkTheme();
    } else {
        applyLightTheme();
    }
    
    // Handle theme toggle button click
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', function() {
            if (htmlElement.classList.contains('dark')) {
                applyLightTheme();
            } else {
                applyDarkTheme();
            }
        });
    }
    
    function applyDarkTheme() {
        htmlElement.classList.add('dark');
        localStorage.setItem(THEME_KEY, 'dark');
        if (themeToggleBtn) themeToggleBtn.textContent = '☀️';
    }
    
    function applyLightTheme() {
        htmlElement.classList.remove('dark');
        localStorage.setItem(THEME_KEY, 'light');
        if (themeToggleBtn) themeToggleBtn.textContent = '🌓';
    }
});