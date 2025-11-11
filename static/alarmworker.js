setInterval(async () => {
  try {
    const res = await fetch("/api/alarms");
    if (!res.ok) return;
    const { alarms } = await res.json();
    const now = Date.now();

    alarms.forEach((alarm) => {
      if (alarm.is_done) return;
      const trigger =
        new Date(alarm.alarm_time).getTime() -
        alarm.notify_before_minutes * 60000;
      if (trigger <= now) {
        if (Notification.permission === "granted") {
          const notif = new Notification(alarm.title, {
            body: alarm.description || "Time!",
            tag: "alarm-" + alarm.id,
            requireInteraction: true,
          });
          const sound = new Audio(
            "https://www.soundjay.com/buttons/beep-01a.mp3"
          );
          sound.loop = true;
          sound.play().catch(() => {});
          notif.onclick = () => {
            sound.pause();
            sound.currentTime = 0;
            notif.close();
            window.focus();
          };
        } else if (Notification.permission === "default") {
          Notification.requestPermission().then((perm) => {
            if (perm === "granted") {
              // retry once
              setTimeout(() => location.reload(), 1000);
            }
          });
        }
      }
    });
  } catch (e) {
    console.error("Worker error:", e);
  }
}, 3000); // every 3 seconds
