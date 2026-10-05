# Codex Network Diagnostics Skill

Готовый репозиторий для повторяемой SSH-диагностики сетевой инфраструктуры через Codex.

Он разделён на два уровня:

- `AGENTS.md` — постоянные правила безопасности и стиль работы Codex в этом репозитории.
- `skills/network-diagnostics/` — workflow диагностики и справочники CLI по вендорам.

## Структура

```text
network-diagnostics-codex/
├── AGENTS.md
├── README.md
├── .gitignore
└── skills/
    └── network-diagnostics/
        ├── SKILL.md
        ├── references/
        │   ├── common-workflow.md
        │   ├── cisco-asa.md
        │   ├── cisco-ios-catalyst.md
        │   ├── ruckus-icx.md
        │   ├── aruba-cx.md
        │   ├── fortigate.md
        │   ├── mikrotik-routeros.md
        │   ├── huawei-vrp.md
        │   ├── ruijie.md
        │   └── eltex.md
        ├── scripts/
        │   └── ssh_readonly.py
        └── assets/
            └── report-template.md
```

## Как использовать

### Вариант 1 — как репозиторий Codex

Открой эту папку как рабочий репозиторий Codex. `AGENTS.md` задаёт постоянные правила, а skill можно вызывать явно:

```text
Use the network-diagnostics skill.
Diagnose why client 3C-52-82-37-6D-AC has no connectivity in VLAN 215.
```

Или просто сформулируй сетевую задачу — описание skill рассчитано на автоматический выбор при SSH/VLAN/DHCP/routing/VPN/Wi-Fi диагностике.

### Вариант 2 — установить skill отдельно

Скопируй каталог:

```text
skills/network-diagnostics
```

в каталог skills/capabilities, который доступен твоему Codex/agent runtime.

## SSH: рекомендуемая схема

Не храни пароли в skill и репозитории. Используй системный OpenSSH, `ssh-agent` и алиасы.

Пример `~/.ssh/config`:

```sshconfig
Host imperial-asa
    HostName 10.64.112.129
    User admin
    IdentityFile ~/.ssh/mikenopa

Host astana-idf14
    HostName 10.20.14.11
    User admin
    IdentityFile ~/.ssh/mikenopa
    ProxyJump company-jump
```

После этого Codex может работать с понятными именами:

```bash
ssh imperial-asa
ssh astana-idf14
```

Ключи лучше держать в `ssh-agent`; приватные ключи и секреты никогда не коммитить.

## Безопасный helper

`scripts/ssh_readonly.py` — небольшой wrapper над системным `ssh`. Он блокирует очевидно опасные команды и по умолчанию только показывает, что собирается выполнить.

Пример:

```bash
python skills/network-diagnostics/scripts/ssh_readonly.py imperial-asa "show route"
```

Для выполнения:

```bash
python skills/network-diagnostics/scripts/ssh_readonly.py --execute imperial-asa "show route"
```

Это дополнительный предохранитель, а не security boundary: окончательная безопасность всё равно зависит от прав SSH-учётной записи и ACL на оборудовании.

## Что skill умеет

- идентифицировать оборудование и выбрать соответствующий CLI;
- искать MAC и определять порт/VLAN;
- проверять STP/LAG/LACP/LLDP;
- проверять ARP, SVI/VE, маршрутизацию и FHRP;
- проверять DHCP/DNS/NAT/ACL/firewall/VPN;
- проходить путь client → AP → access → core → firewall/gateway → WAN;
- собирать доказательства и отделять факт от гипотезы;
- предлагать fix + rollback без самовольного применения изменений.

## Что стоит добавить следующим этапом

Для большого парка оборудования имеет смысл вынести inventory и выполнение SSH в отдельный MCP/tool слой, например:

```text
get_device(site, hostname)
run_show_command(device, command)
find_mac(site, mac)
collect_diagnostics(device, profile)
```

Skill при этом останется workflow-слоем: он будет решать, что проверять и в каком порядке, а MCP — безопасно выполнять действия.
