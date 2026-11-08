import {defineConfig, devices} from '@playwright/test';
import {homedir} from 'node:os';
import {join} from 'node:path';

/**
 * Playwright cho UI thật (KB-4.9) — chạy **trong WSL**, không cần sudo, không cần Docker.
 *
 * Vì sao dùng Playwright thay vì tự viết CDP client qua Chrome của Windows:
 * - Chromium chạy native trong WSL ⇒ không qua biên VM, không phải dò `127.0.0.1` vs `[::1]`, không
 *   `netstat.exe`/PowerShell; khởi động ~1s thay vì 5-8s.
 * - Có auto-wait (`expect(locator)`), trace khi fail, screenshot/video ⇒ review được thẩm mỹ.
 * - Sau này wire vào CI/Docker dễ (TD-24) vì cùng hệ Linux.
 *
 * `LD_LIBRARY_PATH`: Chromium cần 4 lib X11 mà bản Ubuntu 26.04 này không có sẵn
 * (`libXcomposite`, `libXdamage`, `libXfixes`, `libXrandr`). Không có sudo ⇒ tải `.deb` rồi
 * `dpkg -x` vào `~/.local/pw-libs`, trỏ đường dẫn đó cho **process browser** qua `launchOptions.env`.
 * (Xem README/`tools/setup-playwright.sh`.)
 */
const PW_LIBS = join(homedir(), '.local', 'pw-libs', 'root', 'usr', 'lib', 'x86_64-linux-gnu');

/**
 * URL app cần verify (KB-4.9):
 * - Mặc định **`http://localhost:3000`** = `npm run dev` (hot reload) ⇒ vòng lặp sửa UI ~1-3s.
 *   Nếu dev server chưa chạy, Playwright tự bật qua `webServer` bên dưới.
 * - Container (`:3010`) chỉ dùng **một lần cuối ticket** để chắc bản build production cũng đúng:
 *   `npm run test:e2e:prod` (đặt `APP_URL=http://localhost:3010`).
 */
const BASE_URL = process.env.APP_URL ?? 'http://localhost:3000';

export default defineConfig({
    testDir: './e2e',
    timeout: 45_000,
    expect: {timeout: 10_000},
    fullyParallel: false,
    workers: 1,
    retries: 0,
    reporter: [['list']],
    // Chỉ tự bật `next dev` khi test nhắm dev server (không truyền APP_URL).
    webServer: process.env.APP_URL
        ? undefined
        : {
            command: 'npm run dev',
            url: BASE_URL,
            reuseExistingServer: true,
            timeout: 90_000,
        },
    use: {
        baseURL: BASE_URL,
        viewport: {width: 1440, height: 900},
        screenshot: 'only-on-failure',
        trace: 'retain-on-failure',
        launchOptions: {
            env: {...process.env, LD_LIBRARY_PATH: `${PW_LIBS}:${process.env.LD_LIBRARY_PATH ?? ''}`},
        },
    },
    projects: [
        // viewport đặt SAU khi spread device, nếu không sẽ bị 1280x720 của Desktop Chrome ghi đè
        {name: 'chromium', use: {...devices['Desktop Chrome'], viewport: {width: 1440, height: 900}}}
    ],
});
