(function () {
  'use strict';

  const visitorKey = 'perihan-gallery-visitor';
  let visitor = '';
  try {
    visitor = localStorage.getItem(visitorKey) || '';
    if (!visitor) {
      visitor = crypto.randomUUID();
      localStorage.setItem(visitorKey, visitor);
    }
  } catch (_) {
    visitor = 'session-' + Math.random().toString(16).slice(2);
  }

  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };

  function initials(comment) {
    return ((comment.first_name || '')[0] || '') + ((comment.last_name || '')[0] || '');
  }

  function updateCount(code, count) {
    document.querySelectorAll('.comment-button').forEach((button) => {
      if (button.dataset.commentCode !== code) return;
      const number = button.querySelector('.comment-count');
      if (number) number.textContent = String(count || 0);
      button.setAttribute('aria-label', `${count || 0} yorum`);
    });
  }

  function renderThread(parent, replies, list, setReply) {
    const thread = el('div', 'art-comment-thread');
    [parent].concat(replies).forEach((comment, index) => {
      const isReply = index > 0;
      const row = el('article', isReply ? 'art-comment art-comment-reply' : 'art-comment');
      const avatar = el('div', 'art-comment-avatar');
      if (comment.avatar_url) {
        const image = el('img');
        image.src = comment.avatar_url;
        image.alt = '';
        image.loading = 'lazy';
        avatar.appendChild(image);
      } else avatar.textContent = initials(comment);
      row.appendChild(avatar);
      const content = el('div', 'art-comment-content');
      const meta = el('div', 'art-comment-meta');
      meta.appendChild(el('strong', '', `${comment.first_name} ${comment.last_name}`));
      if (comment.created_at) {
        const time = el('time', '', comment.created_at);
        const parsed = new Date(String(comment.created_at).replace(' ', 'T') + 'Z');
        if (!Number.isNaN(parsed.getTime())) time.textContent = parsed.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', year: 'numeric' });
        meta.appendChild(time);
      }
      content.appendChild(meta);
      content.appendChild(el('p', 'art-comment-text', comment.body));
      if (!isReply) {
        const actions = el('div', 'art-comment-actions');
        const reply = el('button', '', 'Yanıtla');
        reply.type = 'button';
        reply.addEventListener('click', () => setReply(parent));
        actions.appendChild(reply);
        content.appendChild(actions);
      }
      row.appendChild(content);
      thread.appendChild(row);
    });
    list.appendChild(thread);
  }

  function openComments(button) {
    const card = button.closest('.product-card');
    const code = button.dataset.commentCode;
    if (!card || !code) return;
    document.querySelector('.public-comments-overlay')?.remove();
    const overlay = el('div', 'public-comments-overlay');
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    const panel = el('section', 'public-comments-panel');
    const close = el('button', 'public-comments-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Kapat');
    const head = el('header', 'public-comments-head');
    const source = card.querySelector('.art-frame img');
    if (source) {
      const image = el('img', 'public-comments-art');
      image.src = source.src;
      image.alt = source.alt || '';
      head.appendChild(image);
    }
    const heading = el('div', '');
    const title = card.querySelector('h3')?.textContent || 'Eser';
    const size = card.querySelector('.product-info > p')?.textContent || '';
    heading.appendChild(el('span', 'eyebrow', 'ATÖLYEDEN BİR ESER'));
    heading.appendChild(el('h2', '', title));
    heading.appendChild(el('p', 'art-detail-code', `${code}${size ? ' · ' + size : ''}`));
    head.appendChild(heading);
    const main = el('div', 'public-comments-main');
    const commentHeading = el('div', 'art-comments-head');
    commentHeading.appendChild(el('h3', '', 'Yorumlar'));
    const count = el('span', 'art-comments-count', 'Yorumlar yükleniyor…');
    commentHeading.appendChild(count);
    main.appendChild(commentHeading);
    const list = el('div', 'art-comment-list');
    main.appendChild(list);
    const form = el('form', 'public-comment-form');
    const formHead = el('div', 'art-comment-form-head');
    const formTitle = el('strong', '', 'Yorumunu yaz');
    const cancel = el('button', 'art-comment-cancel', 'Yanıtı iptal et');
    cancel.type = 'button';
    cancel.hidden = true;
    formHead.append(formTitle, cancel);
    form.appendChild(formHead);
    const notice = el('p', 'art-comment-reply-notice', '');
    notice.hidden = true;
    form.appendChild(notice);
    const names = el('div', 'art-comment-name-fields');
    function nameField(labelText, name, autocomplete) {
      const label = el('label', '', labelText);
      const input = el('input');
      input.type = 'text';
      input.name = name;
      input.maxLength = 60;
      input.required = true;
      input.autocomplete = autocomplete;
      label.appendChild(input);
      names.appendChild(label);
      return input;
    }
    const first = nameField('İsim', 'first_name', 'given-name');
    const last = nameField('Soyisim', 'last_name', 'family-name');
    try {
      first.value = localStorage.getItem('gallery-comment-first-name') || '';
      last.value = localStorage.getItem('gallery-comment-last-name') || '';
    } catch (_) {}
    form.appendChild(names);
    const bodyLabel = el('label', '', 'Yorum');
    const body = el('textarea');
    body.name = 'body';
    body.rows = 3;
    body.maxLength = 1600;
    body.required = true;
    body.placeholder = 'Bu eser sende nasıl bir his uyandırdı?';
    bodyLabel.appendChild(body);
    form.appendChild(bodyLabel);
    const photoRow = el('div', 'art-comment-photo-row');
    const preview = el('div', 'art-comment-avatar-preview', 'PB');
    const photoLabel = el('label', '', 'Profil fotoğrafı ekle (isteğe bağlı)');
    const photo = el('input');
    photo.type = 'file';
    photo.accept = 'image/png,image/jpeg,image/webp';
    photoLabel.appendChild(photo);
    photoRow.append(preview, photoLabel);
    form.appendChild(photoRow);
    const status = el('p', 'art-comment-status', '');
    status.setAttribute('role', 'status');
    form.appendChild(status);
    const submit = el('button', 'art-comment-submit', 'Yorumu paylaş');
    submit.type = 'submit';
    form.appendChild(submit);
    main.appendChild(form);
    panel.append(close, head, main);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    let parentId = null;
    function setReply(parent) {
      parentId = parent.id;
      formTitle.textContent = 'Yanıt yazıyorsun';
      notice.textContent = `${parent.first_name} ${parent.last_name} adlı kişinin yorumuna yanıt veriyorsun.`;
      notice.hidden = false;
      cancel.hidden = false;
      body.focus();
      form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    function clearReply() {
      parentId = null;
      formTitle.textContent = 'Yorumunu yaz';
      notice.hidden = true;
      cancel.hidden = true;
    }
    cancel.addEventListener('click', clearReply);
    function load() {
      list.replaceChildren(el('p', 'art-comments-loading', 'Yorumlar yükleniyor…'));
      fetch('/api/comments?code=' + encodeURIComponent(code), { cache: 'no-store' })
        .then((response) => response.json().then((data) => {
          if (!response.ok) throw new Error(data.error || 'Yorumlar alınamadı.');
          return data;
        }))
        .then((data) => {
          const rows = data.comments || [];
          count.textContent = rows.length + ' yorum';
          updateCount(code, rows.length);
          list.replaceChildren();
          const roots = rows.filter((row) => !row.parent_id);
          if (!roots.length) list.appendChild(el('p', 'art-comments-empty', 'Henüz yorum yok. İlk yorumu sen bırak.'));
          roots.forEach((root) => renderThread(root, rows.filter((row) => row.parent_id === root.id), list, setReply));
        })
        .catch(() => list.replaceChildren(el('p', 'art-comments-empty', 'Yorumlar şu anda yüklenemedi.')));
    }
    load();
    photo.addEventListener('change', () => {
      const file = photo.files?.[0];
      if (!file) { preview.textContent = 'PB'; return; }
      if (file.size > 2 * 1024 * 1024) {
        photo.value = '';
        status.textContent = 'Profil fotoğrafı en fazla 2 MB olabilir.';
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const image = el('img');
        image.src = reader.result;
        image.alt = 'Profil fotoğrafı önizlemesi';
        preview.replaceChildren(image);
      };
      reader.readAsDataURL(file);
    });
    function readFile(file) {
      return new Promise((resolve, reject) => {
        if (!file) return resolve('');
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ''));
        reader.onerror = () => reject(new Error('Fotoğraf okunamadı.'));
        reader.readAsDataURL(file);
      });
    }
    form.addEventListener('submit', (event) => {
      event.preventDefault();
      if (!form.reportValidity()) return;
      submit.disabled = true;
      status.textContent = 'Yorum gönderiliyor…';
      readFile(photo.files?.[0]).then((avatar) => fetch('/api/comments', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, first_name: first.value, last_name: last.value, body: body.value, parent_id: parentId, visitor, avatar_data: avatar })
      })).then((response) => response.json().then((data) => {
        if (!response.ok) throw new Error(data.error || 'Yorum gönderilemedi.');
        return data;
      })).then((data) => {
        try {
          localStorage.setItem('gallery-comment-first-name', first.value.trim());
          localStorage.setItem('gallery-comment-last-name', last.value.trim());
        } catch (_) {}
        body.value = '';
        photo.value = '';
        preview.textContent = initials({ first_name: first.value, last_name: last.value });
        clearReply();
        status.textContent = 'Yorumun paylaşıldı.';
        updateCount(code, data.count);
        load();
      }).catch((error) => { status.textContent = error.message || 'Yorum gönderilemedi.'; })
        .finally(() => { submit.disabled = false; });
    });
    function dismiss() {
      document.removeEventListener('keydown', onKey);
      overlay.remove();
    }
    function onKey(event) { if (event.key === 'Escape') dismiss(); }
    close.addEventListener('click', dismiss);
    overlay.addEventListener('click', (event) => { if (event.target === overlay) dismiss(); });
    document.addEventListener('keydown', onKey);
    close.focus();
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('.comment-button');
    if (!button) return;
    event.preventDefault();
    openComments(button);
  });

  fetch('/api/comments?counts=1', { cache: 'no-store' })
    .then((response) => response.json())
    .then((data) => Object.entries(data.counts || {}).forEach(([code, count]) => updateCount(code, count)))
    .catch(() => {});
})();
