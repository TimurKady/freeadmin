// static/widgets/textarea.js

(() => {
  class TextAreaAutoHeight {
    constructor(textarea) {
      this.ta = textarea;
      const style = window.getComputedStyle(this.ta);
      this.lineHeight = parseFloat(style.lineHeight) || 16;
      this.maxHeight = this.lineHeight * 10;
      this._resize();
      this.ta.addEventListener('input', () => this._resize());
    }

    _resize() {
      this.ta.style.height = 'auto';
      const newHeight = Math.min(this.ta.scrollHeight, this.maxHeight);
      this.ta.style.height = `${newHeight}px`;
      this.ta.style.overflowY = this.ta.scrollHeight > this.maxHeight ? 'auto' : 'hidden';
    }

    static _activate(ta) {
      if (!ta || ta.dataset.textareaAutoHeightInit) return;
      ta.dataset.textareaAutoHeightInit = '1';
      new TextAreaAutoHeight(ta);
    }

    static init(root = document) {
      root
        .querySelectorAll('textarea[data-textarea-autosize]')
        .forEach(ta => this._activate(ta));
    }

    static observe() {
      if (this._observer) return;
      this._observer = new MutationObserver(mutations => {
        mutations.forEach(m =>
          m.addedNodes.forEach(node => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              if (node.matches && node.matches('textarea[data-textarea-autosize]')) {
                this._activate(node);
              }
              node
                .querySelectorAll?.('textarea[data-textarea-autosize]')
                .forEach(el => this._activate(el));
            }
          })
        );
      });
      this._observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });
    }

    static setup() {
      if (document.readyState !== 'loading') {
        this.init();
      } else {
        document.addEventListener('DOMContentLoaded', () => this.init());
      }
      this.observe();
    }
  }

  if (!window.TextAreaAutoHeight) {
    TextAreaAutoHeight.setup();
    window.TextAreaAutoHeight = TextAreaAutoHeight;
  }
})();

// # The End
