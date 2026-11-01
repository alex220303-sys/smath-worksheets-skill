# Как выложить этот репозиторий на GitHub

Инструкция для человека, у которого **на компьютере нет git**. Три пути — от
самого простого к «правильному». Достаточно любого одного.

Что заливаем: папка `E:\AI\smath-worksheets-skill` — 15 файлов, ~400 КБ
(README, LICENSE, SKILL.md, install.py, папки `lib`, `scripts`, `references`,
`examples`, `docs`).

---

## Что понадобится

1. Аккаунт GitHub — регистрация на <https://github.com/signup> (нужна только
   почта, бесплатно).
2. Папка `E:\AI\smath-worksheets-skill` — она уже готова, ничего собирать не надо.
3. Для варианта В — установленный Git (ссылка в разделе).

Проверить, что в папке лежит всё нужное (необязательно, но полезно):

```powershell
Get-ChildItem E:\AI\smath-worksheets-skill -Recurse -File | Select-Object Name
```

Должно быть 15 строк, среди них `SKILL.md`, `README.md`, `LICENSE`, `install.py`,
`lib\smscript.py`, `examples\minimal.sm`, два png в `docs`.

---

## Вариант А — через сайт GitHub (без git, 3–5 минут)

### Шаг 1. Создать пустой репозиторий

1. Откройте <https://github.com/new>.
2. Заполните поля:
   * **Repository name:** `smath-worksheets-skill`
   * **Description:** `Agent skill for SMath Studio: .sm worksheets that actually open, with dot subscripts and visible results (verified on 1.5.0.9678)`
   * **Public** (для портфолио) или **Private** (только для себя) — на ваш выбор.
   * **Initialize this repository with:** оставьте **все галочки пустыми**
     (README, .gitignore и license в папке уже есть — иначе получится конфликт
     и придётся разбираться с merge).
3. Нажмите зелёную кнопку **Create repository**.

### Шаг 2. Загрузить файлы

Откроется страница «Quick setup». На ней ищите ссылку
**uploading an existing file** (она в блоке «…or push an existing file from the
command line» / «Get started by creating a new file»). Нажмите её.

1. Откроется страница **Upload files** с большой пунктирной областью
   «Drag files here to add them to your repository».
2. Откройте проводник: `Win+E` → вставьте в адресную строку
   `E:\AI\smath-worksheets-skill`.
3. Выделите **всё содержимое** (`Ctrl+A`) и перетащите в браузер на пунктирную
   область.
   * Важно: перетаскивать надо **папки целиком** (`lib`, `scripts`, `references`,
     `examples`, `docs`) вместе с файлами — структура папок сохранится сама.
   * `.gitignore` — файл скрытый; если `Ctrl+A` его не захватил, включите показ
     скрытых файлов (вкладка «Вид» в проводнике → «Показать» → «Скрытые
     элементы») и перетащите отдельно.
4. Дождитесь, пока список файлов перестанет меняться (браузер считает файлы).
5. Внизу в поле **Commit changes** напишите:
   `Initial commit: SMath Studio worksheet skill (.sm format 0.88, dot subscripts, visible results)`
6. Нажмите **Commit changes**.

Готово — репозиторий опубликован по адресу
`https://github.com/<ваш-логин>/smath-worksheets-skill`.

### Шаг 3. Проверить, что всё на месте

На главной странице репозитория должно быть видно: `README.md` (отрендеренный,
с картинками!), папки `lib`, `scripts`, `references`, `examples`, `docs`, файлы
`SKILL.md`, `LICENSE`, `install.py`, `.gitignore`.

Если README отображается без картинок — почти всегда потому, что папка `docs`
не загрузилась: повторите шаг 2, перетащив её отдельно.

### Шаг 4. Заполнить поля репозитория

1. Кнопка **⚙ (Settings)** справа от «About» на главной странице, либо
   `https://github.com/<логин>/smath-worksheets-skill` → шестерёнка справа.
2. **Description:** как в шаге 1.
3. **Website:** можно оставить пустым.
4. **Topics** (по одному, через Enter): `smath`, `smath-studio`, `agent-skill`,
   `claude-code`, `deepseek-harness`, `engineering-calculations`, `python`.
5. **Save changes**.

---

## Вариант Б — GitHub Desktop (GUI, удобно обновлять потом)

1. Скачайте <https://desktop.github.com/> и установите (Windows, ~2 минуты).
2. Войдите своим аккаунтом GitHub (кнопка **Sign in to GitHub.com**).
3. **File → Add local repository…** → **Choose…** → укажите
   `E:\AI\smath-worksheets-skill`.
   Появится подсказка «this directory does not appear to be a Git repository» —
   нажмите **create a repository**.
4. В поле **Name** оставьте `smath-worksheets-skill`, нажмите **Create repository**.
5. Слева появятся все файлы как «Changes» — внизу в поле **Summary** напишите
   `Initial commit`, нажмите **Commit to main**.
6. Сверху нажмите **Publish repository** → при желании снимите галочку
   «Keep this code private» → **Publish repository**.

Дальше любые правки: изменили файлы → в GitHub Desktop появились изменения →
**Commit to main** → **Push origin**. Это самый быстрый способ обновлять
репозиторий без командной строки.

---

## Вариант В — git в PowerShell (если хотите классический путь)

1. Установите Git for Windows: <https://git-scm.com/download/win> (все галочки
   по умолчанию). Перезапустите PowerShell.
2. Создайте токен вместо пароля: GitHub → **Settings → Developer settings →
   Personal access tokens → Tokens (classic) → Generate new token (classic)**,
   scope `repo`, срок 30 дней. Скопируйте токен (он показывается один раз).
3. Выполните:

```powershell
cd E:\AI\smath-worksheets-skill
git init
git add .
git commit -m "Initial commit: SMath Studio worksheet skill"
git branch -M main
git remote add origin https://github.com/<ваш-логин>/smath-worksheets-skill.git
git push -u origin main
```

4. На запрос логина введите свой **логин GitHub**, на запрос пароля — вставьте
   **токен** (не пароль от аккаунта).

Если репозиторий создавали через сайт с README — сначала
`git pull --rebase origin main`, иначе push отклонится с
`rejected — non-fast-forward`.

---

## Как обновлять репозиторий потом

| Вариант | Действия |
|---|---|
| Сайт | Страница файла → карандаш ✏ (Edit) → изменить → **Commit changes**. Для новых файлов: **Add file → Upload files**. |
| GitHub Desktop | Изменения появятся сами → Summary → **Commit to main** → **Push origin**. |
| git | `git add .` → `git commit -m "что изменил"` → `git push` |

Для этого проекта важное правило: правки делайте в `E:\AI\.dsh-skills\smath-worksheets`
(это источник правды), затем копируйте в `E:\AI\smath-worksheets-skill` и
коммитьте — иначе версии скилла и репозитория разъедутся.

---

## Бонус: релиз с zip-архивом (2 минуты)

Нужен, чтобы скилл можно было ставить одной командой из архива:

1. В проводнике: правый клик по папке `E:\AI\smath-worksheets-skill` →
   **Отправить → Сжатая ZIP-папка**.
2. GitHub → ваш репозиторий → **Releases → Create a new release**.
3. **Choose a tag:** `v1.0.0` → **Create new tag on publish**.
4. **Release title:** `v1.0.0 — первый рабочий выпуск`.
5. Опишите в двух строках, что внутри.
6. Прикрепите zip в **Attach binaries** → **Publish release**.

Установка из такого архива:

```powershell
# распаковать и запустить
python install.py
```

---

## Частые проблемы

| Симптом | Причина и решение |
|---|---|
| При перетаскивании папки загрузились только файлы верхнего уровня | Перетаскивайте **папки**, а не их содержимое: `lib`, `scripts`, `references`, `examples`, `docs` — каждая должна быть в списке загрузки. |
| `.gitignore` не загрузился | Файл скрытый — включите показ скрытых элементов в проводнике, перетащите отдельно. |
| Картинки в README не отображаются | Не загрузилась папка `docs` или изменились имена файлов (`docs/smath-zadanie1.png`). |
| `git push` просит пароль и не принимает | Нужен Personal Access Token (см. вариант В, п. 2), либо GitHub Desktop/сайт. |
| `rejected — non-fast-forward` | В удалённом репозитории уже есть коммиты: сначала `git pull --rebase origin main`. |
| GitHub пишет про 2FA | Включите двухфакторную аутентификацию в настройках аккаунта — GitHub её требует для push. |
| Не хочется публиковать картинки-скриншоты | Удалите `docs/` перед загрузкой и уберите таблицу «Как это выглядит» из `README.md`. |

**Проверка на секреты:** в папке нет токенов, ключей и `.env` — только код,
документация и скриншоты. Быстрая проверка перед публикацией:

```powershell
Get-ChildItem E:\AI\smath-worksheets-skill -Recurse -File |
  Where-Object Name -ne 'PUBLISH.md' |
  Select-String -Pattern 'ghp_|github_pat_|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|PRIVATE KEY'
```

Совпадений быть не должно (`PUBLISH.md` исключён, потому что содержит сам этот
шаблон). Слова вроде «token» встречаются в коде легитимно — `smread.py` разбирает
*токены* формул, поэтому искать надо по форматам секретов, а не по словам.
