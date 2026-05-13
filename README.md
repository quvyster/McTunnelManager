# TMUS Tunnel Manager Ultra Super

Утилита для создания WireGuard-туннеля через VPS с пробросом портов.
Python-переработка оригинального C# проекта McTunnelManager.

## Возможности
- SSH-подключение к VPS
- Автоустановка WireGuard на VPS
- Генерация ключей, создание и запуск туннеля
- Проброс портов через туннель (NAT)
- Автопереподключение при обрыве
- Современный GUI на CustomTkinter

## Установка
1. Установите WireGuard (https://www.wireguard.com/install/)
2. Установите Python 3.10+
3. pip install -r requirements.txt
4. python main.py

## Сборка .exe
python build_exe.py
Готовый файл: dist/TMUS_Tunnel_Manager.exe

## Требования
- Windows (для клиента)
- VPS с Ubuntu/Debian и публичным IP
