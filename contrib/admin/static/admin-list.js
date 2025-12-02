class AdminList {
  constructor() {
    const path = window.location.pathname.replace(/\/$/, '');
    this.base = path;
    // explicit list API endpoint
    this.api = `${path}/_list`;

    this.state = { search: '', page: 1, per_page: 20, order: '', id_field: 'id' };

    this.input = document.getElementById('search');
    this.btn = document.getElementById('btn-search');
    this.perPage = document.getElementById('per-page');
    this.rangeInfo = document.getElementById('range-info');
    this.thead = document.getElementById('thead-row');
    this.tbody = document.getElementById('tbody');
    this.table = document.getElementById('list-table');
    this.pager = document.getElementById('pager');
    this.spinner = document.getElementById('list-spinner');
    this.empty = document.getElementById('empty-state');
    this.clearFiltersBtn = document.getElementById('clear-filters-btn');
    this.filterChips = document.getElementById('active-filters');
    this.filtersCount = document.getElementById('filters-count');
    this.confirmDelete = document.getElementById('confirm-delete');
    this.deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    this.delId = document.getElementById('del-id');
    this.deleteId = null;

    this.btn?.addEventListener('click', () => this.doSearch());
    this.input?.addEventListener('keydown', e => { if (e.key === 'Enter') this.doSearch(); });
    this.input?.addEventListener('input', this.debounce(() => this.doSearch(), 300));
    this.perPage.addEventListener('change', () => { this.state.per_page = parseInt(this.perPage.value); this.state.page = 1; this.load(); });
    this.clearFiltersBtn?.addEventListener('click', () => window._filters?.reset());
    this.confirmDelete?.addEventListener('click', () => this.onConfirmDelete());

    this.renderFilterChips();
  }

  qs(params){
    const usp = new URLSearchParams();
    for(const [k,v] of Object.entries(params)) if(v!=='' && v!=null) usp.set(k, v);
    return usp.toString();
  }

  debounce(fn, delay){
    let t; return (...args)=>{ clearTimeout(t); t=setTimeout(()=>fn.apply(this,args), delay); };
  }

  doSearch(){
    this.state.search = this.input?.value.trim() ?? '';
    this.state.page = 1;
    this.load();
  }

  renderFilterChips(){
    this.filterChips.innerHTML = '';
    const usp = new URLSearchParams(window.location.search);
    let count = 0;
    for(const [k,v] of usp.entries()){
      if(!k.startsWith('filter.')) continue;
      count++;
      const badge = document.createElement('span');
      badge.className = 'badge bg-secondary';
      const lbl = k.slice(7).split('__')[0].replace(/_/g,' ');
      badge.textContent = `${lbl}: ${v} `;
      const close = document.createElement('span');
      close.style.cursor = 'pointer';
      close.innerHTML = '&times;';
      close.addEventListener('click', ()=>{
        const url = new URL(location.href);
        url.searchParams.delete(k);
        url.searchParams.delete('page_num');
        location.href = url.toString();
      });
      badge.appendChild(close);
      this.filterChips.appendChild(badge);
    }
    this.filterChips.classList.toggle('d-none', count===0);
    if(this.filtersCount){
      this.filtersCount.textContent = count;
      this.filtersCount.hidden = count === 0;
    }
  }

  async load(){
    this.spinner.style.display = '';
    this.empty.classList.add('d-none');
    const pageQS = new URLSearchParams(window.location.search);
    const baseParams = { search: this.state.search, page_num: this.state.page, per_page: this.state.per_page, order: this.state.order };
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(baseParams)) if (v !== '' && v != null) usp.set(k, v);
    for (const k of Array.from(pageQS.keys())) {
      if (k.startsWith('filter.')) usp.set(k, pageQS.get(k));
    }
    const url = `${this.api}?${usp.toString()}`;
    try {
      const res = await fetch(url, {credentials:'same-origin'});
      if(!res.ok){ console.log(await res.text()); return; }
      const data = await res.json();
      this.render(data);
    } catch(err) {
      console.log('Error loading list:', err);
      alert('Failed to load data');
    } finally {
      this.spinner.style.display = 'none';
    }
  }

  fmtCell(val, meta){
    if(val==null) return '';
    switch(meta?.type){
      case 'boolean':
        return val ? '✓' : '✗';
      case 'choice':
        return meta?.choices_map?.[String(val)] ?? '—';
      case 'datetime': {
        const d = new Date(val);
        return isNaN(d.getTime()) ? '—' : d.toLocaleString(undefined, { timeZoneName: 'short' });
      }
      default:
        return typeof val === 'object' ? JSON.stringify(val) : String(val);
    }
  }

  render({columns, columns_meta, items, page, pages, total, order, per_page, id_field}){
    this.state.page = page;
    this.state.order = order;
    this.state.per_page = per_page;
    this.state.id_field = id_field;
    this.perPage.value = String(per_page);

    // header
    this.thead.innerHTML = '';
    const metaMap = Object.fromEntries(columns_meta.map(m=>[m.key, m]));
    columns.forEach((col, idx)=>{
      const meta = metaMap[col] || {};
      const th = document.createElement('th');
      th.textContent = meta.label || col;
      if(meta.sortable){
        th.style.cursor = 'pointer';
        th.addEventListener('click', ()=>{
          const current = this.state.order || '';
          const isThis = current.replace(/^-/, '') === meta.key;
          const next = !isThis ? meta.key : (current.startsWith('-') ? meta.key : `-${meta.key}`);
          this.state.order = next; this.state.page = 1; this.load();
        });
      }
      const ordField = (order||'').replace(/^-/, '');
      if(ordField === meta.key){
        const up = !order.startsWith('-');
        th.insertAdjacentHTML('beforeend', up ? ' ▲' : ' ▼');
      }
      if(idx === 0){
        th.style.width = '1%';
        th.style.whiteSpace = 'nowrap';
      }
      this.thead.appendChild(th);
    });
    const thAct = document.createElement('th');
    thAct.className = 'text-end';
    thAct.style.width = '1%';
    thAct.style.whiteSpace = 'nowrap';
    thAct.textContent = 'Actions';
    this.thead.appendChild(thAct);

    // body
    this.tbody.innerHTML = '';
    if(items.length === 0){
      this.empty.classList.remove('d-none');
      this.table.classList.add('d-none');
    }else{
      this.empty.classList.add('d-none');
      this.table.classList.remove('d-none');
    }
    items.forEach(row=>{
      const tr = document.createElement('tr');
      const id = row[this.state.id_field] ?? row.id ?? row.pk ?? row.ID;
      if(row.can_change){
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', ()=>{ if(id!=null) window.location.href = `${this.base}/${id}/edit`; });
      } else {
        tr.style.cursor = 'default';
      }
      columns.forEach((col, idx)=>{
        const meta = metaMap[col] || {};
        const td = document.createElement('td');
        td.textContent = this.fmtCell(row[col], meta);
        if(idx === 0) td.style.whiteSpace = 'nowrap';
        tr.appendChild(td);
      });
      const tdAct = document.createElement('td');
      tdAct.className = 'text-end';
      tdAct.style.whiteSpace = 'nowrap';
      if(row.can_change){
        const editBtn = document.createElement('a');
        editBtn.className = 'btn btn-sm btn-primary me-1';
        editBtn.textContent = 'Edit';
        editBtn.href = `${this.base}/${id}/edit`;
        editBtn.addEventListener('click', e=>e.stopPropagation());
        tdAct.appendChild(editBtn);
      }
      if(row.can_delete){
        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-sm btn-danger';
        delBtn.textContent = 'Delete';
        delBtn.addEventListener('click', e=>{ e.stopPropagation(); this.showDeleteModal(id); });
        tdAct.appendChild(delBtn);
      }
      tr.appendChild(tdAct);
      this.tbody.appendChild(tr);
    });

    // range info
    const start = total ? (page-1)*per_page + 1 : 0;
    const end = total ? (start + items.length - 1) : 0;
    this.rangeInfo.textContent = total ? `${start}–${end} of ${total}` : '0 results';

    // pager
    this.renderPager(page, pages);
  }

  renderPager(page, pages){
    this.pager.innerHTML = '';
    const mk = (label, p, disabled=false, active=false)=>{
      const li = document.createElement('li');
      li.className = `page-item${disabled?' disabled':''}${active?' active':''}`;
      const a = document.createElement('a');
      a.className = 'page-link';
      a.href = '#';
      a.textContent = label;
      a.addEventListener('click', e=>{ e.preventDefault(); if(disabled||active) return; this.state.page = p; this.load(); });
      li.appendChild(a);
      return li;
    };
    this.pager.appendChild(mk('«', 1, page<=1));
    this.pager.appendChild(mk('‹', Math.max(1,page-1), page<=1));
    const startP = Math.max(1, page-2), endP = Math.min(pages, startP+4);
    for(let p=startP;p<=endP;p++) this.pager.appendChild(mk(String(p), p, false, p===page));
    this.pager.appendChild(mk('›', Math.min(pages,page+1), page>=pages));
    this.pager.appendChild(mk('»', pages, page>=pages));
  }

  showDeleteModal(id){
    this.deleteId = id;
    this.delId.textContent = id;
    this.deleteModal.show();
  }

  async onConfirmDelete(){
    if(this.deleteId==null) return;
    const url = `${this.base}/${encodeURIComponent(this.deleteId)}`;
    const res = await fetch(url, {method:'DELETE', credentials:'same-origin'});
    if(res.ok){ this.deleteModal.hide(); this.load(); }
    else{ console.log(await res.text()); }
  }
}

// # The End
