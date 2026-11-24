#!/usr/bin/env node
/**
 * Deterministic 1080x1080 @ 30fps Chrome CDP (--remote-debugging-pipe) -> FFmpeg H.264 MP4 renderer.
 * Zero TCP ports required, runs 100% locally.
 */
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FFMPEG = '/Users/mac/.local/lib/python3.13/site-packages/static_ffmpeg/bin/darwin/ffmpeg';
const HTML_URL = 'file:///Users/mac/gemini-neon-promo/index.html?render=1';
const AUDIO_WAV = '/Users/mac/gemini-neon-promo/output/soundtrack.wav';
const OUT_MP4 = '/Users/mac/gemini-neon-promo/output/gemini-neon-promo-1080x1080.mp4';
const VERIFY_DIR = '/Users/mac/gemini-neon-promo/output/verify_frames';

const FPS = 30;
const TOTAL_FRAMES = 420; // 14.0s
const KEYFRAMES = new Set([18, 72, 132, 150, 210, 255, 298, 336, 408]);

fs.mkdirSync(VERIFY_DIR, { recursive: true });
fs.rmSync('/tmp/chrome-neon-cdp', { recursive: true, force: true });

class PipeCDP {
  constructor(chromeProc) {
    this.w = chromeProc.stdio[3];
    this.r = chromeProc.stdio[4];
    this.nextId = 1;
    this.pending = new Map();
    this.buf = Buffer.alloc(0);

    this.r.on('data', (chunk) => {
      this.buf = Buffer.concat([this.buf, chunk]);
      let nul;
      while ((nul = this.buf.indexOf(0)) !== -1) {
        const msgStr = this.buf.subarray(0, nul).toString('utf8');
        this.buf = this.buf.subarray(nul + 1);
        if (!msgStr) continue;
        const msg = JSON.parse(msgStr);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          if (msg.error) reject(new Error(`${msg.error.code}: ${msg.error.message}`));
          else resolve(msg.result);
        }
      }
    });
  }

  send(method, params = {}, sessionId = undefined) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.w.write(JSON.stringify(payload) + '\0');
    });
  }
}

async function main() {
  const t0 = Date.now();
  const chrome = spawn(CHROME, [
    '--headless=new',
    '--remote-debugging-pipe',
    '--no-sandbox',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--hide-scrollbars',
    '--mute-audio',
    '--force-device-scale-factor=1',
    '--window-size=1080,1080',
    '--user-data-dir=/tmp/chrome-neon-cdp',
    'about:blank',
  ], {
    stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'],
  });

  const cdp = new PipeCDP(chrome);

  try {
    const { targetInfos } = await cdp.send('Target.getTargets');
    let pageTarget = targetInfos.find((t) => t.type === 'page');
    if (!pageTarget) {
      const created = await cdp.send('Target.createTarget', { url: 'about:blank' });
      pageTarget = { targetId: created.targetId };
    }
    const { sessionId } = await cdp.send('Target.attachToTarget', {
      targetId: pageTarget.targetId,
      flatten: true,
    });

    await cdp.send('Page.enable', {}, sessionId);
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1080,
      height: 1080,
      deviceScaleFactor: 1,
      mobile: false,
    }, sessionId);

    await cdp.send('Page.navigate', { url: HTML_URL }, sessionId);

    // Wait for fonts + scene ready
    for (let attempt = 0; attempt < 200; attempt++) {
      const res = await cdp.send('Runtime.evaluate', {
        expression: 'Boolean(window.__ready)',
        returnByValue: true,
      }, sessionId);
      if (res?.result?.value === true) break;
      await new Promise((r) => setTimeout(r, 50));
    }

    // Spawn FFmpeg accepting raw PNG stream + synthesized WAV soundtrack
    const ffmpegArgs = [
      '-y',
      '-f', 'image2pipe',
      '-vcodec', 'png',
      '-r', String(FPS),
      '-i', 'pipe:0',
      '-i', AUDIO_WAV,
      '-map', '0:v:0',
      '-map', '1:a:0',
      '-c:v', 'libx264',
      '-preset', 'medium',
      '-crf', '16',
      '-pix_fmt', 'yuv420p',
      '-c:a', 'aac',
      '-b:a', '192k',
      '-ar', '48000',
      '-movflags', '+faststart',
      '-shortest',
      OUT_MP4,
    ];
    const ff = spawn(FFMPEG, ffmpegArgs, { stdio: ['pipe', 'ignore', 'pipe'] });
    let ffErr = '';
    ff.stderr.on('data', (d) => { ffErr += d.toString(); });

    const writeToFFmpeg = (buf) => new Promise((resolve, reject) => {
      if (!ff.stdin.write(buf)) ff.stdin.once('drain', resolve);
      else resolve();
    });

    for (let f = 0; f < TOTAL_FRAMES; f++) {
      await cdp.send('Runtime.evaluate', {
        expression: `window.setFrame(${f}); new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))`,
        awaitPromise: true,
      }, sessionId);

      const { data } = await cdp.send('Page.captureScreenshot', {
        format: 'png',
        clip: { x: 0, y: 0, width: 1080, height: 1080, scale: 1 },
      }, sessionId);

      const pngBuf = Buffer.from(data, 'base64');
      if (KEYFRAMES.has(f)) {
        fs.writeFileSync(path.join(VERIFY_DIR, `frame_${String(f).padStart(3, '0')}.png`), pngBuf);
      }
      await writeToFFmpeg(pngBuf);

      if ((f + 1) % 60 === 0 || f === TOTAL_FRAMES - 1) {
        const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
        console.log(`Rendered ${f + 1}/${TOTAL_FRAMES} frames (${elapsed}s)`);
      }
    }

    ff.stdin.end();
    await new Promise((resolve, reject) => {
      ff.on('close', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`ffmpeg exited ${code}: ${ffErr.slice(-800)}`));
      });
    });

    console.log(`Done! Output: ${OUT_MP4} in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
  } finally {
    chrome.kill('SIGTERM');
    await new Promise((r) => setTimeout(r, 250));
    try { fs.rmSync('/tmp/chrome-neon-cdp', { recursive: true, force: true }); } catch {}
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
