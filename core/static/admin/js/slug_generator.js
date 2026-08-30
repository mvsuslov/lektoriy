document.addEventListener('DOMContentLoaded', function() {
    const slugInput = document.getElementById('id_slug');
    if (!slugInput) return;

    // Создаём контейнер для кнопок
    const btnBox = document.createElement('div');
    btnBox.style.cssText = 'margin-top:6px;display:flex;gap:8px;align-items:center;';

    // Кнопка "Сгенерировать"
    const genBtn = document.createElement('button');
    genBtn.type = 'button';
    genBtn.textContent = '🎲 Сгенерировать';
    genBtn.className = 'button';
    genBtn.style.cssText = 'padding:6px 14px;font-size:13px;';
    genBtn.title = 'Случайный адрес для частных занятий';

    // Кнопка "Копировать ссылку"
    const copyBtn = document.createElement('button');
    copyBtn.type = 'button';
    copyBtn.textContent = '📋 Копировать ссылку';
    copyBtn.className = 'button';
    copyBtn.style.cssText = 'padding:6px 14px;font-size:13px;';

    // Текст-подтверждение "Скопировано!"
    const copied = document.createElement('span');
    copied.style.cssText = 'color:#16A34A;font-size:13px;font-weight:600;display:none;';
    copied.textContent = '✓ Скопировано!';

    btnBox.appendChild(genBtn);
    btnBox.appendChild(copyBtn);
    btnBox.appendChild(copied);
    slugInput.parentNode.appendChild(btnBox);

    // Генератор: k7x2-m9f4-p3q8 (3 группы по 4 символа)
    function generateSlug() {
        const chars = 'abcdefghjkmnpqrstuvwxyz23456789'; // без l, o, 0, 1 — чтобы не путать
        const group = () => Array.from({length: 4}, () =>
            chars[Math.floor(Math.random() * chars.length)]).join('');
        return `${group()}-${group()}-${group()}`;
    }

    genBtn.addEventListener('click', function() {
        slugInput.value = generateSlug();
        copied.style.display = 'none';
        // Подсветка, что поле изменилось
        slugInput.style.background = '#F0FDF4';
        setTimeout(() => slugInput.style.background = '', 600);
    });

    copyBtn.addEventListener('click', function() {
        const slug = slugInput.value.trim();
        if (!slug) {
            alert('Сначала введите или сгенерируйте адрес!');
            return;
        }
        const url = `https://phys-it.ru/subjects/${slug}/`;

        // Современный API, fallback для старых браузеров
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url).then(showCopied);
        } else {
            const tmp = document.createElement('textarea');
            tmp.value = url;
            document.body.appendChild(tmp);
            tmp.select();
            document.execCommand('copy');
            document.body.removeChild(tmp);
            showCopied();
        }

        function showCopied() {
            copied.style.display = 'inline';
            setTimeout(() => copied.style.display = 'none', 2500);
        }
    });
});