// `Location` in the browser preview, on top of the Geolocation API.

function fix(position) {
  const { coords, timestamp } = position;
  const result = { latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy, timestamp: timestamp / 1000 };
  if (coords.altitude != null) result.altitude = coords.altitude;
  if (coords.speed != null) result.speed = coords.speed;
  if (coords.heading != null) result.heading = coords.heading;
  return result;
}

export function modules(host) {
  const watchers = new Map();
  return {
    Location: {
      get_current({ accuracy, timeout }) {
        return new Promise((resolve) => {
          if (!navigator.geolocation) return resolve(null);
          navigator.geolocation.getCurrentPosition(
            (position) => resolve(fix(position)),
            () => resolve(null),
            { enableHighAccuracy: accuracy === "high", timeout: timeout * 1000 },
          );
        });
      },
      start_watching({ accuracy }) {
        if (!navigator.geolocation) throw new Error("This browser has no Geolocation API");
        const id = watchers.size + 1;
        watchers.set(id, navigator.geolocation.watchPosition(
          (position) => host.moduleEvent("Location", "position", { id, value: fix(position) }),
          null,
          { enableHighAccuracy: accuracy === "high" },
        ));
        return id;
      },
      stop_watching({ id }) {
        navigator.geolocation?.clearWatch(watchers.get(id));
        watchers.delete(id);
        return null;
      },
    },
  };
}
