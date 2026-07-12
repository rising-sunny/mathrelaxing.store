/* main.js — home page initialisation */

document.addEventListener('DOMContentLoaded', () => {

  // ── Hero Lorenz animation ────────────────────────────────────────────────
  const heroCanvas = document.getElementById('hero-canvas');
  if (heroCanvas) {
    heroCanvas.classList.add('loading');
    heroCanvas.width  = window.innerWidth;
    heroCanvas.height = window.innerHeight;
    window.addEventListener('resize', () => {
      heroCanvas.width  = window.innerWidth;
      heroCanvas.height = window.innerHeight;
    });
    // Remove loading class after first frame renders
    setTimeout(() => {
      heroCanvas.classList.remove('loading');
    }, 100);
    MR.flowfield.animate(heroCanvas, {
      noise_scale: { value: 6.0 }, step_size: { value: 0.003 }, n_particles: { value: 3500 },
      color_start: { value: '#c8a96e' }, color_end: { value: '#7ecfb3' },
    });
  }

  // ── About canvas (Clifford) ──────────────────────────────────────────────
  const aboutCanvas = document.getElementById('about-canvas');
  if (aboutCanvas) {
    MR.renderCanvas(aboutCanvas, 'clifford', {
      a: { value: -1.4 }, b: { value: 1.6 }, c: { value: 1.0 }, d: { value: 0.7 },
      color_start: { value: '#c8a96e' }, color_end: { value: '#7ecfb3' },
    });
  }

  // ── Collection card canvases ─────────────────────────────────────────────
  document.querySelectorAll('.collection-card-canvas').forEach(canvas => {
    const eq = canvas.dataset.eq;
    const defaultParams = {
      lorenz:       { sigma:{value:10}, rho:{value:28}, beta:{value:2.667}, color_start:{value:'#c8a96e'}, color_end:{value:'#7ecfb3'} },
      de_jong:      { a:{value:-2.0}, b:{value:-2.0}, c:{value:2.0}, d:{value:-2.0}, color_start:{value:'#c8a96e'}, color_end:{value:'#7ecfb3'} },
      grayscott:    { f:{value:0.055}, k:{value:0.062}, Du:{value:0.16}, Dv:{value:0.08}, color_start:{value:'#c8a96e'}, color_end:{value:'#7ecfb3'} },
      lissajous:    { fx:{value:3}, fy:{value:4}, delta:{value:1.5708}, color_start:{value:'#c8a96e'}, color_end:{value:'#f0ece0'} },
      superformula: { m:{value:9.5}, n1:{value:0.4}, n2:{value:1.35}, n3:{value:2.1}, turns:{value:15}, scale_bias:{value:1.0}, wave_depth:{value:0.42}, wave_freq:{value:7.5}, phase_drift:{value:0.46}, orbit_mix:{value:0.16}, echo_layers:{value:4}, color_start:{value:'#f4c987'}, color_end:{value:'#e8f5ef'} },
      julia:        { cx:{value:-0.7}, cy:{value:0.27}, zoom:{value:1}, max_iter:{value:80}, color_start:{value:'#c8a96e'}, color_end:{value:'#080808'} },
      waves:        { freq1:{value:5}, freq2:{value:7}, amp1:{value:1}, amp2:{value:0.8}, phase:{value:0}, color_start:{value:'#c8a96e'}, color_end:{value:'#7ecfb3'} },
    };
    const params = defaultParams[eq] || {};
    // defer rendering with IntersectionObserver for performance
    const loader = canvas.parentElement.querySelector('.collection-card-loader');
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          MR.renderCanvas(canvas, eq, params);
          // Hide loader after rendering
          if (loader) {
            setTimeout(() => {
              loader.classList.add('hidden');
            }, 100);
          }
          observer.unobserve(canvas);
        }
      });
    }, { threshold: 0.1 });
    observer.observe(canvas);
  });

  // ── Featured product card canvases ───────────────────────────────────────
  document.querySelectorAll('.product-card-canvas').forEach(canvas => {
    const eq = canvas.dataset.eq;
    let params = {};
    try { params = JSON.parse(canvas.dataset.params || '{}'); } catch(e) {}
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          MR.renderCanvas(canvas, eq, params);
          observer.unobserve(canvas);
        }
      });
    }, { threshold: 0.1 });
    observer.observe(canvas);
  });

  // ── Newsletter form ──────────────────────────────────────────────────────
  const nlForm = document.getElementById('newsletter-form');
  if (nlForm) {
    nlForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = nlForm.querySelector('input[type=email]').value;
      nlForm.innerHTML = '<p style="color:var(--accent2);font-size:13px;">Thank you! We\'ll be in touch.</p>';
    });
  }

});
