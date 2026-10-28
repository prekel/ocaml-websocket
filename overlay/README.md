# WebSocket Lwt: готовые пакеты для opam overlay

Два независимых каталога для копирования в `packages/websocket-lwt-unix/`
вашего overlay-репозитория. В каждом уже есть полный `opam`, официальный URL
архива, его checksum, `patches`, `extra-files` с SHA256 и `files/` с патчем.

| Каталог | Назначение |
| --- | --- |
| `packages/websocket-lwt-unix/websocket-lwt-unix.2.15` | Замена Lwt-части форка NightBlues на `a4811557e51661f05e963688b3be88207691c2ec` |
| `packages/websocket-lwt-unix/websocket-lwt-unix.2.17` | Обновление на релиз 2.17 с тем же исправлением |

## Копирование и установка

Из корня этого checkout:

```sh
overlay_repo=/path/to/corporate-opam-overlay
mkdir -p "$overlay_repo/packages/websocket-lwt-unix"
cp -R overlay/packages/websocket-lwt-unix/websocket-lwt-unix.2.15 "$overlay_repo/packages/websocket-lwt-unix/"
cp -R overlay/packages/websocket-lwt-unix/websocket-lwt-unix.2.17 "$overlay_repo/packages/websocket-lwt-unix/"
```

Далее в нужном switch обновить подключённый корпоративный репозиторий
(`corp-overlay` — его имя в `opam repository list`) и снять существующие git pins:

```sh
opam update corp-overlay
opam pin list
# Указать только действительно закреплённые пакеты:
opam pin remove --no-action websocket-lwt-unix websocket
opam install websocket.2.15 websocket-lwt-unix.2.15
```

Если та же версия уже установлена, выполнить
`opam reinstall websocket-lwt-unix.2.15`, чтобы пересобрать её с патчем.
Для обновления выбрать `opam install websocket.2.17 websocket-lwt-unix.2.17`.
Ограничение `websocket {= version}` в metadata обеспечивает согласованность версий.
Базовый `websocket` берётся из обычного opam-repository. Версии пакетов
намеренно совпадают с официальными: overlay должен иметь приоритет над обычным
репозиторием. Обновить корпоративные `.opam` и lock-файлы, если в них есть git URL.

Каталог `overlay/` также является самостоятельным opam-репозиторием:

```sh
opam repository add websocket-overlay ./overlay
```

## Поведение и происхождение

Патчи переносят [исправление NightBlues](https://github.com/NightBlues/ocaml-websocket/commit/a4811557e51661f05e963688b3be88207691c2ec):
`Lwt.Canceled` при чтении передаётся вызывающему коду без закрытия входного канала.
Можно начать следующее чтение через то же соединение. Остальные исключения
обрабатываются как в соответствующем релизе. Публичный API не меняется.

Metadata и checksum взяты из официального opam-repository; архивы соответствуют
релизам [2.15](https://github.com/vbmithr/ocaml-websocket/releases/tag/2.15) и
[2.17](https://github.com/vbmithr/ocaml-websocket/releases/tag/2.17).
В старом наборе пропатченный `lwt/websocket_lwt_unix.ml` точно совпадает с `a481155`.
Изменения Async/Core v0.15 из форка исключены: этот комплект предназначен для Lwt.

Официальные ограничения совместимости Cohttp/Conduit сохранены.
Переход на 2.17 меняет генератор случайных чисел на Mirage Crypto:
если приложение использует стандартный `random_string`, оно должно
инициализировать Mirage Crypto RNG согласно используемой версии.
Тест использует явно переданный детерминированный RNG только для loopback-проверки.

## Проверка

Python >= 3.12, opam и patch должны быть доступны в PATH.

```sh
python3 scripts/verify-overlay.py --check-only
python3 scripts/verify-overlay.py --set legacy --switch=/path/to/legacy-switch
python3 scripts/verify-overlay.py --set latest --switch=/path/to/latest-switch
```

Switch должен содержать зависимости соответствующей версии, включая обычный
`websocket` той же версии. Скрипт ничего в switch не устанавливает, собирает
исходники и отдельные тесты во временном каталоге. Не устанавливайте каталог
overlay-пакета как локальные исходники: используйте подключённый overlay и
имя пакета с версией, чтобы opam скачал официальный архив из `url`.

Проверяются lint, checksum архива и патча, применение без fuzz/offsets, сборка
production-пакета и настоящий обмен через loopback TCP. Независимый Python peer
дожидается отмены чтения, затем отправляет сообщение и принимает ответ через
то же соединение. Отдельно проверяются обычный EOF, повторная ошибка чтения
и явное закрытие транспорта.
Проверка отмены выполняется до поступления байтов следующего фрейма.
Тесты в production-патчи не входят.

Контрольный запуск этого же теста на чистом 2.17 без патча воспроизводит
ошибку повторного чтения после отмены; пропатченная версия проходит.

Проверены на OCaml 4.14.1 / Conduit 6.2.3 и OCaml 5.5.0 / Conduit 7.0.0,
с Cohttp Lwt Unix 5.3.0 и Lwt 5.10.1. Пакеты также установлены штатным opam
из локального overlay с `--with-test`. Сборка корпоративного приложения
остаётся отдельной проверкой.
