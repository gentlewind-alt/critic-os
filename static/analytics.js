/**
 * Vercel Web Analytics Utilities
 * 
 * This module provides helper functions for tracking custom events
 * using Vercel Web Analytics via the script injection method.
 * 
 * Documentation: https://vercel.com/docs/analytics
 */

// Initialize the Vercel Analytics queue before the script loads
// This allows events to be queued and processed once the script is ready
window.va = window.va || function () { 
  (window.vaq = window.vaq || []).push(arguments); 
};

/**
 * Track a custom event with optional data
 * @param {string} eventName - Name of the event (max 255 chars)
 * @param {Object} data - Optional key-value pairs (strings, numbers, booleans, or null)
 * @example
 * trackEvent('button_click', { button_id: 'login', page: 'home' });
 */
function trackEvent(eventName, data = {}) {
  if (typeof window.va !== 'function') {
    console.warn('Vercel Analytics not loaded yet');
    return;
  }
  
  window.va('event', {
    name: eventName,
    data: data
  });
}

/**
 * Track a custom pageview (useful for SPAs or custom routing)
 * @param {Object} options - Options for pageview tracking
 * @param {string} options.path - Custom path to track
 * @param {string} options.route - Route name
 * @example
 * trackPageview({ path: '/custom-page', route: '/custom-page' });
 */
function trackPageview(options = {}) {
  if (typeof window.va !== 'function') {
    console.warn('Vercel Analytics not loaded yet');
    return;
  }
  
  window.va('pageview', options);
}

/**
 * Enable cookie-based tracking (opt-in for EU compliance)
 */
function enableAnalyticsCookie() {
  if (typeof window.va !== 'function') {
    console.warn('Vercel Analytics not loaded yet');
    return;
  }
  
  window.va('enableCookie');
}

// Make functions available globally
if (typeof window !== 'undefined') {
  window.trackEvent = trackEvent;
  window.trackPageview = trackPageview;
  window.enableAnalyticsCookie = enableAnalyticsCookie;
}
