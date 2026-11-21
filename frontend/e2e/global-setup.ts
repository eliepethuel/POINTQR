import { execSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';

/** Creates fresh test data through the backend command `e2e_prepare` (JSON on stdout). */
export default function globalSetup(): void {
  const command =
    process.env['E2E_PREPARE'] ??
    'uv run --project ../backend python ../backend/manage.py e2e_prepare';
  const cwd = process.env['E2E_PREPARE_CWD'] ?? join(__dirname, '..');
  const output = execSync(command, { cwd, encoding: 'utf8', stdio: ['ignore', 'pipe', 'inherit'] });
  const json = output.slice(output.indexOf('{'));
  JSON.parse(json); // fail early on unexpected output
  writeFileSync(join(__dirname, '.data.json'), json, 'utf8');
}
