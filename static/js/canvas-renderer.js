/* canvas-renderer.js — client-side math equation renderers */

const MR = window.MR || {};

// ── Color helpers ────────────────────────────────────────────────────────────
MR.hexToRgb = (hex) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return [r, g, b];
};

MR.paramValue = (params, key, fallback = null) => {
  const value = params?.[key];
  if (value && typeof value === 'object' && 'value' in value) {
    return value.value ?? fallback;
  }
  return value ?? fallback;
};

MR.getBackground = (params, fallback = '#080808') =>
  MR.paramValue(params, 'background_color', fallback);

MR.fillBackground = (ctx, w, h, params, fallback = '#080808') => {
  ctx.fillStyle = MR.getBackground(params, fallback);
  ctx.fillRect(0, 0, w, h);
};

MR.lerpColor = (c1, c2, t) => {
  const a = MR.hexToRgb(c1), b = MR.hexToRgb(c2);
  return `rgb(${Math.round(a[0]+(b[0]-a[0])*t)},${Math.round(a[1]+(b[1]-a[1])*t)},${Math.round(a[2]+(b[2]-a[2])*t)})`;
};

// ── Lorenz attractor ─────────────────────────────────────────────────────────
MR.lorenz = {
  _state: null,
  _animId: null,

  init(canvas, params, animated = false) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const sigma = +params.sigma?.value ?? 10;
    const rho   = +params.rho?.value   ?? 28;
    const beta  = +params.beta?.value  ?? 2.667;
    const cs    = params.color_start?.value ?? '#c8a96e';
    const ce    = params.color_end?.value   ?? '#7ecfb3';

    MR.fillBackground(ctx, w, h, params);

    // Generate trail
    const N = animated ? 8000 : 30000;
    const dt = 0.005;
    let x = 0.1, y = 0, z = 0;
    const pts = [];
    for (let i = 0; i < N; i++) {
      const dx = sigma * (y - x);
      const dy = x * (rho - z) - y;
      const dz = x * y - beta * z;
      x += dx * dt; y += dy * dt; z += dz * dt;
      pts.push([x, y, z]);
    }

    // Project 3D → 2D (simple orthographic with slight rotation)
    const angle = animated ? (this._state?.angle || 0) : 0.4;
    const ca = Math.cos(angle), sa = Math.sin(angle);
    const projected = pts.map(([px, py, pz]) => {
      const rx = px * ca - pz * sa;
      const ry = py;
      return [rx, ry];
    });

    // Scale to canvas
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    projected.forEach(([px, py]) => {
      if (px < minX) minX = px; if (px > maxX) maxX = px;
      if (py < minY) minY = py; if (py > maxY) maxY = py;
    });
    const rangeX = maxX - minX, rangeY = maxY - minY;
    const scale = Math.min(w, h) * 0.85 / Math.max(rangeX, rangeY);
    const offX = (w - rangeX * scale) / 2;
    const offY = (h - rangeY * scale) / 2;

    // Draw
    for (let i = 1; i < projected.length; i++) {
      const t = i / projected.length;
      ctx.strokeStyle = MR.lerpColor(cs, ce, t);
      ctx.globalAlpha = 0.4 + t * 0.4;
      ctx.lineWidth = 0.5;
      ctx.beginPath();
      ctx.moveTo((projected[i-1][0] - minX) * scale + offX, (projected[i-1][1] - minY) * scale + offY);
      ctx.lineTo((projected[i  ][0] - minX) * scale + offX, (projected[i  ][1] - minY) * scale + offY);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  },

  animate(canvas, params) {
    if (this._animId) cancelAnimationFrame(this._animId);
    this._state = { angle: 0 };
    const tick = () => {
      this._state.angle += 0.003;
      // only redraw every 2 frames for perf
      this.init(canvas, params, true);
      this._animId = requestAnimationFrame(tick);
    };
    tick();
  },

  stop() {
    if (this._animId) { cancelAnimationFrame(this._animId); this._animId = null; }
  }
};

// ── Clifford attractor ───────────────────────────────────────────────────────
MR.clifford = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const a = +params.a?.value ?? -1.4;
    const b = +params.b?.value ??  1.6;
    const c = +params.c?.value ??  1.0;
    const d = +params.d?.value ??  0.7;
    const cs = params.color_start?.value ?? '#c8a96e';
    const ce = params.color_end?.value   ?? '#7ecfb3';

    const imgData = ctx.createImageData(w, h);
    const acc = new Float32Array(w * h);
    const N = 500000;
    let x = 0, y = 0;

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    const pts = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) {
      const nx = Math.sin(a * y) + c * Math.cos(a * x);
      const ny = Math.sin(b * x) + d * Math.cos(b * y);
      x = nx; y = ny;
      pts[i*2] = x; pts[i*2+1] = y;
      if (x < minX) minX = x; if (x > maxX) maxX = x;
      if (y < minY) minY = y; if (y > maxY) maxY = y;
    }

    const scaleX = (w - 2) / (maxX - minX);
    const scaleY = (h - 2) / (maxY - minY);
    for (let i = 0; i < N; i++) {
      const px = Math.floor((pts[i*2]   - minX) * scaleX);
      const py = Math.floor((pts[i*2+1] - minY) * scaleY);
      if (px >= 0 && px < w && py >= 0 && py < h) acc[py * w + px]++;
    }

    const maxVal = Math.max(...acc);
    const [r1,g1,b1] = MR.hexToRgb(cs);
    const [r2,g2,b2] = MR.hexToRgb(ce);
    for (let i = 0; i < w * h; i++) {
      const t = acc[i] > 0 ? Math.log1p(acc[i]) / Math.log1p(maxVal) : 0;
      const idx = i * 4;
      if (t > 0) {
        imgData.data[idx]   = Math.round(r1 + (r2-r1)*t);
        imgData.data[idx+1] = Math.round(g1 + (g2-g1)*t);
        imgData.data[idx+2] = Math.round(b1 + (b2-b1)*t);
        imgData.data[idx+3] = Math.round(t * 255);
      }
    }
    MR.fillBackground(ctx, w, h, params);
    ctx.putImageData(imgData, 0, 0);
  }
};

// ── Lissajous ────────────────────────────────────────────────────────────────
MR.lissajous = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const fx    = +params.fx?.value    ?? 3;
    const fy    = +params.fy?.value    ?? 4;
    const delta = +params.delta?.value ?? 1.5708;
    const cs    = params.color_start?.value ?? '#c8a96e';
    const ce    = params.color_end?.value   ?? '#f0ece0';

    MR.fillBackground(ctx, w, h, params);

    const N = 3000;
    const margin = 30;
    ctx.lineWidth = 1.2;
    for (let i = 0; i < N - 1; i++) {
      const t1 = (i   / N) * 2 * Math.PI;
      const t2 = ((i+1) / N) * 2 * Math.PI;
      const x1 = (Math.sin(fx * t1 + delta) + 1) / 2 * (w - margin*2) + margin;
      const y1 = (Math.sin(fy * t1)          + 1) / 2 * (h - margin*2) + margin;
      const x2 = (Math.sin(fx * t2 + delta) + 1) / 2 * (w - margin*2) + margin;
      const y2 = (Math.sin(fy * t2)          + 1) / 2 * (h - margin*2) + margin;
      ctx.strokeStyle = MR.lerpColor(cs, ce, i / N);
      ctx.globalAlpha = 0.7;
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }
};

// Radial Symmetry: rose curves
MR.rose = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const petals = +MR.paramValue(params, 'petals', 7.0);
    const phase = +MR.paramValue(params, 'phase', 0.0);
    const power = +MR.paramValue(params, 'power', 1.0);
    const turns = +MR.paramValue(params, 'turns', 24.0);
    const petalMix = +MR.paramValue(params, 'petal_mix', 0.16);
    const radialMix = +MR.paramValue(params, 'radial_mix', 0.18);
    const radialFreq = +MR.paramValue(params, 'radial_freq', Math.max(3.0, petals * 0.55));
    const phaseDrift = +MR.paramValue(params, 'phase_drift', 0.42);
    const twist = +MR.paramValue(params, 'twist', Math.max(2.0, petals / 2.0));
    const echoLayers = Math.max(2, Math.min(6, Math.round(+MR.paramValue(params, 'echo_layers', 3))));
    const cs = MR.paramValue(params, 'color_start', '#c8a96e');
    const ce = MR.paramValue(params, 'color_end', '#f0ece0');

    MR.fillBackground(ctx, w, h, params);
    const n = 3400;
    const radius = Math.min(w, h) * 0.42;
    const cx = w / 2, cy = h / 2;
    const baseWidth = Math.max(0.8, Math.min(w, h) / 520);
    const layers = [];
    let maxExtent = 1;

    for (let layer = 0; layer < echoLayers; layer++) {
      const layerPhase = phase + layer * 0.34;
      const layerScale = 1.0 - layer * 0.08;
      const pts = [];
      for (let i = 0; i < n; i++) {
        const theta = i / (n - 1) * Math.PI * turns + layer * 0.028 * Math.PI;
        const base = Math.cos(
          (petals + 0.18 * layer) * theta
          + layerPhase
          + phaseDrift * Math.sin(theta * (twist + layer * 0.15))
        );
        const signed = Math.sign(base) * Math.pow(Math.max(Math.abs(base), 1e-6), power + layer * 0.03);
        const harmonic = petalMix * Math.sin((petals * (1.45 + 0.04 * layer) + 1.0) * theta - layerPhase * 0.6);
        const envelope = 1.0 + radialMix * Math.cos((radialFreq + layer * 0.85) * theta + layerPhase * 0.45);
        const drift = 0.08 * petalMix * Math.cos(theta * (0.5 + 0.04 * layer) + layer * 0.7);
        const r = ((0.86 * signed) + harmonic + drift) * envelope * layerScale;
        const x = Math.cos(theta) * r;
        const y = Math.sin(theta) * r;
        maxExtent = Math.max(maxExtent, Math.abs(x), Math.abs(y));
        pts.push([x, y]);
      }
      layers.push(pts);
    }

    const scale = radius / (maxExtent * 1.06);
    layers.reverse().forEach((pts, layerIdx) => {
      ctx.globalAlpha = Math.min(0.88, 0.24 + layerIdx * 0.16);
      ctx.lineWidth = baseWidth * (1.36 - layerIdx * 0.08);
      for (let i = 1; i < pts.length; i++) {
        const [x1, y1] = pts[i - 1];
        const [x2, y2] = pts[i];
        ctx.strokeStyle = MR.lerpColor(cs, ce, i / pts.length);
        ctx.beginPath();
        ctx.moveTo(cx + x1 * scale, cy + y1 * scale);
        ctx.lineTo(cx + x2 * scale, cy + y2 * scale);
        ctx.stroke();
      }
    });
    ctx.globalAlpha = 1;
  }
};

// Radial Symmetry: superformula blooms
MR.superformula = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const m = +MR.paramValue(params, 'm', 7.0);
    const n1 = +MR.paramValue(params, 'n1', 0.3);
    const n2 = +MR.paramValue(params, 'n2', 1.7);
    const n3 = +MR.paramValue(params, 'n3', 1.7);
    const turns = +MR.paramValue(params, 'turns', 12.0);
    const scaleBias = +MR.paramValue(params, 'scale_bias', 1.0);
    const waveDepth = +MR.paramValue(params, 'wave_depth', 0.32);
    const waveFreq = +MR.paramValue(params, 'wave_freq', Math.max(4.0, m * 0.75));
    const phaseDrift = +MR.paramValue(params, 'phase_drift', 0.38);
    const orbitMix = +MR.paramValue(params, 'orbit_mix', 0.12);
    const echoLayers = Math.max(2, Math.min(6, Math.round(+MR.paramValue(params, 'echo_layers', 4))));
    const cs = MR.paramValue(params, 'color_start', '#c8a96e');
    const ce = MR.paramValue(params, 'color_end', '#7ecfb3');

    MR.fillBackground(ctx, w, h, params);
    const n = 3600;
    const radius = Math.min(w, h) * 0.42;
    const cx = w / 2, cy = h / 2;
    const baseWidth = Math.max(0.8, Math.min(w, h) / 520);
    const layers = [];
    let maxExtent = 1;

    for (let layer = 0; layer < echoLayers; layer++) {
      const layerPhase = layer * 0.28 * Math.PI;
      const layerScale = 1.0 - layer * 0.07;
      const pts = [];
      for (let i = 0; i < n; i++) {
        const theta = i / (n - 1) * Math.PI * turns + layer * 0.02 * Math.PI;
        const localM = m + 0.25 * layer;
        const drift = phaseDrift * Math.sin(theta * (0.35 + 0.03 * layer));
        const cosTerm = Math.abs(Math.cos(localM * theta / 4 + layerPhase + drift));
        const sinTerm = Math.abs(Math.sin(localM * theta / 4 - layerPhase));
        const n2Eff = Math.max(0.12, n2 * (1.0 + 0.28 * waveDepth * Math.cos(theta * (waveFreq + layer * 0.65) + layerPhase)));
        const n3Eff = Math.max(0.12, n3 * (1.0 + 0.28 * waveDepth * Math.sin(theta * (waveFreq * 0.82 + layer * 0.45) - layerPhase * 0.5)));
        const base = Math.pow(cosTerm, n2Eff) + Math.pow(sinTerm, n3Eff);
        let r = Math.pow(Math.max(base, 1e-6), -1 / Math.max(n1 * (1.0 + 0.05 * layer), 1e-3));
        r = Math.pow(r, 0.92) * scaleBias;
        const breathing = 1.0 + 0.18 * waveDepth * Math.cos(theta * (waveFreq * 0.55 + 1.0 + layer * 0.2) + layerPhase);
        const orbit = orbitMix * 0.22 * Math.sin((m * 0.5 + 2.0 + layer * 0.25) * theta + layerPhase * 0.7);
        const resonance = 0.14 * waveDepth * Math.sin((localM * 1.35 + waveFreq + layer * 0.35) * theta - layerPhase * 0.6);
        const fold = orbitMix * 0.08 * Math.cos((waveFreq * 0.5 + 1.5) * theta + layerPhase);
        r = (r * breathing + orbit + resonance + fold) * layerScale;
        const x = Math.cos(theta) * r;
        const y = Math.sin(theta) * r;
        maxExtent = Math.max(maxExtent, Math.abs(x), Math.abs(y));
        pts.push([x, y]);
      }
      layers.push(pts);
    }

    const scale = radius / (maxExtent * 1.08);
    layers.reverse().forEach((pts, layerIdx) => {
      ctx.globalAlpha = Math.min(0.9, 0.22 + layerIdx * 0.15);
      ctx.lineWidth = baseWidth * (1.42 - layerIdx * 0.09);
      for (let i = 1; i < pts.length; i++) {
        const [x1, y1] = pts[i - 1];
        const [x2, y2] = pts[i];
        ctx.strokeStyle = MR.lerpColor(cs, ce, i / pts.length);
        ctx.beginPath();
        ctx.moveTo(cx + x1 * scale, cy + y1 * scale);
        ctx.lineTo(cx + x2 * scale, cy + y2 * scale);
        ctx.stroke();
      }
    });
    ctx.globalAlpha = 1;
  }
};

// ── Harmonograph ─────────────────────────────────────────────────────────────
MR.harmonograph = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const f1 = +params.f1?.value ?? 2;
    const f2 = +params.f2?.value ?? 3;
    const ph = +params.p?.value  ?? 0.5;
    const dc = +params.d?.value  ?? 0.002;
    const cs = params.color_start?.value ?? '#c8a96e';
    const ce = params.color_end?.value   ?? '#7ecfb3';

    MR.fillBackground(ctx, w, h, params);

    const tMax = 60 * Math.PI;
    const steps = 80000;
    const dt = tMax / steps;
    ctx.lineWidth = 0.6;
    ctx.beginPath();
    let prevX, prevY;
    for (let i = 0; i < steps; i++) {
      const t = i * dt;
      const decay = Math.exp(-dc * t);
      const x = Math.sin(f1 * t + ph) * decay;
      const y = Math.sin(f2 * t) * decay;
      const px = (x + 1) / 2 * (w - 40) + 20;
      const py = (y + 1) / 2 * (h - 40) + 20;
      if (i === 0) { ctx.moveTo(px, py); }
      else {
        ctx.strokeStyle = MR.lerpColor(cs, ce, i / steps);
        ctx.globalAlpha = decay * 0.8;
        ctx.beginPath();
        ctx.moveTo(prevX, prevY);
        ctx.lineTo(px, py);
        ctx.stroke();
      }
      prevX = px; prevY = py;
    }
    ctx.globalAlpha = 1;
  }
};

// ── Julia set ────────────────────────────────────────────────────────────────
MR.julia = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const cx       = +params.cx?.value       ?? -0.7;
    const cy       = +params.cy?.value       ??  0.27;
    const zoom     = +params.zoom?.value     ??  1.0;
    const maxIter  = +params.max_iter?.value ?? 128;
    const cs = params.color_start?.value ?? '#c8a96e';
    const ce = params.color_end?.value   ?? '#080808';
    const bg = MR.getBackground(params);

    const imgData = ctx.createImageData(w, h);
    const [r1,g1,b1] = MR.hexToRgb(cs);
    const [r2,g2,b2] = MR.hexToRgb(ce);
    const [rb,gb,bb] = MR.hexToRgb(bg);

    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        let zx = (px / w - 0.5) * 4 / zoom;
        let zy = (py / h - 0.5) * 4 / zoom;
        let iter = 0;
        while (zx*zx + zy*zy < 4 && iter < maxIter) {
          const tmp = zx*zx - zy*zy + cx;
          zy = 2 * zx * zy + cy;
          zx = tmp;
          iter++;
        }
        const t = iter / maxIter;
        const idx = (py * w + px) * 4;
        if (iter >= maxIter) {
          imgData.data[idx]   = rb;
          imgData.data[idx+1] = gb;
          imgData.data[idx+2] = bb;
        } else {
          imgData.data[idx]   = Math.round(r1 + (r2-r1)*t);
          imgData.data[idx+1] = Math.round(g1 + (g2-g1)*t);
          imgData.data[idx+2] = Math.round(b1 + (b2-b1)*t);
        }
        imgData.data[idx+3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }
};

// ── Mandelbrot ───────────────────────────────────────────────────────────────
MR.mandelbrot = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const centerX = +params.cx?.value      ?? -0.5;
    const centerY = +params.cy?.value      ??  0.0;
    const zoom    = +params.zoom?.value    ??  1.0;
    const maxIter = +params.max_iter?.value ?? 128;
    const cs = params.color_start?.value ?? '#c8a96e';
    const ce = params.color_end?.value   ?? '#080808';
    const bg = MR.getBackground(params);

    const imgData = ctx.createImageData(w, h);
    const [r1,g1,b1] = MR.hexToRgb(cs);
    const [r2,g2,b2] = MR.hexToRgb(ce);
    const [rb,gb,bb] = MR.hexToRgb(bg);
    const scale = 4 / zoom;

    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        const c0 = centerX + (px / w - 0.5) * scale;
        const c1 = centerY + (py / h - 0.5) * scale;
        let zx = 0, zy = 0, iter = 0;
        while (zx*zx + zy*zy < 4 && iter < maxIter) {
          const tmp = zx*zx - zy*zy + c0;
          zy = 2*zx*zy + c1;
          zx = tmp;
          iter++;
        }
        const t = iter / maxIter;
        const idx = (py * w + px) * 4;
        if (iter >= maxIter) {
          imgData.data[idx]   = rb;
          imgData.data[idx+1] = gb;
          imgData.data[idx+2] = bb;
        } else {
          imgData.data[idx]   = Math.round(r1 + (r2-r1)*t);
          imgData.data[idx+1] = Math.round(g1 + (g2-g1)*t);
          imgData.data[idx+2] = Math.round(b1 + (b2-b1)*t);
        }
        imgData.data[idx+3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }
};

// ── Gray-Scott (fast JS approximation) ──────────────────────────────────────
MR.grayscott = {
  render(canvas, params) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const f  = +params.f?.value  ?? 0.055;
    const k  = +params.k?.value  ?? 0.062;
    const Du = +params.Du?.value ?? 0.16;
    const Dv = +params.Dv?.value ?? 0.08;
    const cs = params.color_start?.value ?? '#c8a96e';
    const ce = params.color_end?.value   ?? '#7ecfb3';

    const size = Math.min(w, h, 128);
    const u = new Float32Array(size * size).fill(1);
    const v = new Float32Array(size * size);
    const mid = size >> 1;
    for (let y = mid-5; y < mid+5; y++)
      for (let x = mid-5; x < mid+5; x++) {
        u[y*size+x] = 0.5 + (Math.random()-0.5)*0.1;
        v[y*size+x] = 0.25 + (Math.random()-0.5)*0.1;
      }

    const nu = new Float32Array(size * size);
    const nv = new Float32Array(size * size);

    for (let step = 0; step < 1500; step++) {
      for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
          const i = y * size + x;
          const up = ((y-1+size)%size)*size + x;
          const dn = ((y+1)%size)*size + x;
          const lt = y*size + (x-1+size)%size;
          const rt = y*size + (x+1)%size;
          const lapu = u[up]+u[dn]+u[lt]+u[rt] - 4*u[i];
          const lapv = v[up]+v[dn]+v[lt]+v[rt] - 4*v[i];
          const uvv = u[i]*v[i]*v[i];
          nu[i] = u[i] + Du*lapu - uvv + f*(1-u[i]);
          nv[i] = v[i] + Dv*lapv + uvv - (f+k)*v[i];
        }
      }
      u.set(nu); v.set(nv);
    }

    const imgData = ctx.createImageData(w, h);
    const [r1,g1,b1] = MR.hexToRgb(cs);
    const [r2,g2,b2] = MR.hexToRgb(ce);
    for (let py = 0; py < h; py++) {
      for (let px = 0; px < w; px++) {
        const sx = Math.floor(px / w * size);
        const sy = Math.floor(py / h * size);
        const t = Math.min(1, Math.max(0, v[sy * size + sx] * 4));
        const idx = (py * w + px) * 4;
        imgData.data[idx]   = Math.round(r1 + (r2-r1)*t);
        imgData.data[idx+1] = Math.round(g1 + (g2-g1)*t);
        imgData.data[idx+2] = Math.round(b1 + (b2-b1)*t);
        imgData.data[idx+3] = 255;
      }
    }
    ctx.putImageData(imgData, 0, 0);
  }
};

// ── De Jong attractor ──────────────────────────────────────────────────────────
MR.dejong = {
  render(canvas, params, maxPts = 600000, isAnim = false) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width, h = canvas.height;
    const a = +MR.paramValue(params, 'a', -2.0);
    const b = +MR.paramValue(params, 'b', -2.0);
    const c = +MR.paramValue(params, 'c', 2.0);
    const d = +MR.paramValue(params, 'd', -2.0);
    const cs = MR.paramValue(params, 'color_start', '#c8a96e');
    const ce = MR.paramValue(params, 'color_end',   '#7ecfb3');

    if (!canvas._djState || !isAnim) {
      MR.fillBackground(ctx, w, h, params);
      canvas._djState = {
        acc: new Float32Array(w * h),
        x: 0.1, y: 0.1,
        minX: Infinity, maxX: -Infinity,
        minY: Infinity, maxY: -Infinity
      };
      
      let tx = 0.1, ty = 0.1;
      for (let i = 0; i < 50000; i++) {
        const nx = Math.sin(a * ty) - Math.cos(b * tx);
        const ny = Math.sin(c * tx) - Math.cos(d * ty);
        tx = nx; ty = ny;
        if (tx < canvas._djState.minX) canvas._djState.minX = tx; 
        if (tx > canvas._djState.maxX) canvas._djState.maxX = tx;
        if (ty < canvas._djState.minY) canvas._djState.minY = ty; 
        if (ty > canvas._djState.maxY) canvas._djState.maxY = ty;
      }
      const rangeX = canvas._djState.maxX - canvas._djState.minX;
      const rangeY = canvas._djState.maxY - canvas._djState.minY;
      canvas._djState.scale = Math.min((w - 2) / rangeX, (h - 2) / rangeY);
      canvas._djState.offX = (w - rangeX * canvas._djState.scale) / 2;
      canvas._djState.offY = (h - rangeY * canvas._djState.scale) / 2;
    }

    const st = canvas._djState;

    for (let i = 0; i < maxPts; i++) {
      const nx = Math.sin(a * st.y) - Math.cos(b * st.x);
      const ny = Math.sin(c * st.x) - Math.cos(d * st.y);
      st.x = nx; st.y = ny;
      
      const px = Math.floor((st.x - st.minX) * st.scale + st.offX);
      const py = Math.floor((st.y - st.minY) * st.scale + st.offY);
      if (px >= 0 && px < w && py >= 0 && py < h) {
        st.acc[py * w + px]++;
      }
    }

    let maxVal = 0;
    for (let i = 0; i < st.acc.length; i++) if (st.acc[i] > maxVal) maxVal = st.acc[i];
    if (maxVal === 0) return;
    const logMax = Math.log1p(maxVal);

    const imgData = ctx.createImageData(w, h);
    const [r1,g1,b1] = MR.hexToRgb(cs);
    const [r2,g2,b2] = MR.hexToRgb(ce);
    const bgStr = MR.getBackground(params);
    const [rb,gb,bb] = MR.hexToRgb(bgStr);
    
    for (let i = 0; i < w * h; i++) {
      const idx = i * 4;
      if (st.acc[i] === 0) {
        imgData.data[idx] = rb; imgData.data[idx+1] = gb; imgData.data[idx+2] = bb; imgData.data[idx+3] = 255;
        continue;
      }
      const t = Math.pow(Math.log1p(st.acc[i]) / logMax, 0.6);
      imgData.data[idx]   = Math.round(r1 + (r2-r1)*t);
      imgData.data[idx+1] = Math.round(g1 + (g2-g1)*t);
      imgData.data[idx+2] = Math.round(b1 + (b2-b1)*t);
      imgData.data[idx+3] = 255;
    }
    ctx.putImageData(imgData, 0, 0);
  },

  animate(canvas, params) {
    if (canvas._djAnimId) cancelAnimationFrame(canvas._djAnimId);
    let ptsRendered = 0;
    const ptsPerFrame = 15000;
    const totalPts = 2000000;
    
    this.render(canvas, params, 0, false); 
    
    const tick = () => {
      if (ptsRendered < totalPts) {
        this.render(canvas, params, ptsPerFrame, true);
        ptsRendered += ptsPerFrame;
        canvas._djAnimId = requestAnimationFrame(tick);
      }
    };
    tick();
  },

  stop(canvas) {
    if (canvas && canvas._djAnimId) { 
      cancelAnimationFrame(canvas._djAnimId); 
      canvas._djAnimId = null; 
    }
  }
};

// ── Flow Field ───────────────────────────────────────────────────────────────
MR.flowfield = {
  render(canvas, params) {
    const ctx  = canvas.getContext('2d');
    const W    = canvas.width, H = canvas.height;
    const cs   = params?.color_start?.value ?? '#5b9bd5';
    const ce   = params?.color_end?.value   ?? '#1e3a5f';
    const scl  = +(params?.noise_scale?.value ?? 5.0);
    // Cap particles/steps for JS — server handles full-res
    const nPts = Math.min(+(params?.n_particles?.value ?? 1800), 700);
    const nStp = Math.min(+(params?.n_steps?.value     ?? 120),  80);
    const ss   = +(params?.step_size?.value ?? 0.004);
    const seed = +(params?.seed?.value      ?? 7);

    MR.fillBackground(ctx, W, H, params);

    // Seedable pseudo-random (mulberry32)
    let s = (seed * 1664525 + 1013904223) | 0;
    const rand = () => {
      s = (Math.imul(s ^ (s >>> 16), 0x45d9f3b) ^ (s >>> 11)) | 0;
      return (s >>> 0) / 0xFFFFFFFF;
    };

    // Low-res angle grid + bilinear lookup
    const COLS = Math.max(Math.round(W / (scl * 8)), 3);
    const ROWS = Math.max(Math.round(H / (scl * 8)), 3);
    const grid = new Float32Array(COLS * ROWS);
    for (let i = 0; i < grid.length; i++) grid[i] = rand() * Math.PI * 2;

    const getAngle = (nx, ny) => {
      const gx = Math.max(0, Math.min(nx, 0.9999)) * (COLS - 1);
      const gy = Math.max(0, Math.min(ny, 0.9999)) * (ROWS - 1);
      const cx = gx | 0, cy = gy | 0;
      const fx = gx - cx, fy = gy - cy;
      return grid[cy       * COLS + cx    ] * (1-fx)*(1-fy)
           + grid[cy       * COLS + cx + 1] * fx    *(1-fy)
           + grid[(cy + 1) * COLS + cx    ] * (1-fx)* fy
           + grid[(cy + 1) * COLS + cx + 1] * fx    * fy;
    };

    const hex2rgb = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
    const [r0,g0,b0] = hex2rgb(cs), [r1,g1,b1] = hex2rgb(ce);
    const alpha = Math.max(0.04, Math.min(0.28, 500 / (nPts * Math.pow(nStp, 0.35))));

    const px = new Float32Array(nPts), py = new Float32Array(nPts);
    for (let i = 0; i < nPts; i++) { px[i] = rand(); py[i] = rand(); }

    // Draw one path per step — avoids giant accumulated paths
    ctx.lineWidth = 0.8;
    for (let step = 0; step < nStp; step++) {
      const t = step / (nStp - 1);
      const r = (r0 + (r1-r0)*t) | 0;
      const g = (g0 + (g1-g0)*t) | 0;
      const b = (b0 + (b1-b0)*t) | 0;
      ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
      ctx.beginPath();
      for (let i = 0; i < nPts; i++) {
        const angle = getAngle(px[i], py[i]);
        const x0 = px[i] * W, y0 = py[i] * H;
        px[i] += Math.cos(angle) * ss;
        py[i] += Math.sin(angle) * ss;
        ctx.moveTo(x0, y0);
        ctx.lineTo(px[i] * W, py[i] * H);
      }
      ctx.stroke();
    }
  },

  animate(canvas, params) {
    if (canvas._ffAnimId) cancelAnimationFrame(canvas._ffAnimId);
    
    const ctx  = canvas.getContext('2d');
    const W    = canvas.width, H = canvas.height;
    const cs   = params?.color_start?.value ?? '#5b9bd5';
    const ce   = params?.color_end?.value   ?? '#1e3a5f';
    const scl  = +(params?.noise_scale?.value ?? 5.0);
    const nPts = 3500; // More particles for animation
    const ss   = +(params?.step_size?.value ?? 0.0035);
    const seed = +(params?.seed?.value      ?? 7);

    MR.fillBackground(ctx, W, H, params);
    
    const bgStr = MR.getBackground(params, '#080808');
    const [br, bg, bb] = MR.hexToRgb(bgStr);
    const fadeStyle = `rgba(${br},${bg},${bb},0.08)`;

    let s = (seed * 1664525 + 1013904223) | 0;
    const rand = () => {
      s = (Math.imul(s ^ (s >>> 16), 0x45d9f3b) ^ (s >>> 11)) | 0;
      return (s >>> 0) / 0xFFFFFFFF;
    };

    const COLS = Math.max(Math.round(W / (scl * 8)), 3);
    const ROWS = Math.max(Math.round(H / (scl * 8)), 3);
    const grid = new Float32Array(COLS * ROWS);
    for (let i = 0; i < grid.length; i++) grid[i] = rand() * Math.PI * 2;

    const getAngle = (nx, ny) => {
      const gx = Math.max(0, Math.min(nx, 0.9999)) * (COLS - 1);
      const gy = Math.max(0, Math.min(ny, 0.9999)) * (ROWS - 1);
      const cx = gx | 0, cy = gy | 0;
      const fx = gx - cx, fy = gy - cy;
      return grid[cy       * COLS + cx    ] * (1-fx)*(1-fy)
           + grid[cy       * COLS + cx + 1] * fx    *(1-fy)
           + grid[(cy + 1) * COLS + cx    ] * (1-fx)* fy
           + grid[(cy + 1) * COLS + cx + 1] * fx    * fy;
    };

    const hex2rgb = h => [parseInt(h.slice(1,3),16), parseInt(h.slice(3,5),16), parseInt(h.slice(5,7),16)];
    const [r0,g0,b0] = hex2rgb(cs), [r1,g1,b1] = hex2rgb(ce);

    const px = new Float32Array(nPts), py = new Float32Array(nPts), ages = new Float32Array(nPts);
    for (let i = 0; i < nPts; i++) { 
      px[i] = rand(); py[i] = rand(); ages[i] = rand(); 
    }

    let globalTick = 0;
    ctx.lineWidth = 1.2;

    const tick = () => {
      globalTick++;
      
      // Fade previous frames
      ctx.fillStyle = fadeStyle;
      ctx.fillRect(0, 0, W, H);
      
      const t = (Math.sin(globalTick * 0.005) + 1) / 2;
      const r = (r0 + (r1-r0)*t) | 0;
      const g = (g0 + (g1-g0)*t) | 0;
      const b = (b0 + (b1-b0)*t) | 0;
      
      ctx.strokeStyle = `rgba(${r},${g},${b},0.8)`;
      ctx.beginPath();
      
      // Shift grid slowly over time for dynamic wind
      const driftAngle = globalTick * 0.001;
      
      for (let i = 0; i < nPts; i++) {
        const angle = getAngle(px[i], py[i]) + driftAngle;
        const x0 = px[i] * W, y0 = py[i] * H;
        
        px[i] += Math.cos(angle) * ss;
        py[i] += Math.sin(angle) * ss;
        ages[i] += 0.01;
        
        // Draw segment
        ctx.moveTo(x0, y0);
        ctx.lineTo(px[i] * W, py[i] * H);
        
        // Reset if offscreen or too old
        if (px[i] < 0 || px[i] > 1 || py[i] < 0 || py[i] > 1 || ages[i] > 1) {
          px[i] = rand(); py[i] = rand(); ages[i] = 0;
        }
      }
      ctx.stroke();
      
      canvas._ffAnimId = requestAnimationFrame(tick);
    };
    tick();
  },

  stop(canvas) {
    if (canvas && canvas._ffAnimId) { 
      cancelAnimationFrame(canvas._ffAnimId); 
      canvas._ffAnimId = null; 
    }
  }
};

// ── Dispatcher: render any canvas with data-eq attribute ─────────────────────
MR.renderCanvas = function(canvas, eq, params) {
  if (!canvas || !canvas.getContext) return;
  const w = canvas.offsetWidth || canvas.width;
  const h = canvas.offsetHeight || canvas.height;
  canvas.width = w; canvas.height = h;

  const ctx = canvas.getContext('2d');
  MR.fillBackground(ctx, w, h, params);

  const render = () => {
    switch (eq) {
      case 'lorenz':       MR.lorenz.init(canvas, params); break;
      case 'clifford':
      case 'aizawa':       MR.clifford.render(canvas, params); break;
      case 'de_jong':
      case 'de-jong':
      case 'de-jong-attractors': MR.dejong.render(canvas, params); break;
      case 'grayscott':
      case 'gray-scott':   MR.grayscott.render(canvas, params); break;
      case 'lissajous':    MR.lissajous.render(canvas, params); break;
      case 'harmonograph': MR.harmonograph.render(canvas, params); break;
      case 'rose':         MR.rose.render(canvas, params); break;
      case 'superformula': MR.superformula.render(canvas, params); break;
      case 'julia':        MR.julia.render(canvas, params); break;
      case 'mandelbrot':   MR.mandelbrot.render(canvas, params); break;
      case 'flowfield':    MR.flowfield.render(canvas, params); break;
      default:
        ctx.fillStyle = MR.getBackground(params, '#1e1e1e');
        ctx.fillRect(0, 0, w, h);
    }
  };

  // Use setTimeout so the browser can paint first
  setTimeout(render, 10);
};

window.MR = MR;
