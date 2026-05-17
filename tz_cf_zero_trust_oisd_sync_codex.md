# Техническое задание для Codex

## Название проекта

`cf-zt-oisd-sync`

## Цель

Разработать CLI-программу, которая автоматически загружает официальный список OISD small, нормализует домены, разбивает их на части до 1000 записей, создаёт в Cloudflare Zero Trust несколько reusable domain lists и создаёт DNS Gateway правило блокировки по этим спискам.

Также программа должна уметь:

1. создавать списки и правило с нуля;
2. обновлять уже созданные списки;
3. пакетно удалять все списки и правило, созданные этой программой;
4. показывать статус текущей установки;
5. работать в безопасном режиме dry-run.

---

# Важный контекст

OISD имеет несколько списков, включая oisd big, oisd small, oisd nsfw, oisd nsfw small; oisd small в официальном описании mainly focuses on blocking ads.

Для Cloudflare Zero Trust reusable lists нужно использовать тип списка DOMAIN.

У Cloudflare Zero Trust lists есть ограничение: до 1000 entries для Standard/free-подобных планов и до 5000 для Enterprise.

Для API авторизации использовать Cloudflare API Token, желательно не Global API Key.

---

# Официальный источник OISD

Использовать только официальный источник OISD small.

Базовый источник по умолчанию:

```text
https://small.oisd.nl
```

Дополнительно предусмотреть настройку `OISD_SOURCE_URL`, чтобы при необходимости можно было заменить источник на другой официальный формат OISD.

Программа должна валидировать загруженный список и не загружать мусорные строки в Cloudflare.

---

# Язык и стек

Предпочтительно Python 3.11+.

Рекомендуемые библиотеки:

```text
requests или httpx
python-dotenv
pydantic или dataclasses
typer или argparse
rich для красивого CLI-вывода
idna для punycode/IDN-нормализации
pytest для тестов
```

Код должен быть модульным, без хардкода токенов и account_id.

---

# Конфигурация

Программа должна читать настройки из `.env` и/или переменных окружения.

Обязательные переменные:

```text
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
```

Опциональные переменные:

```text
OISD_SOURCE_URL=https://small.oisd.nl
LIST_PREFIX=oisd-small-auto
RULE_NAME=OISD Small Auto Block
CHUNK_SIZE=1000
RULE_PRECEDENCE=5000
STATE_FILE=.cf-zt-oisd-state.json
DRY_RUN=false
```

---

# CLI-команды

Реализовать команды:

```text
cf-zt-oisd-sync init
```

Создаёт списки и DNS blocking rule с нуля.

```text
cf-zt-oisd-sync update
```

Заново загружает OISD small, нормализует домены, сравнивает с текущим состоянием и обновляет списки.

```text
cf-zt-oisd-sync delete
```

Удаляет все списки и правило, созданные программой.

```text
cf-zt-oisd-sync status
```

Показывает:

```text
количество локальных доменов после обработки
количество чанков
найденные Cloudflare lists
найденное Cloudflare rule
дата последнего обновления
расхождение между state-файлом и Cloudflare
```

```text
cf-zt-oisd-sync dry-run
```

Выполняет полный процесс без изменений в Cloudflare.

---

# Формат state-файла

Программа должна хранить локальное состояние в JSON-файле.

Пример структуры:

```json
{
  "managed_by": "cf-zt-oisd-sync",
  "list_prefix": "oisd-small-auto",
  "rule_name": "OISD Small Auto Block",
  "source_url": "https://small.oisd.nl",
  "chunk_size": 1000,
  "last_sync_at": "2026-05-08T12:00:00Z",
  "source_hash": "sha256...",
  "domain_count": 12345,
  "chunks": [
    {
      "index": 1,
      "name": "oisd-small-auto-001",
      "cloudflare_list_id": "uuid",
      "item_count": 1000,
      "chunk_hash": "sha256..."
    }
  ],
  "rule": {
    "name": "OISD Small Auto Block",
    "cloudflare_rule_id": "uuid",
    "precedence": 5000
  }
}
```

---

# Правила именования Cloudflare lists

Каждый список должен называться строго по шаблону:

```text
{LIST_PREFIX}-{index:03d}
```

Пример:

```text
oisd-small-auto-001
oisd-small-auto-002
oisd-small-auto-003
```

Description каждого списка:

```text
Managed by cf-zt-oisd-sync. Source: OISD small. Chunk 001/XYZ. Do not edit manually.
```

---

# Обработка OISD списка

После скачивания нужно:

1. проверить HTTP status code;
2. проверить, что ответ не пустой;
3. обработать строки построчно;
4. убрать пробелы;
5. игнорировать пустые строки;
6. игнорировать комментарии;
7. игнорировать строки с #, !, [, ], @@, ||;
8. убрать возможные префиксы вроде 0.0.0.0 и 127.0.0.1;
9. убрать trailing dot;
10. привести домены к lowercase;
11. убрать wildcard-префиксы *. и ||;
12. убрать символы /, ^, $important;
13. пропускать строки, которые не похожи на домены;
14. преобразовать IDN-домены в punycode через idna;
15. удалить дубликаты;
16. отсортировать результат для стабильного diff/hash;
17. разбить на чанки по CHUNK_SIZE.

Важно: Cloudflare domain lists должны получать элементы в формате:

```json
[
  {"value": "example.com"},
  {"value": "ads.example.net"}
]
```

---

# Cloudflare API client

Сделать отдельный модуль Cloudflare API client.

Нужные методы:

```text
list_gateway_lists()
get_gateway_list(list_id)
create_gateway_list(name, description, type, items)
update_gateway_list(list_id, name, description, type, items)
delete_gateway_list(list_id)
list_gateway_rules()
create_gateway_rule(...)
update_gateway_rule(rule_id, ...)
delete_gateway_rule(rule_id)
```

Все запросы должны использовать:

```text
Authorization: Bearer {CLOUDFLARE_API_TOKEN}
Content-Type: application/json
```

---

# Логика создания

Команда `init` должна:

1. скачать OISD small;
2. нормализовать домены;
3. разбить на чанки;
4. проверить, нет ли уже списков с таким LIST_PREFIX;
5. создать Cloudflare DOMAIN list для каждого чанка;
6. сохранить ID созданных списков в state-файл;
7. создать одно DNS Gateway rule, которое блокирует все созданные списки;
8. сохранить rule ID в state-файл.

---

# DNS rule

Создать одно правило:

```json
{
  "name": "OISD Small Auto Block",
  "description": "Blocks domains from OISD small. Managed by cf-zt-oisd-sync.",
  "precedence": 5000,
  "enabled": true,
  "action": "block",
  "filters": ["dns"],
  "traffic": "any(dns.domains[*] in $LIST_UUID_1) or any(dns.domains[*] in $LIST_UUID_2)"
}
```

Если Cloudflare API не принимает очень длинное выражение traffic, предусмотреть fallback.

---

# Логика обновления

Команда `update` должна:

1. скачать свежий OISD small;
2. нормализовать и разбить на чанки;
3. сравнить source_hash и chunk_hash;
4. если список не изменился — ничего не делать;
5. если количество чанков такое же — обновить только изменившиеся списки;
6. если чанков стало больше — создать недостающие списки и обновить DNS rule;
7. если чанков стало меньше — удалить лишние списки и обновить DNS rule;
8. обновить state-файл только после успешного завершения всех операций.

---

# Логика удаления

Команда `delete` должна:

1. найти rule по state-файлу или по имени RULE_NAME;
2. удалить rule;
3. найти все lists по state-файлу или по LIST_PREFIX;
4. удалить все найденные lists;
5. удалить локальный state-файл;
6. вывести отчёт.

Перед удалением запросить подтверждение:

```text
Type DELETE to confirm:
```

Добавить флаг:

```text
--yes
```

---

# Dry-run

Любая изменяющая команда должна поддерживать:

```text
--dry-run
```

В этом режиме программа ничего не создаёт, не обновляет и не удаляет в Cloudflare.

---

# Безопасность

Не логировать Cloudflare API Token.

Не сохранять токен в state-файл.

Добавить защиту от удаления чужих списков.

---

# Обработка ошибок

Программа должна понятно обрабатывать:

```text
нет CLOUDFLARE_API_TOKEN
нет CLOUDFLARE_ACCOUNT_ID
OISD недоступен
OISD вернул пустой список
Cloudflare вернул 401/403
Cloudflare вернул лимит/ошибку валидации
Cloudflare не принял traffic expression
state-файл повреждён
часть списков уже существует
rule уже существует
```

---

# Тесты

Добавить unit-тесты для:

```text
парсинга plain-domain списка
парсинга hosts-формата
парсинга adblock-style строк
удаления комментариев
удаления wildcard-префиксов
валидации доменов
punycode-конвертации
удаления дубликатов
разбиения на чанки по 1000
формирования Cloudflare list payload
формирования DNS traffic expression
обновления state-файла
```

---

# Документация

Создать README.md с разделами:

```text
Назначение
Требования
Как создать Cloudflare API Token
Как найти Cloudflare Account ID
Установка
Настройка .env
Первый запуск
Обновление списков
Удаление списков
Автоматический запуск по расписанию
Troubleshooting
```

---

# Автоматизация

Предусмотреть пример запуска по расписанию.

### Windows Task Scheduler

```text
python -m cf_zt_oisd_sync update
```

### Linux cron

```text
0 4 * * * /usr/bin/python3 -m cf_zt_oisd_sync update
```

### GitHub Actions

Добавить пример workflow, который запускает update раз в сутки.

---

# Критерии готовности

Проект считается готовым, если:

```text
init создаёт Cloudflare DOMAIN lists и DNS blocking rule
update корректно обновляет списки без дубликатов
delete удаляет только созданные программой ресурсы
dry-run показывает план без изменений
state-файл создаётся и обновляется
токены не попадают в логи
есть README
есть тесты парсинга и Cloudflare payload
```

---

# Важное замечание для реализации

Не писать решение как одноразовый скрипт. Нужна нормальная структура проекта:

```text
cf_zt_oisd_sync/
  __init__.py
  cli.py
  config.py
  oisd.py
  normalize.py
  cloudflare.py
  state.py
  sync.py
tests/
README.md
.env.example
pyproject.toml
```

Код должен быть читаемым, с понятными ошибками и без жёстко прошитых значений.

