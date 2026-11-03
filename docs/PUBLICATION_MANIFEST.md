# Состав публикации — 2026-11-03

Репозиторий: `TopSerg/network-diagnostics-codex`. Публикация текущего кода агента и описания RU DC прямо запрошена пользователем. Закрытые данные в состав не входят.

## Включено

- Текущие `agent/*.py`, локальные `agent_tools` (KB, redaction, offline test runner, publication review).
- Полные проектные skills в `.agents/skills/` и совместимый исходный комплект `skills/network-diagnostics/`.
- Чистые модели и XNet HTML parser; операционные `network_ssh.py`, `credential_input.py`, credential-reference policy.
- Обезличенный существующий `tools/ru_dc_vpn.py`, его mock regression tests и auth tests.
- Зависимости, правила работы, README, quickstart, RU DC workflow и архитектура.

## Проверка

Перед переносом используется точный локальный JSON manifest с SHA256 каждого кандидата, target paths и hash-scoped примерами для synthetic tests/public identifiers. Этот JSON — приватный артефакт проверки, не runtime-зависимость demo и не файл, хеширующий сам себя.

Scanner проверяет только явные файлы и сравнивает содержимое с credential columns локальных приватных XLSX без вывода значений. Реальные secret/customer matches нельзя разрешить как примеры. Дополнительно проверяются итоговый Git diff, список файлов и история; игнорирование не очищает уже опубликованную историю.

README подготовлен заново как публичный текст; корневой README приватного workspace не копируется. Операционный runner получен из существующего исходника с удалением объектных defaults и фиксированных внутренних ресурсов. Добавленных проверок SSH-ключей нет.

Проверено на Python 3.12 в новом виртуальном окружении и на Python 3.14: **76 offline/mock tests + 1 совместимый KB test прошли**. Демонстрация сформировала 6 fixture evidence; CLI help запускается без приватного inventory. В чистом окружении зависимости установлены из `requirements-operational.txt`, `pip check` ошибок не нашёл. Проверка не подключалась к оборудованию и не подтверждает перенос конкретного объекта.

## Исключено

KB и её содержимое, ZIP, Hotels, Knowledge Base, Ru Dc, WLC, data, inventory/export, конфиги/backup, сертификаты/ключи, captures, browser profiles/sessions/tokens, логи и локальные отчёты. Приватные reboot/Daktela/browser/Cisco operational programs также не включены. Для работы с реальным объектом инженер получает разрешённые входные данные отдельно.
