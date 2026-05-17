# cf-zt-oisd-sync

Эта программа скачивает официальный список `OISD small` и добавляет домены из него в Cloudflare Zero Trust Gateway как reusable DOMAIN lists. Затем она создаёт DNS Gateway rule, которое блокирует эти домены.

Программа не изменяет существующие Cloudflare policies, если они не были созданы этой программой.

## Самый короткий путь

Если хочется, чтобы оно "просто работало", общий порядок такой:

1. Откройте папку проекта в терминале.
2. Установите Python и зависимости.
3. Запустите `python run.py`.
4. Выберите пункт `1`, чтобы создать `.env`.
5. Выберите пункт `2`, чтобы проверить подключение.
6. Выберите пункт `3`, чтобы посмотреть план без изменений.
7. Если план выглядит нормально, выберите пункт `4`.
8. Для последующих обновлений снова запускайте `python run.py` и выбирайте пункт `4`.

Команды ниже можно выполнять по порядку.

## Установка зависимостей

В папке проекта выполните:

```bash
python3 -m pip install -e .
```

В Windows PowerShell обычно можно так:

```powershell
python -m pip install -e .
```

## Самый простой запуск через меню

После установки зависимостей запустите:

```bash
python run.py
```

В WSL/Ubuntu иногда команда называется `python3`:

```bash
python3 run.py
```

Вы увидите меню:

```text
1. Первичная настройка (.env)
2. Проверить подключение Cloudflare и OISD
3. Dry-run: показать план без изменений
4. Создать или обновить списки и правило блокировки
5. Показать статус
6. Удалить созданные объекты
7. Диагностика проблем
0. Выход
```

Введите номер пункта и нажмите `Enter`. Например, для первого запуска обычно идут так:

```text
1 -> 2 -> 3 -> 4 -> 5
```

То есть: настроить, проверить, посмотреть план, применить, проверить статус.

Если программа установлена как CLI-команда, это же меню можно открыть так:

```bash
cf-zt-oisd-sync menu
```

## Какую папку открыть

Откройте именно папку проекта:

```text
C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater
```

Если вы работаете в WSL/Linux, тот же путь выглядит так:

```text
/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater
```

В этой папке должны быть файлы:

```text
README.md
pyproject.toml
.env.example
cf_zt_oisd_sync/
tests/
```

## Чем открыть папку

Подойдут любые варианты:

- Windows Terminal;
- PowerShell;
- Ubuntu/WSL terminal;
- VS Code: `File -> Open Folder`, затем `Terminal -> New Terminal`.

Если вы не уверены, проще всего открыть VS Code, выбрать папку проекта и открыть встроенный терминал.

## Как перейти в папку проекта

В WSL/Ubuntu:

```bash
cd "/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater"
```

В PowerShell:

```powershell
cd "C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater"
```

## Установка Python

Проверьте, есть ли Python:

```bash
python3 --version
```

Или в Windows PowerShell:

```powershell
py --version
```

Нужен Python 3.11 или новее.

Если Python не установлен, установите его с официального сайта:

```text
https://www.python.org/downloads/
```

На Windows во время установки включите галочку `Add python.exe to PATH`.

## Установка зависимостей

### Вариант A: WSL/Ubuntu

Сначала установите `pip` и модуль виртуального окружения:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
```

Затем в папке проекта выполните:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
```

После `source .venv/bin/activate` в начале строки терминала обычно появляется `(.venv)`. Это нормально: значит, включено отдельное окружение Python для этого проекта.

### Вариант B: Windows PowerShell

В папке проекта выполните:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
```

Если PowerShell не даёт активировать `.venv`, выполните:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

После этого снова:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Настройка Cloudflare

Программе нужны два значения:

- `CLOUDFLARE_ACCOUNT_ID`;
- `CLOUDFLARE_API_TOKEN`.

### Где найти Account ID

1. Откройте Cloudflare dashboard.
2. Выберите нужный account.
3. Обычно `Account ID` виден в правой панели или в разделе account/profile.
4. Скопируйте значение целиком.

### Как создать API token

1. Откройте Cloudflare dashboard.
2. Перейдите в `My Profile -> API Tokens`.
3. Нажмите `Create Token`.
4. Создайте token с правами на Cloudflare Zero Trust Gateway Lists и Gateway Rules.
5. Скопируйте token сразу после создания.

Cloudflare показывает token только один раз. Если вы закрыли страницу и не скопировали token, проще создать новый.

## Создание `.env`

Самый простой способ:

```bash
cf-zt-oisd-sync setup
```

Программа задаст вопросы:

```text
Введите Cloudflare Account ID:
Введите Cloudflare API Token:
Источник OISD small [https://small.oisd.nl]:
Префикс списков [oisd-small-auto]:
Название правила [OISD Small Auto Block]:
Размер части списка [1000]:
```

Для большинства вопросов можно нажимать `Enter` и оставлять значения по умолчанию. Ввести вручную обязательно нужно только `Account ID` и `API Token`.

После этого в папке появится файл `.env`. Это обычный текстовый файл с настройками. Его можно открыть в VS Code или Блокноте, но не публикуйте его в интернет: внутри находится секретный API token.

## Проверка перед запуском

Запустите:

```bash
cf-zt-oisd-sync check
```

Если всё хорошо, вы увидите строки с `[OK]`.

Если видите ошибку про token или права, проверьте:

- правильно ли вставлен `CLOUDFLARE_API_TOKEN`;
- правильно ли вставлен `CLOUDFLARE_ACCOUNT_ID`;
- есть ли у token права на Gateway Lists и Gateway Rules.

## Безопасный предварительный просмотр

Перед реальным созданием объектов выполните:

```bash
cf-zt-oisd-sync dry-run
```

Эта команда ничего не меняет в Cloudflare. Она только показывает, сколько списков будет создано и какое правило появится.

## Первый реальный запуск

Если `dry-run` выглядит нормально:

```bash
cf-zt-oisd-sync init
```

Программа попросит подтверждение. После подтверждения она создаст:

- несколько Cloudflare DOMAIN lists;
- одно DNS Gateway rule;
- локальный state-файл `.cf-zt-oisd-state.json`.

Во время создания вы увидите индикаторы прогресса для списков Cloudflare и DNS Gateway rule. Если списков много, это нормально: Cloudflare принимает их по частям.

State-файл нужен программе, чтобы помнить, какие объекты она создала. Его не нужно редактировать руками.

## Как проверить, что всё работает

Запустите:

```bash
cf-zt-oisd-sync status
```

Хороший результат выглядит примерно так:

```text
[OK] Локальное состояние совпадает с Cloudflare
```

Также можно открыть Cloudflare Zero Trust dashboard и проверить Gateway lists/rules вручную.

## Как обновлять список

Обычное обновление:

```bash
cf-zt-oisd-sync update
```

Для автоматического запуска без вопросов:

```bash
cf-zt-oisd-sync update --yes
```

При обновлении программа тоже показывает прогресс: отдельно для списков и отдельно для правила блокировки.

## Как удалить всё, что создала программа

Интерактивно:

```bash
cf-zt-oisd-sync delete
```

Программа попросит ввести:

```text
DELETE
```

Автоматически, без вопроса:

```bash
cf-zt-oisd-sync delete --yes
```

Удаляются только managed-объекты этой программы: списки с нужным префиксом, объекты из state-файла и объекты с пометкой `Managed by cf-zt-oisd-sync`.

## Что запускать каждый день

Для регулярного обновления нужна команда:

```bash
cf-zt-oisd-sync update --yes
```

### Windows Task Scheduler

Команда для планировщика:

```powershell
python -m cf_zt_oisd_sync.cli update --yes
```

Рабочая папка должна быть папкой проекта:

```text
C:\Users\MAESTRO\Downloads\cloudflare zero trust adblock updater
```

### Linux cron

Пример запуска каждый день в 04:00:

```bash
0 4 * * * cd "/mnt/c/Users/MAESTRO/Downloads/cloudflare zero trust adblock updater" && . .venv/bin/activate && cf-zt-oisd-sync update --yes
```

## Частые вопросы

### Какой файл открыть?

Для инструкции откройте `README.md`.

Для настроек откройте `.env`.

Для просмотра состояния откройте `.cf-zt-oisd-state.json`, но редактировать его обычно не нужно.

### Чем открыть `.env`?

Подойдёт VS Code, Блокнот, Notepad++ или любой текстовый редактор. В VS Code удобнее всего.

### Почему файл `.env` не виден?

Файлы, которые начинаются с точки, иногда считаются скрытыми. В VS Code они обычно видны. В Windows Explorer включите показ скрытых файлов.

### Что делать, если команда `cf-zt-oisd-sync` не найдена?

Скорее всего, не активировано виртуальное окружение.

В WSL/Ubuntu:

```bash
source .venv/bin/activate
```

В PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

После этого снова попробуйте:

```bash
cf-zt-oisd-sync --help
```

### Что делать, если `python3: No module named pip`?

В WSL/Ubuntu установите `pip`:

```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv
```

После этого повторите установку зависимостей.

### Что делать, если Cloudflare вернул `403 Forbidden`?

Это почти всегда означает, что API token не имеет нужных прав. Создайте или обновите token с доступом к Zero Trust Gateway Lists и Gateway Rules.

### Что делать, если я боюсь что-то сломать?

Сначала запустите:

```bash
cf-zt-oisd-sync dry-run
```

Эта команда ничего не меняет. Она только показывает план.

### Можно ли менять `CHUNK_SIZE`?

Обычно оставьте `1000`. Это безопасное значение для Standard/free-подобных планов Cloudflare.

### Что такое `state-файл`?

Это файл `.cf-zt-oisd-state.json`. Программа записывает туда ID созданных списков и правила Cloudflare. Благодаря этому она понимает, что обновлять и что удалять.

### Можно ли удалить state-файл?

Лучше не удалять. Если он пропал, выполните:

```bash
cf-zt-oisd-sync doctor
```

### Как понять, что программа ничего лишнего не удалит?

Команда `delete` ищет только объекты, которые выглядят как созданные этой программой:

- есть в state-файле;
- или имеют нужный префикс;
- или содержат описание `Managed by cf-zt-oisd-sync`.

## Команды для справки

```bash
cf-zt-oisd-sync --help
cf-zt-oisd-sync setup
cf-zt-oisd-sync check
cf-zt-oisd-sync dry-run
cf-zt-oisd-sync init
cf-zt-oisd-sync update
cf-zt-oisd-sync status
cf-zt-oisd-sync delete
cf-zt-oisd-sync doctor
```

## Проверка для разработчика

Если установлены dev-зависимости:

```bash
pytest
```
