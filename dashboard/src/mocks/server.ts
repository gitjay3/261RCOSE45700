import { setupServer } from 'msw/node';
import { handlers } from './handlers';

/** Node 환경(Vitest 등) MSW — 브라우저 setupWorker와 동일한 핸들러 공유. */
export const server = setupServer(...handlers);
