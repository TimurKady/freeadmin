// static/widgets/select2.js

// Manager for integrating Select2 with JSONEditor lifecycle events.
(() => {
  const globalSelect2Obj = typeof window !== 'undefined' ? window : globalThis;
  if (globalSelect2Obj.Select2WidgetManager) {
    return;
  }

  class Select2WidgetManager {
  constructor(globalObj) {
    this.global = globalObj;
    this.document = globalObj?.document || null;
    this._pluginRegistered = false;
    this._warningShown = false;
    this.maxPluginAttempts = 20;
    this.maxDecorateAttempts = 10;

    this._handleSchemaEvent = this._handleSchemaEvent.bind(this);
    this._handleCreatedEvent = this._handleCreatedEvent.bind(this);
    this._handleReadyEvent = this._handleReadyEvent.bind(this);

    this.readyPromise = this._waitForJSONEditor();
    this.readyPromise.then(JSONEditorGlobal => {
      this._registerPlugin(JSONEditorGlobal);
    });

    this._ensurePluginRegistration();

    if (this.document?.addEventListener) {
      this.document.addEventListener('admin:jsoneditor:schema', this._handleSchemaEvent);
      this.document.addEventListener('admin:jsoneditor:created', this._handleCreatedEvent);
      this.document.addEventListener('admin:jsoneditor:ready', this._handleReadyEvent);
    }
  }

  static bootstrap(globalObj) {
    if (!this.instance) {
      this.instance = new Select2WidgetManager(globalObj);
    }
    return this.instance;
  }

  _waitForJSONEditor() {
    if (this.global?.JSONEditor) {
      return Promise.resolve(this.global.JSONEditor);
    }
    return new Promise(resolve => {
      const poll = () => {
        if (this.global?.JSONEditor) {
          resolve(this.global.JSONEditor);
        } else {
          const timer = this.global?.setTimeout || globalThis.setTimeout;
          if (typeof timer === 'function') {
            timer(poll, 50);
          }
        }
      };
      poll();
    });
  }

  _getJQuery() {
    return this.global?.jQuery || this.global?.$ || null;
  }

  _registerPlugin(JSONEditorGlobal, attempt = 0) {
    if (this._pluginRegistered) return;
    const editorGlobal = JSONEditorGlobal || this.global?.JSONEditor || null;
    const jq = this._getJQuery();
    const plugin = jq?.fn?.select2;

    if (!editorGlobal || !plugin) {
      if (attempt >= this.maxPluginAttempts) {
        this._notifyMissingDependencies();
        return;
      }
      const timer = this.global?.setTimeout || globalThis.setTimeout;
      if (typeof timer === 'function') {
        timer(() => this._registerPlugin(this.global?.JSONEditor || editorGlobal, attempt + 1), 50);
      }
      return;
    }

    editorGlobal.plugins = editorGlobal.plugins || {};
    editorGlobal.plugins.select2 = plugin;
    this._pluginRegistered = true;
  }

  _ensurePluginRegistration() {
    const editorGlobal = this.global?.JSONEditor;
    if (editorGlobal) {
      this._registerPlugin(editorGlobal);
      return;
    }
    if (this.readyPromise && typeof this.readyPromise.then === 'function') {
      this.readyPromise.then(JSONEditorGlobal => {
        this._registerPlugin(JSONEditorGlobal);
      });
    }
  }

  _handleSchemaEvent() {
    this._ensurePluginRegistration();
  }

  _handleCreatedEvent(event) {
    const editor = event?.detail?.editor;
    if (!editor) return;
    this._ensurePluginRegistration();
  }

  _handleReadyEvent(event) {
    const editor = event?.detail?.editor;
    if (!editor) return;
    this._ensurePluginRegistration();
    this._scheduleDecoration(editor);
  }

  _scheduleDecoration(editor, attempt = 0) {
    if (!editor) return;
    const jq = this._getJQuery();
    if (!jq?.fn?.select2) {
      if (attempt >= this.maxDecorateAttempts) {
        this._notifyMissingDependencies();
        return;
      }
      const timer = this.global?.setTimeout || globalThis.setTimeout;
      if (typeof timer === 'function') {
        timer(() => this._scheduleDecoration(editor, attempt + 1), 50);
      }
      return;
    }

    this._decorateEditorFields(editor, jq);
  }

  _decorateEditorFields(editor, jq) {
    const context = this._resolveSearchContext(editor);
    const selector = 'select, input[data-select2-many]';
    const elements = context ? jq(selector, context) : jq(selector);

    elements.each((_, element) => {
      if (this._isChoicesElement(element)) {
        return;
      }
      const instance = jq(element);
      if (!instance.data('select2')) {
        instance.select2({ theme: 'bootstrap-5' });
      }
    });
  }

  _resolveSearchContext(editor) {
    if (!editor) {
      return this.document || null;
    }

    const contexts = [];
    if (typeof editor.getEditor === 'function') {
      const rootEditor = editor.getEditor('root') || editor.root || null;
      if (rootEditor) {
        contexts.push(rootEditor.container);
        if (rootEditor.theme && rootEditor.theme.container) {
          contexts.push(rootEditor.theme.container);
        }
      }
    } else if (editor.root) {
      contexts.push(editor.root.container);
      if (editor.root.theme && editor.root.theme.container) {
        contexts.push(editor.root.theme.container);
      }
    }

    contexts.push(editor.element);
    contexts.push(editor.container);

    for (const candidate of contexts) {
      if (candidate && typeof candidate.querySelectorAll === 'function') {
        return candidate;
      }
    }

    return this.document || null;
  }

  _isChoicesElement(element) {
    if (!element || typeof element !== 'object') {
      return false;
    }
    if (typeof element.hasAttribute === 'function' && element.hasAttribute('data-choice')) {
      return true;
    }
    const cls = element.classList;
    if (cls && typeof cls.contains === 'function' && cls.contains('choices__input')) {
      return true;
    }
    if (typeof element.closest === 'function') {
      const wrapper = element.closest('.choices');
      if (wrapper && wrapper !== element) {
        return true;
      }
    }
    return false;
  }

  _notifyMissingDependencies() {
    if (this._warningShown) {
      return;
    }
    this._warningShown = true;

    const msg = 'Select2 or JSONEditor failed to load. Verify CDN availability and network connectivity.';
    if (typeof console !== 'undefined' && typeof console.warn === 'function') {
      console.warn(msg);
    }

    const doc = this.document;
    const body = doc?.body;
    if (!body || !doc?.createElement) {
      return;
    }

    const banner = doc.createElement('div');
    banner.textContent = msg;
    banner.className = 'alert alert-warning m-0 text-center';
    banner.style.position = 'fixed';
    banner.style.top = '0';
    banner.style.left = '0';
    banner.style.right = '0';
    banner.style.zIndex = '1050';
    body.prepend(banner);

    const timer = this.global?.setTimeout || globalThis.setTimeout;
    if (typeof timer === 'function') {
      timer(() => banner.remove(), 5000);
    }
  }
  }

  Select2WidgetManager.instance = null;

  globalSelect2Obj.Select2WidgetManager = Select2WidgetManager;
  Select2WidgetManager.bootstrap(globalSelect2Obj);
})();

// # The End
