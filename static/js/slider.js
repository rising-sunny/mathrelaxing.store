/* slider.js — product page interactive parameter controls */

const SliderController = {
  product: null,
  currentParams: {},
  renderTimeout: null,
  onParamsChange: null,   // optional callback(params) fired on debounced change

  init(product) {
    this.product = product;
    this.currentParams = JSON.parse(JSON.stringify(product.params));

    const colorDefaults = {
      color_start: '#c8a96e',
      color_end: '#7ecfb3',
      background_color: '#080808',
    };
    for (const [key, value] of Object.entries(colorDefaults)) {
      if (!this.currentParams[key]) {
        this.currentParams[key] = { value };
      }
    }

    // Initial render
    this._render();

    // Slider events
    document.querySelectorAll('input[type=range][data-param]').forEach(slider => {
      slider.addEventListener('input', () => {
        const key = slider.dataset.param;
        const val = parseFloat(slider.value);
        if (this.currentParams[key]) {
          this.currentParams[key].value = val;
        } else {
          this.currentParams[key] = { value: val };
        }
        document.getElementById(`val-${key}`).textContent = val;
        this._debouncedRender();
      });
    });

    // Color picker events
    ['color-start', 'color-end', 'background-color'].forEach(id => {
      const input = document.getElementById(id);
      if (!input) return;
      input.addEventListener('input', () => {
        const paramKey = id === 'color-start'
          ? 'color_start'
          : id === 'color-end'
            ? 'color_end'
            : 'background_color';
        if (this.currentParams[paramKey]) {
          this.currentParams[paramKey].value = input.value;
        } else {
          this.currentParams[paramKey] = { value: input.value };
        }
        this._debouncedRender();
      });
    });

    // Add to cart
    document.getElementById('add-to-cart')?.addEventListener('click', () => {
      this._addToCart();
    });
  },

  _debouncedRender() {
    clearTimeout(this.renderTimeout);
    this.renderTimeout = setTimeout(() => {
      try { this._render(); } catch(e) { console.warn('canvas render error:', e); }
      if (this.onParamsChange) this.onParamsChange(this.currentParams);
    }, 300);
  },

  _render() {
    const canvas = document.getElementById('product-canvas');
    const status = document.getElementById('canvas-status');
    if (!canvas) return;
    if (status) status.textContent = 'Rendering…';
    MR.renderCanvas(canvas, this.product.equation_type, this.currentParams);
    if (status) {
      setTimeout(() => { status.textContent = 'Your unique configuration'; }, 500);
    }
  },

  triggerRender() {
    this._render();
  },

  _addToCart() {
    const cart = JSON.parse(localStorage.getItem('mr_cart') || '[]');

    // Build a clean params snapshot (just key → value)
    const snapshot = {};
    for (const [key, cfg] of Object.entries(this.currentParams)) {
      snapshot[key] = typeof cfg === 'object' ? cfg.value : cfg;
    }

    cart.push({
      slug:          this.product.slug,
      name:          this.product.name,
      collection:    this.product.collection,
      equation_type: this.product.equation_type,
      product_type:  this.product.product_type || 'bundle',
      price_usd:     this.product.price_usd,
      params:        snapshot,
      added_at:      Date.now(),
    });

    localStorage.setItem('mr_cart', JSON.stringify(cart));
    window.dispatchEvent(new Event('storage'));

    // Feedback
    const btn = document.getElementById('add-to-cart');
    btn.textContent = '✓ Added to Cart';
    btn.style.background = 'var(--accent2)';
    btn.style.borderColor = 'var(--accent2)';
    btn.style.color = 'var(--bg)';
    setTimeout(() => {
      btn.textContent = 'Add to Cart — Buy This Bundle';
      btn.style.background = '';
      btn.style.borderColor = '';
      btn.style.color = '';
    }, 2500);
  },
};
