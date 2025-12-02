class Sidebar {
  constructor({ accordionId = 'appsAccordion', storageKey = 'appsAccordionState' } = {}) {
    this.accordion = document.getElementById(accordionId);
    this.storageKey = storageKey;
  }

  load() {
    if (!this.accordion) {
      return;
    }

    let state = [];
    try {
      state = JSON.parse(localStorage.getItem(this.storageKey)) || [];
    } catch (e) {
      state = [];
    }

    // Restore state
    state.forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        const collapse = new bootstrap.Collapse(el, { toggle: false });
        collapse.show();
      }
    });

    // Save state on show/hide
    this.accordion.addEventListener('shown.bs.collapse', (e) => {
      const id = e.target.id;
      if (!state.includes(id)) {
        state.push(id);
        localStorage.setItem(this.storageKey, JSON.stringify(state));
      }
    });

    this.accordion.addEventListener('hidden.bs.collapse', (e) => {
      const id = e.target.id;
      const index = state.indexOf(id);
      if (index !== -1) {
        state.splice(index, 1);
        localStorage.setItem(this.storageKey, JSON.stringify(state));
      }
    });
  }

  static load(options) {
    new Sidebar(options).load();
  }
}

// Ensure the Sidebar constructor is available globally so templates can
// invoke `Sidebar.load()` without hitting "Sidebar.load is not a function".
// Some browsers do not attach ES6 classes to the global `window` object by
// default, so we explicitly expose it here.
window.Sidebar = Sidebar;

// # The End
