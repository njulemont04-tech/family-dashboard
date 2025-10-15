// This is a basic "network-first" service worker.
// It satisfies the fetch handler requirement for PWA installability.

self.addEventListener("install", (event) => {
  console.log("Service worker installing...");
  // Add a call to skipWaiting to activate the new service worker immediately.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  console.log("Service worker activating...");
});

self.addEventListener("fetch", (event) => {
  // This fetch handler is the key part.
  // We are just letting the network handle the request, which is fine for now.
  event.respondWith(fetch(event.request));
});
