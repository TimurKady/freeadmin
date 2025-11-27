// static/widgets/choices.js

(() => {
  const choicesGlobalObj = typeof window !== 'undefined' ? window : globalThis;
  if (choicesGlobalObj.FreeAdminChoicesWidgetManager) {
    choicesGlobalObj.FreeAdminChoicesWidgetManager.bootstrap(choicesGlobalObj);
    return;
  }

  // Manager for integrating Choices.js with JSONEditor lifecycle events.
  class ChoicesWidgetManager {
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

      this.readyPromise = this._waitForDependencies();
      if (this.readyPromise && typeof this.readyPromise.then === 'function') {
        this.readyPromise.then(([editorGlobal, choicesCtor]) => {
          this._registerPlugin(editorGlobal, choicesCtor);
        });
      }

      this._ensurePluginRegistration();

      if (this.document?.addEventListener) {
        this.document.addEventListener('admin:jsoneditor:schema', this._handleSchemaEvent);
        this.document.addEventListener('admin:jsoneditor:created', this._handleCreatedEvent);
        this.document.addEventListener('admin:jsoneditor:ready', this._handleReadyEvent);
      }
    }

    static bootstrap(globalObj) {
      if (!this.instance) {
        this.instance = new ChoicesWidgetManager(globalObj);
      }
      return this.instance;
    }

    _waitForDependencies() {
      return Promise.all([this._waitForJSONEditor(), this._waitForChoicesLibrary()]);
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

    _waitForChoicesLibrary() {
      if (this._getChoicesCtor()) {
        return Promise.resolve(this._getChoicesCtor());
      }
      return new Promise(resolve => {
        const poll = () => {
          const ctor = this._getChoicesCtor();
          if (ctor) {
            resolve(ctor);
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

    _getChoicesCtor() {
      return this.global?.Choices || null;
    }

    _registerPlugin(JSONEditorGlobal, choicesCtor, attempt = 0) {
      if (this._pluginRegistered) {
        return;
      }
      const editorGlobal = JSONEditorGlobal || this.global?.JSONEditor || null;
      const ctor = choicesCtor || this._getChoicesCtor();

      if (!editorGlobal || !ctor) {
        if (attempt >= this.maxPluginAttempts) {
          this._notifyMissingDependencies();
          return;
        }
        const timer = this.global?.setTimeout || globalThis.setTimeout;
        if (typeof timer === 'function') {
          timer(() => this._registerPlugin(editorGlobal, ctor, attempt + 1), 50);
        }
        return;
      }

      editorGlobal.plugins = editorGlobal.plugins || {};
      editorGlobal.plugins.choices = ctor;
      this._pluginRegistered = true;
    }

    _ensurePluginRegistration() {
      const editorGlobal = this.global?.JSONEditor || null;
      const ctor = this._getChoicesCtor();
      if (editorGlobal && ctor) {
        this._registerPlugin(editorGlobal, ctor);
      }
    }

    _handleSchemaEvent() {
      this._ensurePluginRegistration();
    }

    _handleCreatedEvent(event) {
      const editor = event?.detail?.editor;
      if (!editor) return;
      this._ensurePluginRegistration();
      this._scheduleDecoration(editor);
    }

    _handleReadyEvent(event) {
      const editor = event?.detail?.editor;
      if (!editor) return;
      this._ensurePluginRegistration();
      this._scheduleDecoration(editor);
    }

    _scheduleDecoration(editor, attempt = 0) {
      if (!editor) return;
      const ctor = this._getChoicesCtor();
      if (!ctor) {
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

      this._decorateEditorFields(editor, ctor);
    }

    _decorateEditorFields(editor, ctor) {
      const context = this._resolveSearchContext(editor);
      const selector = 'select[data-choice], input[data-choice]:not([type="hidden"])';
      const elements = context?.querySelectorAll
        ? Array.from(context.querySelectorAll(selector))
        : [];

      elements.forEach(element => {
        this._decorateElement(element, ctor);
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

    _decorateElement(element, ctor) {
      if (!element || typeof element !== 'object') {
        return;
      }
      if (element.dataset?.choiceManagerInit === '1') {
        return;
      }
      if (element.classList && typeof element.classList.contains === 'function') {
        if (element.classList.contains('choices__input')) {
          return;
        }
      }
      if (typeof element.closest === 'function') {
        const wrapper = element.closest('.choices');
        if (wrapper && wrapper !== element) {
          element.dataset.choiceManagerInit = '1';
          return;
        }
      }

      const options = this._extractOptions(element);
      try {
        const instance = new ctor(element, options);
        element.dataset.choiceManagerInit = '1';
        element.__choicesWidgetInstance = instance;
      } catch (err) {
        if (typeof console !== 'undefined' && typeof console.error === 'function') {
          console.error('Choices.js initialization failed', err);
        }
      }
    }

    _extractOptions(element) {
      const dataset = element?.dataset || {};
      const candidates = [
        dataset.choicesOptions,
        dataset.choiceOptions,
        element?.getAttribute ? element.getAttribute('data-choices-options') : null,
      ];

      for (const raw of candidates) {
        if (typeof raw === 'string' && raw.trim()) {
          try {
            return JSON.parse(raw);
          } catch (err) {
            if (typeof console !== 'undefined' && typeof console.warn === 'function') {
              console.warn('Invalid JSON in data-choices-options attribute', err);
            }
          }
        }
      }

      const direct =
        element?.jsoneditor_choices_options ||
        element?.jsoneditorChoicesOptions ||
        element?.choicesOptions ||
        null;

      if (direct && typeof direct === 'object') {
        return { ...direct };
      }

      return undefined;
    }

    _notifyMissingDependencies() {
      if (this._warningShown) {
        return;
      }
      this._warningShown = true;

      const msg = 'Choices.js or JSONEditor failed to load. Verify CDN availability and network connectivity.';
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

  ChoicesWidgetManager.instance = null;
  choicesGlobalObj.FreeAdminChoicesWidgetManager = ChoicesWidgetManager;
  ChoicesWidgetManager.bootstrap(choicesGlobalObj);
})();

// # The End
