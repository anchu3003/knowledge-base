/**
 * UI verification bằng **Chrome thật** qua CDP (KB-4.9 follow-up, trả một phần TD-26).
 *
 * Vì sao phải chạy trên **Windows**: Chrome của máy này chỉ mở DevTools ở `127.0.0.1:9222`
 * (`--remote-debugging-address=0.0.0.0` bị Chrome mới bỏ qua) ⇒ WSL **không** kết nối được.
 * `node.exe` trên Windows thì gọi được cả `127.0.0.1:9222` **và** `localhost:3010` (WSL forward).
 * ⇒ driver chạy bằng `node.exe`, chỉ dùng `fetch` + `WebSocket` có sẵn trong Node ≥ 22 (0 dependency).
 *
 * Cách dùng (từ WSL): `bash tools/ui-verify.sh`
 * Env: CDP_URL (http://127.0.0.1:9222), APP_URL (http://localhost:3010), OUT_DIR (C:\Temp)
 */

import {mkdirSync, writeFileSync} from 'node:fs';
import {join} from 'node:path';

const CDP_URL = process.env.CDP_URL ?? '';
/**
 * Chrome có thể bind DevTools ở 127.0.0.1 hoặc [::1] tuỳ phiên bản/cách chạy ⇒ dò từng ứng viên.
 * Ghi đè bằng env CDP_URL khi cần trỏ tay.
 */
const CDP_CANDIDATES = CDP_URL
    ? [CDP_URL]
    : ['http://127.0.0.1:9222', 'http://[::1]:9222', 'http://localhost:9222'];
let CDP = CDP_CANDIDATES[0];
const APP_URL = process.env.APP_URL ?? 'http://localhost:3010';
const OUT_DIR = process.env.OUT_DIR ?? 'C:\\Temp';

const results = [];
let failures = 0;

function record(name, ok, detail = '') {
    results.push({name, ok, detail});
    if (!ok) failures += 1;
    console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
}

async function openTarget() {
    // Chrome mới yêu cầu PUT cho /json/new
    for (const method of ['PUT', 'GET']) {
        const res = await fetch(`${CDP}/json/new?about:blank`, {method});
        if (res.ok) return res.json();
    }
    throw new Error('Không tạo được tab qua CDP (Chrome đã bật --remote-debugging-port chưa?)');
}

class Cdp {
    constructor(ws) {
        this.ws = ws;
        this.id = 0;
        this.pending = new Map();
        ws.addEventListener('message', (event) => {
            const message = JSON.parse(event.data);
            if (message.id && this.pending.has(message.id)) {
                const {resolve, reject} = this.pending.get(message.id);
                this.pending.delete(message.id);
                if (message.error) reject(new Error(message.error.message));
                else resolve(message.result);
            }
        });
    }

    static async connect(wsUrl) {
        const ws = new WebSocket(wsUrl);
        await new Promise((resolve, reject) => {
            ws.addEventListener('open', resolve, {once: true});
            ws.addEventListener('error', () => reject(new Error('CDP websocket error')), {once: true});
        });
        return new Cdp(ws);
    }

    send(method, params = {}) {
        this.id += 1;
        const id = this.id;
        return new Promise((resolve, reject) => {
            const timer = setTimeout(() => {
                this.pending.delete(id);
                reject(new Error(`CDP timeout: ${method}`));
            }, 20_000);
            this.pending.set(id, {
                resolve: (value) => {
                    clearTimeout(timer);
                    resolve(value);
                },
                reject: (error) => {
                    clearTimeout(timer);
                    reject(error);
                },
            });
            this.ws.send(JSON.stringify({id, method, params}));
        });
    }

    async eval(expression) {
        const result = await this.send('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
        if (result.exceptionDetails) {
            throw new Error(`JS error: ${result.exceptionDetails.text} ${result.result?.description ?? ''}`);
        }
        return result.result.value;
    }

    async screenshot(name) {
        const {data} = await this.send('Page.captureScreenshot', {format: 'png', captureBeyondViewport: true});
        const file = join(OUT_DIR, name);
        writeFileSync(file, Buffer.from(data, 'base64'));
        return file;
    }

    async pressEscape() {
        for (const type of ['keyDown', 'keyUp']) {
            await this.send('Input.dispatchKeyEvent', {
                type,
                key: 'Escape',
                code: 'Escape',
                windowsVirtualKeyCode: 27,
                nativeVirtualKeyCode: 27,
            });
        }
    }

    /** Chờ tới khi biểu thức JS trả truthy (poll 100ms). */
    async waitFor(expression, {timeout = 15_000, label = expression} = {}) {
        const start = Date.now();
        while (Date.now() - start < timeout) {
            if (await this.eval(expression)) return true;
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        throw new Error(`timeout chờ: ${label}`);
    }
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));


async function resolveCdp() {
    for (const candidate of CDP_CANDIDATES) {
        try {
            const res = await fetch(`${candidate}/json/version`, {signal: AbortSignal.timeout(2000)});
            if (res.ok) {
                CDP = candidate;
                return res.json();
            }
        } catch {
            // thử ứng viên kế tiếp
        }
    }
    throw new Error(`Không kết nối được CDP (đã thử: ${CDP_CANDIDATES.join(', ')})`);
}

async function main() {
    mkdirSync(OUT_DIR, {recursive: true});

    const version = await resolveCdp();
    console.log(`Chrome: ${version.Browser} (${CDP})`);

    const target = await openTarget();
    const cdp = await Cdp.connect(target.webSocketDebuggerUrl);

    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {width: 1440, height: 900, deviceScaleFactor: 1, mobile: false});

    // ---------- 1. Trang load được ----------
    await cdp.send('Page.navigate', {url: APP_URL});
    await cdp.waitFor("document.querySelector('header') && document.body.innerText.includes('Knowledge Base')", {
        label: 'trang chat render',
    });
    record('Trang load + header "Knowledge Base"', true);

    // ---------- 2. Chỉ còn MỘT nút "Kho tài liệu" (KB-4.9) ----------
    const docButtons = await cdp.eval(
        "[...document.querySelectorAll('button')].filter((b) => b.textContent.trim() === 'Kho tài liệu').length",
    );
    record('Chỉ có 1 nút "Kho tài liệu" (ở header)', docButtons === 1, `tìm thấy ${docButtons}`);

    // ---------- 3. Lịch sử chat persist qua reload (KB-4.9) ----------
    await cdp.eval(`
        localStorage.setItem('kb.chat_sessions', JSON.stringify({
            version: 1,
            currentSessionId: 's-verify',
            sessions: [{
                id: 's-verify',
                title: 'Kiểm tra F5',
                createdAt: new Date().toISOString(),
                messageCount: 2,
                conversationId: 'conv-verify',
                messages: [
                    {id: 'm1', role: 'user', content: 'Câu hỏi kiểm tra F5'},
                    {id: 'm2', role: 'assistant', content: 'Trả lời **giữ sau reload**'}
                ]
            }]
        }));
        true;
    `);
    await cdp.send('Page.reload');
    await sleep(900);
    await cdp.waitFor("document.body.innerText.includes('Câu hỏi kiểm tra F5')", {label: 'message sau reload'});
    record('F5 vẫn thấy hội thoại + tiêu đề session', await cdp.eval("document.body.innerText.includes('Kiểm tra F5')"));

    const markdownRendered = await cdp.eval(
        "!!document.querySelector('.md-body strong') && document.querySelector('.md-body strong').textContent.includes('giữ sau reload')",
    );
    record('Markdown câu trả lời render (<strong>)', markdownRendered);

    // ---------- 4. Theme toggle: light → dark + lưu localStorage ----------
    await cdp.eval("document.querySelector('header button[data-theme-mode]').click(); true;");
    await sleep(350);
    const lightState = await cdp.eval(
        "({dark: document.documentElement.classList.contains('dark'), stored: localStorage.getItem('kb.theme'), scheme: document.documentElement.style.colorScheme})",
    );
    record(
        'Theme: bấm lần 1 → light (bỏ .dark + lưu kb.theme)',
        lightState.stored === 'light' && lightState.dark === false,
        JSON.stringify(lightState),
    );
    await cdp.screenshot('kb-ui-light.png');

    await cdp.eval("document.querySelector('header button[data-theme-mode]').click(); true;");
    await sleep(350);
    const darkState = await cdp.eval(
        "({dark: document.documentElement.classList.contains('dark'), stored: localStorage.getItem('kb.theme'), scheme: document.documentElement.style.colorScheme})",
    );
    record(
        'Theme: bấm lần 2 → dark (.dark + color-scheme)',
        darkState.stored === 'dark' && darkState.dark === true && darkState.scheme === 'dark',
        JSON.stringify(darkState),
    );
    await cdp.screenshot('kb-ui-dark.png');

    // ---------- 5. Sheet Kho tài liệu: mở + ESC đóng (Radix Dialog) ----------
    await cdp.eval(
        "[...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Kho tài liệu').click(); true;",
    );
    await cdp.waitFor("!!document.querySelector('[data-slot=\"sheet-content\"]')", {label: 'sheet mở'});
    await sleep(600); // chờ animation slide-in xong rồi mới đo/chụp (nếu không sẽ bắt được cảnh đang trượt)
    // Radix Dialog: `role="dialog"` + `aria-labelledby` + focus trap (không set `aria-modal`, nó dùng
    // aria-hidden cho phần ngoài + focus guard). Kiểm đúng thứ có thực: role + focus nằm trong sheet.
    const sheetState = await cdp.eval(`(() => {
        const content = document.querySelector('[data-slot="sheet-content"]');
        return {
            role: content?.getAttribute('role'),
            labelledBy: content?.getAttribute('aria-labelledby'),
            focusInside: !!content && content.contains(document.activeElement),
        };
    })()`);
    record(
        'Sheet mở: role=dialog + aria-labelledby + focus nằm trong sheet',
        sheetState.role === 'dialog' && !!sheetState.labelledBy && sheetState.focusInside,
        JSON.stringify(sheetState),
    );
    await cdp.screenshot('kb-ui-sheet.png');

    await cdp.pressEscape();
    await sleep(600);
    record('ESC đóng được sheet', await cdp.eval("!document.querySelector('[data-slot=\"sheet-content\"]')"));

    // ---------- 6. Không tràn ngang ở 768px ----------
    await cdp.send('Emulation.setDeviceMetricsOverride', {width: 720, height: 900, deviceScaleFactor: 1, mobile: false});
    await sleep(500);
    record('720px không tràn ngang', await cdp.eval('document.documentElement.scrollWidth <= window.innerWidth + 1'));
    record(
        '720px sidebar thu gọn (dùng Sheet)',
        await cdp.eval("getComputedStyle(document.querySelector('aside')).display === 'none'"),
    );
    await cdp.screenshot('kb-ui-720.png');

    // dọn state test, không ảnh hưởng phiên thật của user
    await cdp.eval("localStorage.removeItem('kb.chat_sessions'); localStorage.removeItem('kb.theme'); true;");

    console.log(`\nScreenshots: C:\\Temp\\kb-ui-*.png`);
    console.log(failures === 0 ? `\nTẤT CẢ ${results.length} CHECK PASS` : `\n${failures}/${results.length} CHECK FAIL`);
    process.exit(failures === 0 ? 0 : 1);
}

main().catch((error) => {
    console.error('VERIFY ERROR:', error.message);
    process.exit(2);
});
