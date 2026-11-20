const KEY = 'pq.deviceId';

/**
 * Installation identifier of this phone. The server only ever stores its SHA-256 (RG-13);
 * clearing the browser data means re-activating the phone, which requires HR approval.
 */
export function deviceId(): string {
  try {
    const existing = localStorage.getItem(KEY);
    if (existing) return existing;
    const created = crypto.randomUUID();
    localStorage.setItem(KEY, created);
    return created;
  } catch {
    return 'no-storage';
  }
}

/** Short human description of the phone, shown to HR in phone-change requests. */
export function deviceLabel(): { model: string; os: string } {
  const ua = navigator.userAgent;
  const android = /Android\s([\d.]+)/.exec(ua);
  const ios = /OS (\d+[_\d]*) like Mac OS X/.exec(ua);
  const model = /;\s*([^;)]+)\sBuild\//.exec(ua)?.[1] ?? (ios ? 'iPhone' : 'Navigateur');
  const os = android
    ? `Android ${android[1]}`
    : ios
      ? `iOS ${ios[1]?.replace(/_/g, '.')}`
      : navigator.platform;
  return { model: model.slice(0, 120), os: os.slice(0, 60) };
}
