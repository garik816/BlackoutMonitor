# Установка BlackoutMonitor

[← К проекту](../README.md)

## Требования

Проверенная среда — OpenWrt 25.12.6 x86/64 с LuCI, rpcd и ucode-шаблонами. Нужны Python 3 с SQLite, XML, HTML parser и стандартными модулями, `curl`, `nmap` и `ping`.

На проверенной системе установлены `python3-light`, `python3-sqlite3`, `python3-xml`, `python3-urllib`, `curl`, `nmap`, `luci-base` и `rpcd-mod-file`. Доступные названия пакетов зависят от выпуска OpenWrt.

Проверьте интерпретатор до запуска служб:

```sh
python3 -c 'import sqlite3, html.parser, xml.etree.ElementTree, urllib.parse, fcntl'
```

Настройте часовой пояс роутера на **Europe/Kyiv**. Страница графиков и адаптер используют киевское время, а история доступности записывается в часовом поясе роутера.

## Получить исходники

На компьютере или роутере с установленным Git:

```sh
git clone https://github.com/garik816/BlackoutMonitor.git
cd BlackoutMonitor
```

Если Git на роутере не установлен, можно скачать ZIP репозитория и перенести каталог `files/` на роутер.

## Скопировать файлы

Следующие команды выполняются **на роутере** из корня скачанного проекта:

```sh
cp -a files/. /
chmod 755 /usr/bin/smartmeter-availability   /usr/libexec/smartmeter-availability-dashboard   /usr/libexec/smartmeter-availability-config   /usr/libexec/svitlo-schedule   /usr/libexec/svitlo-schedule-watch   /etc/init.d/smartmeter-availability   /etc/init.d/svitlo-schedule
```

В поставке нет рабочей конфигурации `/etc/config/smartmeter-availability`: только пример с документальным IP-адресом и условным MAC. Существующие настройки не заменяются.

## Только для новой установки

Если файл `/etc/config/smartmeter-availability` отсутствует:

```sh
cp /etc/config/smartmeter-availability.example /etc/config/smartmeter-availability
chmod 600 /etc/config/smartmeter-availability
```

Отредактируйте `main`: укажите реальный адрес и интерфейс устройства. Замените условный MAC либо очистите это поле, если проверка MAC не нужна. Проверка `main` используется как источник факта на странице графиков.

При обновлении существующей установки этот шаг пропускается.

## Включить службы

```sh
/etc/init.d/rpcd reload
/etc/init.d/smartmeter-availability enable
/etc/init.d/smartmeter-availability restart
/etc/init.d/svitlo-schedule enable
/etc/init.d/svitlo-schedule restart
```

Если новые пункты меню не появились, очистите индекс LuCI и перезагрузите страницу:

```sh
rm -f /tmp/luci-indexcache.*.json
```

Откройте:

- **Services → Мониторинг доступности** — настройки и история проверок.
- **Services → Графики отключений** — опубликованный план, факт и аналитика.

## Обновление со SmartMeterMonitor

Перед копированием новой версии сохраните собственную резервную копию конфигурации и баз SQLite. При работе службы используйте SQLite backup API для согласованной копии, а не копирование одного файла без WAL.

Скопируйте файлы как описано выше, пропустите создание конфигурации и перезапустите службы. Идентификатор `main` и его база `/root/smartmeter-availability.sqlite3` сохраняются; другие проверки продолжают использовать свои базы.

## Проверить работу

```sh
/etc/init.d/smartmeter-availability status
/etc/init.d/svitlo-schedule status
/usr/libexec/svitlo-schedule
```

Последняя команда возвращает JSON с графиками и результатом анализа. При ошибке источника она возвращает сообщение и последний корректный график, если он уже сохранён.

Очередь не обязана определиться сразу: для рейтинга нужны и фактические состояния, и графики, сохранённые до соответствующих наблюдений. Минимальные пороги описаны в [методике](ANALYTICS.md).

## Данные на роутере

| Путь | Назначение |
| --- | --- |
| `/etc/config/smartmeter-availability` | Параметры проверок |
| `/root/smartmeter-availability.sqlite3` | История `main` |
| `/root/smartmeter-<id>.sqlite3` | История остальных проверок |
| `/root/svitlo-schedule.sqlite3` | Архив редакций графиков, 90 дней |
| `/tmp/svitlo-schedule/` | Временный кеш HTTP и блокировка |

После перезагрузки служб или роутера архив остаётся на диске. Временный HTTP-кеш пересоздаётся. Сохранение этих дополнительных файлов при **перепрошивке OpenWrt** нужно настроить отдельно в механизме резервирования конфигурации.
