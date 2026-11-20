import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { ServerStatus } from './server-status';

describe('ServerStatus', () => {
  let http: HttpTestingController;
  let status: ServerStatus;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    http = TestBed.inject(HttpTestingController);
    status = TestBed.inject(ServerStatus);
  });

  afterEach(() => http.verify());

  async function answer(body: object | null, error = false): Promise<void> {
    TestBed.tick();
    const req = http.expectOne('/api/v1/health/');
    if (error) req.flush(null, { status: 503, statusText: 'Unavailable' });
    else req.flush(body);
    // Let the resource loader promise settle, then flush signal effects.
    await new Promise((resolve) => setTimeout(resolve, 0));
    TestBed.tick();
  }

  it('is online and follows the server clock, not the device clock', async () => {
    const serverEpoch = Date.now() + 30 * 60 * 1000; // device clock is 30 min behind (R4)
    await answer({
      status: 'ok',
      version: '0.1.0',
      server_time: new Date(serverEpoch).toISOString(),
      epoch_ms: serverEpoch,
      database: true,
      cache: true,
    });
    expect(status.state()).toBe('online');
    expect(status.version()).toBe('0.1.0');
    const drift = Math.abs((status.serverTime()?.getTime() ?? 0) - serverEpoch);
    expect(drift).toBeLessThan(2000);
  });

  it('reports degraded when a dependency is down', async () => {
    await answer({
      status: 'degraded',
      version: '0.1.0',
      server_time: new Date().toISOString(),
      epoch_ms: Date.now(),
      database: true,
      cache: false,
    });
    expect(status.state()).toBe('degraded');
  });

  it('reports offline when the API cannot be reached', async () => {
    await answer(null, true);
    expect(status.state()).toBe('offline');
    expect(status.serverTime()).toBeNull();
  });
});
