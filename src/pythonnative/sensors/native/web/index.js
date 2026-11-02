// `Sensors` in the browser preview, on top of `DeviceMotionEvent`. Browsers
// expose no magnetometer or barometer, so those two stay unavailable.

const IS_IOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
// iOS Safari reports gravity with the opposite sign from the W3C spec, which
// is also the sign the Python facade promises.
const ACCELERATION_SIGN = IS_IOS ? -1 : 1;
const RADIANS_PER_DEGREE = Math.PI / 180;

function available(sensor) {
  if (sensor !== "accelerometer" && sensor !== "gyroscope") return false;
  // Desktop browsers define the event but never fire it with real values.
  return typeof DeviceMotionEvent !== "undefined" && navigator.maxTouchPoints > 0;
}

function reading(sensor, event) {
  if (sensor === "accelerometer") {
    const value = event.accelerationIncludingGravity;
    if (value?.x == null) return null;
    return { x: value.x * ACCELERATION_SIGN, y: value.y * ACCELERATION_SIGN, z: value.z * ACCELERATION_SIGN };
  }
  // `alpha`, `beta`, and `gamma` turn around z, x, and y, in degrees per second.
  const rate = event.rotationRate;
  if (rate?.alpha == null) return null;
  return { x: rate.beta * RADIANS_PER_DEGREE, y: rate.gamma * RADIANS_PER_DEGREE, z: rate.alpha * RADIANS_PER_DEGREE };
}

export function modules(host) {
  const listeners = new Map();
  let nextId = 1;
  return {
    Sensors: {
      is_available({ sensor }) {
        return available(sensor);
      },
      async start({ sensor, hz }) {
        if (!available(sensor)) throw new Error(`This browser has no ${sensor}`);
        // Only Safari holds events back until this answers, and it must run
        // during a user gesture. Chrome defines it too, but fires events anyway.
        if (IS_IOS && typeof DeviceMotionEvent.requestPermission === "function") {
          if ((await DeviceMotionEvent.requestPermission()) !== "granted") {
            throw new Error("Motion permission was denied");
          }
        }
        const id = nextId++;
        const interval = 800 / hz;
        let last = 0;
        const listener = (event) => {
          if (event.timeStamp - last < interval) return;
          const value = reading(sensor, event);
          if (value === null) return;
          last = event.timeStamp;
          host.moduleEvent("Sensors", "reading", { id, value: { ...value, timestamp: Date.now() / 1000 } });
        };
        window.addEventListener("devicemotion", listener);
        listeners.set(id, listener);
        return id;
      },
      stop({ id }) {
        window.removeEventListener("devicemotion", listeners.get(id));
        listeners.delete(id);
        return null;
      },
    },
  };
}
