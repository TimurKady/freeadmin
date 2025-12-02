// API endpoints injected via templates (see contrib/admin/core/settings)
const { list_filters: API_LIST_FILTERS } = window.ADMIN_API;

function sanitizeId(name) {
  return `filter-${String(name).toLowerCase().replace(/[^a-z0-9_-]/gi, '-')}`;
}

class FiltersPanel {
  constructor({ offcanvasId = 'filtersOffcanvas', formId = 'filters-form', buttonId = 'btn-filters', clearButtonId = 'clear-filters-btn', app = '', model = '' } = {}) {
    this.el = document.getElementById(offcanvasId);
    this.form = document.getElementById(formId);
    this.button = document.getElementById(buttonId);
    this.clearButton = document.getElementById(clearButtonId);
    this.canvas = (this.el && window.bootstrap) ? new bootstrap.Offcanvas(this.el, { backdrop: true }) : null;
    this.qs = new URLSearchParams(location.search);

    if (this.form) {
      this.form.addEventListener('submit', (e) => { e.preventDefault(); this.apply(); });
    }

    // `API_LIST_FILTERS` already contains the full base path, so no extra
    // prefix should be prepended here.
    this.load(app, model);
  }

  async load(app, model) {
    if (!app || !model) {
      this.button?.setAttribute('hidden', '');
      this.clearButton?.setAttribute('hidden', '');
      return;
    }
    try {
      const res = await fetch(`${API_LIST_FILTERS}?app=${app}&model=${model}`, {
        credentials: 'same-origin',
      });
      const data = await res.json();
      const specs = data.filters || [];
      if (!specs.length) {
        this.button?.setAttribute('hidden', '');
        this.clearButton?.setAttribute('hidden', '');
        return;
      }
      this.render(specs);
      this.button?.removeAttribute('hidden');
      this.clearButton?.removeAttribute('hidden');
    } catch (err) {
      this.button?.setAttribute('hidden', '');
      this.clearButton?.setAttribute('hidden', '');
    }
  }

  
  renderField(field) {
    const wrap = document.createElement('div');
    wrap.className = 'mb-3';
    const label = document.createElement('label');
    label.className = 'form-label mb-1';
    const id = sanitizeId(field.name);
    label.setAttribute('for', id);
    label.textContent = field.label;
    wrap.appendChild(label);
    const input = this.createInput(field);
    input.id = id;
    wrap.appendChild(input);
    return wrap;
  }

  createInput(field) {
    const name = `filter.${field.name}`;
    const kind = String(field.kind || field.type || '').toLowerCase();
    let el;
    const val = this.qs.get(name) || '';
    if (kind === 'bool' || kind === 'boolean') {
      el = document.createElement('select');
      el.className = 'form-select';
      el.innerHTML = `
          <option value="">Any</option>
          <option value="true">Yes</option>
          <option value="false">No</option>`;
      el.value = val;
    } else if (['int', 'integer', 'number'].includes(kind)) {
      el = document.createElement('input');
      el.type = 'number';
      el.className = 'form-control';
      el.value = val;
    } else if (kind === 'date' || kind === 'datetime') {
      el = document.createElement('input');
      el.type = kind === 'date' ? 'date' : 'datetime-local';
      el.className = 'form-control';
      el.value = val;
    } else {
      el = document.createElement('input');
      el.type = 'text';
      el.className = 'form-control';
      el.value = val;
    }
    el.name = name;
    return el;
  }

  render(specs) {
    const form = this.form;
    if (!form) return;
    form.innerHTML = '';
    for (const sp of specs) {
      try {
        form.appendChild(this.renderField(sp));
      } catch (err) {
        console.warn('Failed to render filter field', sp, err);
      }
    }
    const btnWrap = document.createElement('div');
    btnWrap.className = 'd-flex gap-2 mt-3';
    btnWrap.innerHTML = `
      <button type="submit" class="btn btn-primary">Apply</button>
      <button type="button" class="btn btn-outline-secondary" data-action="reset">Reset</button>`;
    form.appendChild(btnWrap);
    form.querySelector('[data-action="reset"]').addEventListener('click', () => this.reset());
  }

  apply() {
    const url = new URL(location.href);
    for (const k of Array.from(url.searchParams.keys())) if (k.startsWith('filter.')) url.searchParams.delete(k);
    const fd = new FormData(this.form);
    const map = {};
    for (const [k, v] of fd.entries()) {
      if (v === '') continue;
      (map[k] = map[k] || []).push(v);
    }
    for (const [k, arr] of Object.entries(map)) {
      const val = arr.length > 1 ? arr.join(',') : arr[0];
      url.searchParams.set(k, val);
    }
    url.searchParams.delete('page_num');
    location.href = url.toString();
  }

  reset() {
    const url = new URL(location.href);
    for (const k of Array.from(url.searchParams.keys())) if (k.startsWith('filter.')) url.searchParams.delete(k);
    url.searchParams.delete('page_num');
    location.href = url.toString();
  }

  show() { this.canvas?.show(); }
}

// # The End
