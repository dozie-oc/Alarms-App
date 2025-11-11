self.addEventListener("install", (e) => self.skipWaiting());
self.addEventListener("activate", (e) => self.clients.claim());

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  e.waitUntil(clients.openWindow("/"));
});

self.addEventListener("push", (e) => {
  const audio = new Audio("https://www.soundjay.com/buttons/beep-01a.mp3");
  audio.loop = true;
  audio.play().catch(() => {});
});
