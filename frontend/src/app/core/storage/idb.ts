/**
 * Minimal promise wrapper around IndexedDB (kiosk configuration, its CryptoKey and the offline
 * queue survive reloads and power cuts; a non-extractable CryptoKey can be stored as is).
 */
const DB_NAME = 'pointqr';
const DB_VERSION = 1;
export const STORES = ['config', 'queue'] as const;
export type StoreName = (typeof STORES)[number];

let opening: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  opening ??= new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      for (const name of STORES) {
        if (!request.result.objectStoreNames.contains(name)) request.result.createObjectStore(name);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('IndexedDB indisponible'));
  });
  return opening;
}

function run<T>(
  store: StoreName,
  mode: IDBTransactionMode,
  action: (s: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  return open().then(
    (db) =>
      new Promise<T>((resolve, reject) => {
        const request = action(db.transaction(store, mode).objectStore(store));
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error ?? new Error('IndexedDB'));
      }),
  );
}

export const idb = {
  get<T>(store: StoreName, key: string): Promise<T | undefined> {
    return run<T | undefined>(store, 'readonly', (s) => s.get(key) as IDBRequest<T | undefined>);
  },
  set(store: StoreName, key: string, value: unknown): Promise<IDBValidKey> {
    return run(store, 'readwrite', (s) => s.put(value, key));
  },
  delete(store: StoreName, key: string): Promise<undefined> {
    return run(store, 'readwrite', (s) => s.delete(key));
  },
  all<T>(store: StoreName): Promise<T[]> {
    return run<T[]>(store, 'readonly', (s) => s.getAll() as IDBRequest<T[]>);
  },
  count(store: StoreName): Promise<number> {
    return run(store, 'readonly', (s) => s.count());
  },
  clear(store: StoreName): Promise<undefined> {
    return run(store, 'readwrite', (s) => s.clear());
  },
};
