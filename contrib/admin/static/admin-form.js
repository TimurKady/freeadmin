// admin-form.js

// API endpoints injected via templates (see contrib/admin/core/settings)
const { schema: API_SCHEMA } = window.ADMIN_API;

class AdminFormEditor {
  constructor({ rootId = 'form-root', spinnerId = 'form-spinner', app, model, pk, prefix, config = {} }) {
    this.root = document.getElementById(rootId);
    this.spinner = document.getElementById(spinnerId);
    this.pk = pk;
    this.mode = pk ? 'edit' : 'add';
    this.prefix = prefix;

    this.base = window.location.pathname.replace(/\/(add|[^/]+\/edit)\/?$/, '');
    const parts = this.base.split('/').filter(Boolean);
    this.model = model || parts.pop();
    this.app = app || parts.pop();

    this.cfg = Object.assign({
      defaults: {
        theme: 'bootstrap5',
        iconlib: 'bootstrap',
        show_errors: 'interaction',
        form_name_root: '\u200B',
        display_required_only: false,
        disable_edit_json: true,
        disable_collapse: true,
        required_by_default: false,
        disable_properties: true,
      },
      endpoints: {
        schema: (a, m, mode, pk) => `${API_SCHEMA}?app=${a}&model=${m}&mode=${mode}` + (pk ? `&pk=${pk}` : ''),
        save: (base, pk) => (pk ? `${base}/${pk}` : base),
      },
      debug: false,
    }, config);
  }

  async load() {
    try {
      const { schema, startval } = await this.fetchSchema();

      let sv = startval;
      if (sv === null || typeof sv !== 'object') {
        sv = {};
      }

      this.spinner.style.display = 'none';

      this.editor = new JSONEditor(this.root, {
        schema,
        startval: sv,
        ...this.cfg.defaults,
        display_required_only: false,
      });

      window._editor = this.editor;

      this.hideRootHeader();
      this.bindSubmit();

    } catch (err) {
      console.error(err);
      const msg = err?.message ? `Failed to load form: ${err.message}` : 'Failed to load form.';
      alert(msg);
    }
  }

  async fetchSchema() {
    const url = this.cfg.endpoints.schema(this.app, this.model, this.mode, this.pk);
    const res = await fetch(url, { credentials: 'same-origin' });
    if (!res.ok) {
      let detail = '';
      try {
        const data = await res.json();
        detail = data?.detail || JSON.stringify(data);
      } catch {
        detail = await res.text();
      }
      throw new Error(detail || `Request failed with status ${res.status}`);
    }
    const { schema, startval } = await res.json();
    return { schema, startval };
  }


  hideRootHeader() {
    const rootEditor = this.editor.getEditor('root');
    if (rootEditor?.header) rootEditor.header.style.display = 'none';
  }

  showBanner(text, variant = 'warning') {
    const host = this.root.parentElement;
    let el = host.querySelector('.form-alert-host');
    if (!el) {
      el = document.createElement('div');
      el.className = 'form-alert-host my-2';
      host.prepend(el);
    }
    if (!text) { el.innerHTML = ''; return; }
    el.innerHTML = `<div class="alert alert-${variant} py-2 mb-2">${text}</div>`;
  }

  applyServerErrors(detail) {
    if (detail && typeof detail.detail === 'string') {
      this.showBanner(detail.detail, 'warning');
    }

    const errsMap = (detail && detail.errors) || {};
    const list = Object.entries(errsMap).map(([field, msg]) => ({
      path: `root.${field}`,
      message: String(msg ?? 'Invalid value'),
    }));
    if (!list.length) return false;

    this.editor.showValidationErrors(list);

    // Selective highlight reset: when typing into a field with an error, remove it from external errors
    list.forEach(({ path }) => {
      const ed = this.editor.getEditor(path);
      const holder = ed?.container || ed?.theme?.container || null;
      if (!holder) return;
      const handler = () => {
        const rest = (this._extErrors || []).filter(e => e.path !== path);
        this._extErrors = rest;
        this.editor.showValidationErrors(rest);
        holder.removeEventListener('input', handler, true);
        if (!rest.length) this.showBanner('');
      };
      holder.addEventListener('input', handler, true);
    });
    this._extErrors = list;

    const firstPath = list[0].path;
    if (typeof this.editor.scrollTo === 'function') this.editor.scrollTo(firstPath);
    const firstEd = this.editor.getEditor(firstPath);
    firstEd?.activate?.();
    try { firstEd?.input?.focus?.(); } catch {}

    return true;
  }

  bindSubmit() {
    const btn = document.getElementById('submit');
    btn?.addEventListener('click', () => this.onSubmit());
  }

  async onSubmit() {
    const btn = document.getElementById('submit');
    btn?.setAttribute('disabled', 'disabled');
    this.editor.showValidationErrors([]);
    this._extErrors = [];
    this.showBanner('');

    const errs = this.editor.validate();
    if (errs.length) {
      const ext = errs.map(e => ({ path: e.path, message: e.message }));
      this.editor.showValidationErrors(ext);
      if (ext[0]?.path && typeof this.editor.scrollTo === 'function') {
        this.editor.scrollTo(ext[0].path);
      }
      btn?.removeAttribute('disabled');
      return;
    }

    const value = this.editor.getValue();
    const cleanedValue = this.cleanEmptyValues(value);

    const url = this.cfg.endpoints.save(this.base, this.pk);
    const method = this.pk ? 'PUT' : 'POST';

    try {
      const resp = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(cleanedValue),
      });

      if (!resp.ok) {
        if (resp.status === 422) {
          let data; try { data = await resp.json(); } catch {}
          const handled = this.applyServerErrors(data?.detail || data);
          if (handled) { btn?.removeAttribute('disabled'); return; }
        }
        const txt = await resp.text();
        alert('Save error: ' + txt);
        btn?.removeAttribute('disabled');
        return;
      }
      window.location.href = `${this.base}/`;
    } catch (err) {
      console.error(err);
      alert('Network error during save.');
      btn?.removeAttribute('disabled');
    }
  }

  // Cleaning empty values (carefully):
  //  - remove '' and null for non-required fields
  //  - do NOT remove empty arrays (important for clearing M2M)
  cleanEmptyValues(obj) {
    const cleaned = { ...obj };
    const required = new Set(this.editor.schema.required || []);

    Object.keys(cleaned).forEach(key => {
      const value = cleaned[key];

      if (value === '' && !required.has(key)) {
        delete cleaned[key];
        return;
      }
      if (value === null && !required.has(key)) {
        delete cleaned[key];
        return;
      }
      // Leave empty arrays—they signal "clear" for M2M
    });

    return cleaned;
  }
}

// # The End
