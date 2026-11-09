# Установка BlackoutMonitor через LuCI (OpenWrt 25.12.6)

Пакет `luci-app-blackout-monitor` включает оба раздела: SmartMeterMonitor и BlackoutMonitor. Предназначен для OpenWrt 25.12.6 на x86_64 с пакетным менеджером `apk`.

## Настроить сборку один раз

1. В репозитории GitHub открой **Settings → Secrets and variables → Actions → New repository secret**. Имя: `APK_SIGN_KEY`. Вставь **полное содержимое приватного EC P-256 PEM** из отдельно переданного владельцу файла. Никогда не коммить этот файл.
2. Запусти **Actions → OpenWrt APK → Run workflow** и проверь, что сборка успешно создала пакет и ветку `gh-pages`.
3. В **Settings → Pages → Build and deployment** выбери **Deploy from a branch → gh-pages → /(root)**.

После публикации индекс доступен по адресу:

`https://garik816.github.io/BlackoutMonitor/releases/25.12/x86_64/packages.adb`

## Подключить подписанный feed к OpenWrt

После успешной публикации выполни по SSH:

```sh
wget -O /tmp/add-blackout-feed.sh https://raw.githubusercontent.com/garik816/BlackoutMonitor/main/scripts/add-apk-feed.sh
cat /tmp/add-blackout-feed.sh
sh /tmp/add-blackout-feed.sh
```

Затем в **LuCI → System → Software** нажми **Update lists**, найди `luci-app-blackout-monitor` и **Install**.

CLI-альтернатива: `apk add luci-app-blackout-monitor`.

Оба интерфейса появятся в **Services**. При последующих сборках пакет можно обновлять штатным образом. Не запускай глобальный `apk upgrade` ради этого приложения.

## Сохранение данных

Активная `/etc/config/smartmeter-availability` не включена в пакет и не перезаписывается. При первой установке создаётся конфигурация с отключённой проверкой `main`: укажи реальный адрес устройства перед включением.

Базы SQLite в `/root/*.sqlite3` не принадлежат пакету и сохраняются при его обновлении или удалении. Перед первой установкой поверх файлов, ранее скопированных вручную, создай резервную копию. При sysupgrade базы нужно резервировать отдельно.

## Диагностика

```sh
apk --print-arch
apk policy luci-app-blackout-monitor
/etc/init.d/smartmeter-availability status
/etc/init.d/svitlo-schedule status
```

Ошибка `UNTRUSTED signature` означает, что публичный ключ в `/etc/apk/keys/blackout-monitor.pem` не соответствует индексу. HTTP 404 означает, что GitHub Pages/`gh-pages` ещё не опубликованы.
