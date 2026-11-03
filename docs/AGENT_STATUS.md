# Состояние агента — 2026-11-03

В репозиторий перенесён текущий локальный офлайн-агент и обезличенная версия существующего операционного runner RU DC. Внутренние inventory, KB, конфигурации, сертификаты, журналы и доступы не включены.

| Возможность | Состояние | Ограничение |
|---|---|---|
| Local XLSX / saved XNet HTML | Реальные локальные парсеры | Свежесть и firmware не выводятся из факта наличия экспорта |
| Точный device/AP lookup | Реализован; ambiguity tests | Нет live XNet/WLC discovery |
| Connectivity/VLAN/VPN/Wi-Fi планы | Типизированные проверки и права | Небольшой каталог моделей; backend fixtures only |
| KB SQLite FTS5 | Локальное чтение, redaction, citations | Приватная БД предоставляется отдельно |
| Журнал и отчёт | Evidence ID, источник/время/SHA256 | Хеш подтверждает целостность, не истинность исходных данных |
| RU DC ASA / RouterOS | Отдельный `tools/ru_dc_vpn.py` | Требует точного плана, входных данных и разрешённой операции |
| SCEP / peer certificate | Скрытая подстановка challenge, работа с публичными X.509 | CA и параметры получают отдельно; debug автоматически не включается |
| Browser / Daktela / reboot / Cisco collector | Не поставляются | Не объявлять их доступными по наличию документации навыка |
| Live backend в `agent/` | Отсутствует | Никаких изменений/SSH/закрытия тикетов через typed API |

## Проверить после скачивания

```powershell
python -m pip install -r requirements-agent.txt
python -m agent --demo
python -m agent_tools.offline_tests
python -m pip install -r requirements-operational.txt
python tools/ru_dc_vpn.py --help
python -m agent_tools.offline_tests --operational
```

Оба тестовых режима блокируют сеть и создание внешних процессов до discovery. Операционные проверки работают с mocks, не с реальным оборудованием. Успешный тест или demo не подтверждает доступ и состояние конкретного объекта. Числа и версии проверки этого релиза записаны в [PUBLICATION_MANIFEST.md](PUBLICATION_MANIFEST.md).

Public runner получен из существующей приватной программы: исключены объектные default paths, ZIP/SCEP probe с фиксированными внутренними ресурсами; inventory/output/trust/label обязательны, CA задаётся явно, неоднозначная цель блокируется. Существующие функции CLI/auth/redaction и механизм SSH-ключей сохранены. Новые проверки ключей не добавлены.
