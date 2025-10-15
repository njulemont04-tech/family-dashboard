// A simple, no-op service worker that's enough to make the app installable.
self.addEventListener("fetch", (event) => {
  // We are not caching anything for now, just fulfilling the requirement.
  return;
});
