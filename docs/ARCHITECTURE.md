# Архитектура

```text
Инженер + Codex + AGENTS.md + .agents/skills/
  ├─ python -m agent                       [offline / credential-free]
  │    ├─ local XLSX / saved HTML -> exact typed identity
  │    ├─ exact ReadGrant -> supported typed checks
  │    ├─ FixtureDiagnostics -> observations with source/time
  │    └─ local KB -> sanitized evidence journal + report
  └─ tools/ru_dc_vpn.py                     [separate authorized operation]
       ├─ explicit local inventory, output directory, existing trust
       ├─ network_ssh.py + credential_input.py
       └─ ASA / RouterOS commands, SFTP, SCEP placeholder, public cert extraction
```

`agent/` не импортирует операционный SSH транспорт или runner, не получает credentials и не имеет произвольного shell/SSH tool. Смена VPN/VLAN/NAT, reboot, save, ticket resolution и publishing недоступны в typed API даже с approval flag.

Операционный runner — существующий инструмент инженера, выполняющий переданные команды. Его полномочия задаёт SSH-учётная запись. Разрешение на работу, проверка применимости CLI/identity, согласованный change plan, резервный доступ, откат и end-to-end проверка выполняются в рамках отдельной операции. Это не подключённый автономный backend офлайн-агента.

`agent/inventory.py` использует только `DeviceRow` и чистый локальный XNet HTML parser, обходя приватный connected package initializer. Browser/XNet clients не поставляются.

Для добавления live typed backend потребуется отдельно выбранный pilot, проверенные device-side read-only права, ограниченный типизированный транспорт и review. Запуск операционного runner этого не реализует.
