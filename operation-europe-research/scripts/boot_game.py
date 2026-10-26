#!/usr/bin/env python3
"""Быстрый вход в игру без ожидания роликов (DOSBox Automation должен быть запущен с `-Run koei`).
Алгоритм: ускорить CPU -> пока идёт OPEN.EXE (интро Koei) слать Esc -> на экране выбора ввода выбрать мышь/клавиатуру ->
дождаться главного меню по пикселям (не по sleep) -> при --to scenarios нажать New Game.
Использование: boot_game.py [--input mouse|keyboard] [--to menu|scenarios] [--timeout 120]
"""
import argparse
import io
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__file__))
import dosbox_ctl as d  # noqa: E402
from PIL import Image  # noqa: E402

T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:5.1f}s] {msg}", flush=True)


def frame():
    return Image.open(io.BytesIO(d.call("/video/frame", raw=True))).convert("RGB")


def program():
    return d.call("/program/state").get("segment_name", "").strip().upper()


def mode():
    return d.call("/video/frame/info")["video_mode"]


def is_input_select(im):
    """Чёрный экран с одной строкой белого текста по центру (Select Keyboard ... OR Mouse)."""
    if im.size != (640, 480):
        return False
    px = im.load()
    text = sum(1 for x in range(100, 540, 2) for y in range(140, 158) if sum(px[x, y]) > 500)
    other = sum(1 for x in range(0, 640, 8) for y in range(0, 100, 8) if sum(px[x, y]) > 120)
    return text > 40 and other == 0


def is_title_menu(im):
    """Страница-книга: светлый лист слева, кнопки New Game / Load Game."""
    if im.size != (640, 480):
        return False
    px = im.load()
    page = sum(1 for x in range(60, 280, 20) for y in range(60, 180, 20) if min(px[x, y]) > 225)
    btn = sum(1 for x in range(45, 150, 6) if 150 < px[x, 206][0] < 215 and abs(px[x, 206][0] - px[x, 206][2]) < 12)
    return page > 30 and btn > 8


def is_scenarios(im):
    if im.size != (640, 480):
        return False
    px = im.load()
    return sum(1 for y in (195, 219, 243, 267, 291, 315) if 150 < px[60, y][0] < 215) >= 5 and min(px[100, 120]) > 225


def sig(im):
    return im.convert("L").resize((160, 120))


def diff_px(a, b):
    from PIL import ImageChops
    return ImageChops.difference(a, b).point(lambda v: 255 if v > 24 else 0).histogram()[255]


def click_at(x, y, btn="left"):
    """Абсолютный клик в координатах экрана 640x480: home -> сдвиг (x, 2*y) (INT 33h 8:16 мик/пикс)."""
    d.mouse_move(-4000, -4000)
    time.sleep(0.12)
    d.mouse_move(x, y * 2)
    time.sleep(0.15)
    d.seq([{"type": "mouse_button", "button": btn, "pressed": True},
           {"type": "mouse_button", "button": btn, "pressed": False, "delay_ms": 100}])


def wait_change(before, timeout=4.0, thr=8, settle=0.3):
    """Ждать, пока экран изменится относительно `before` (sig-кадр), затем дать ему устояться."""
    end = time.time() + timeout
    while time.time() < end:
        cur = sig(frame())
        if diff_px(before, cur) >= thr:
            time.sleep(settle)
            return True
        time.sleep(0.12)
    return False


def cursor_tip(clean, now):
    """Остриё курсора-стрелки: новые тёмные пиксели в `now` относительно `clean` (кадр, где курсор в углу и не виден)."""
    import numpy as np
    a = np.asarray(clean, dtype=int)
    b = np.asarray(now, dtype=int)
    new_black = (b.max(axis=2) <= 40) & (a.max(axis=2) > 40)
    ys, xs = np.nonzero(new_black[:, :])
    if len(xs) < 8:
        return None
    # отсечь одиночные шумы: берём ячейку 24x24 с наибольшим числом новых тёмных пикселей
    best = None
    for cy in range(0, 480, 12):
        for cx in range(0, 640, 12):
            blk = new_black[cy:cy + 28, cx:cx + 28]
            n = int(blk.sum())
            if n > 10 and (best is None or n > best[0]):
                best = (n, cx, cy)
    if best is None:
        return None
    _, cx, cy = best
    ys, xs = np.nonzero(new_black[cy:cy + 28, cx:cx + 28])
    # остриё — самый верхний пиксель, среди них самый левый
    top = ys.min()
    return cx + int(xs[ys == top].min()), cy + int(top)


def goto(x, y, tol=3, tries=4):
    """Навести курсор в (x,y): home -> грубый сдвиг -> докрутка по положению курсора на скриншоте. Возвращает остриё или None."""
    d.mouse_move(-4000, -4000)
    time.sleep(0.2)
    clean = frame()
    d.mouse_move(x, y * 2)
    time.sleep(0.25)
    tip = None
    for i in range(tries):
        now = frame()
        tip = cursor_tip(clean, now)
        if tip is None:
            return None
        ex, ey = x - tip[0], y - tip[1]
        if abs(ex) <= tol and abs(ey) <= tol:
            return tip
        d.mouse_move(ex, ey * 2)
        time.sleep(0.25)
    return tip


def wait_stable(quiet=0.9, timeout=12.0, thr=3):
    """Ждать, пока экран перестанет меняться (текст допечатался, анимация/затухание закончились)."""
    end = time.time() + timeout
    prev = sig(frame())
    still_since = time.time()
    while time.time() < end:
        time.sleep(0.15)
        cur = sig(frame())
        if diff_px(prev, cur) > thr:
            still_since = time.time()
        prev = cur
        if time.time() - still_since >= quiet:
            return True
    return False


def step(name, x, y, timeout=4.0):
    wait_stable()
    tip = goto(x, y)
    if tip is not None and (abs(tip[0] - x) > 6 or abs(tip[1] - y) > 6):
        log(f"   курсор не дошёл: цель ({x},{y}), остриё {tip}")
    before = sig(frame())              # кадр ПОСЛЕ наведения: сам курсор уже не считается изменением
    if __import__("os").environ.get("OE_SHOTS"):
        step.n = getattr(step, "n", 0)
        frame().save(__import__("os").path.join(__import__("os").environ["OE_SHOTS"], f"{step.n + 1:02d}_hover.png"))
    d.seq([{"type": "mouse_button", "button": "left", "pressed": True},
           {"type": "mouse_button", "button": "left", "pressed": False, "delay_ms": 100}])
    ok = wait_change(before, timeout)
    if __import__("os").environ.get("OE_SHOTS"):          # отладка: кадр после каждого шага
        step.n = getattr(step, "n", 0) + 1
        pre = __import__("os").path.join(__import__("os").environ["OE_SHOTS"], f"{step.n:02d}_pre.png")
        frame().save(__import__("os").path.join(__import__("os").environ["OE_SHOTS"], f"{step.n:02d}_after.png"))
    log(f"{name}: клик ({x},{y}) -> {'экран сменился' if ok else 'НЕТ изменения (идём дальше)'}")
    return ok


def is_strategy(im):
    """Стратегический экран: серая строка меню (Pass..Game) сверху и серая рамка карты."""
    if im.size != (640, 480):
        return False
    px = im.load()
    gray = sum(1 for x in range(20, 620, 10) if min(px[x, 50]) > 170 and max(px[x, 50]) - min(px[x, 50]) < 20)
    return gray >= 45 and px[500, 300][2] > 100 and px[500, 300][0] < 60


# Координаты (экран 640x480) по записи PLAY-001; см. knowledge/DOS_SCREENS.md
BATTLES = {"view": (100, 211), "dont": (100, 235), "choose": (100, 259)}
DIFF = {"veryeasy": 211, "easy": 235, "average": 259, "hard": 283, "veryhard": 307}
OFFICER_ROWS = [297, 314, 332, 349, 367, 383]          # строки таблицы: AC, Ops, Intl, Div1, Div2, Div3
SIDES = {"allies": 211, "axis": 235}


def kb(name, *keys, settle=0.7, thr=15, stable_timeout=2.5):
    """Нажать клавиши по очереди (каждая после стабилизации экрана), затем дождаться реакции и покоя.
    thr — сколько пикселей (в уменьшенном кадре) считается движением; stable_timeout — максимум ждать покоя
    (мигающий значок/анимация не должны подвешивать проход)."""
    wait_stable(quiet=settle, thr=thr, timeout=stable_timeout)
    before = sig(frame())
    for k in keys:
        d.key(k, 70)
        time.sleep(0.25)
    changed = wait_change(before, 3.0, settle=0.2)
    if __import__("os").environ.get("OE_SHOTS"):
        kb.n = getattr(kb, "n", 0) + 1
        frame().save(__import__("os").path.join(__import__("os").environ["OE_SHOTS"], f"kb{kb.n:02d}.png"))
    log(f"{name}: {' '.join(k.replace('KBD_', '') for k in keys)} -> {'экран сменился' if changed else 'нет изменений'}")
    return changed


def newgame_keyboard(a):
    """Проход меню клавиатурой: Enter = выбрать (левый клик), Down/Up = переместить выделение."""
    E, D = "KBD_enter", "KBD_down"
    kb("сценарий France", E)
    kb("предыстория (ждём допечатывания)", E, settle=1.0, thr=2, stable_timeout=9)     # текст печатается побуквенно
    kb("игроков: One Player", D, E)
    kb(f"сторона: {a.side}", *([D] if a.side == "axis" else []), E)
    kb("карта: Field Map", E)
    kb(f"показ боёв: {a.battles}", *([D] * {"view": 0, "dont": 1, "choose": 2}[a.battles]), E)
    kb(f"сложность: {a.difficulty}", *([D] * list(DIFF).index(a.difficulty)), E)
    kb("настройки OK", E)
    kb("способности зафиксированы", E, settle=1.2)
    if __import__("os").environ.get("OE_STOP") == "officers":      # отладка: остановиться перед выбором офицеров
        return True
    names = ["Army Cmndr", "Ops Chief", "Intl Chief", "Div 1", "Div 2", "Div 3", "Div 4"]
    boxes = {"Army Cmndr": (257, 80), "Ops Chief": (97, 80), "Intl Chief": (417, 80),
             "Div 1": (17, 175), "Div 2": (177, 175), "Div 3": (337, 175), "Div 4": (497, 175)}

    def filled(nm):
        x, y = boxes[nm]
        px = frame().crop((x + 6, y + 6, x + 56, y + 70)).convert("L")
        return sum(px.tobytes()) / (50 * 64) > 35        # пустая рамка тёмная, с портретом — светлее

    for nm in names:
        # Enter выбирает подсвеченную строку; занятого офицера выбрать нельзя -> Down (список сам прокручивается) и Enter;
        # успех проверяем по появлению портрета в своей рамке, а не по «экран сменился»
        for attempt in range(14):
            # выбранный предыдущим офицер остаётся подсвеченным -> для всех, кроме первого, сразу Down+Enter
            keys = (E,) if (nm == "Army Cmndr" and attempt == 0) else (D, E)
            kb(f"офицер {nm}", *keys, stable_timeout=1.5)
            end = time.time() + 1.5
            ok = False
            while time.time() < end and not ok:      # портрет рисуется с небольшой задержкой
                ok = filled(nm)
                time.sleep(0.15)
            if ok:
                break
        else:
            log(f"не удалось назначить {nm}")
            return False
    for q in ("Are you satisfied?", "Use these generals?", "Are you ready for battle?"):
        kb(q, E)
    end = time.time() + 45
    clicks = 0
    while time.time() < end:
        if is_strategy(frame()):
            log(f"стратегическая карта (реплик пропущено: {clicks})")
            return True
        d.key(E, 70)
        clicks += 1
        time.sleep(0.6)
    return False


def newgame(a):
    if a.input == "keyboard":
        return newgame_keyboard(a)
    """От списка сценариев (France) до стратегической карты. Всё остальное по записи PLAY-001."""
    step("сценарий France", 150, 195)
    step("предыстория", 150, 300)
    step("игроков: One Player", 80, 235)
    step(f"сторона: {a.side}", 80, SIDES[a.side])
    step("карта: Field Map", 80, 211)
    step(f"показ боёв: {a.battles}", *BATTLES[a.battles])
    step(f"сложность: {a.difficulty}", 100, DIFF[a.difficulty])
    step("настройки OK", 320, 300)
    step("способности зафиксированы", 320, 240)       # «Left-click after making all changes»
    names = ["Army Cmndr", "Ops Chief", "Intl Chief", "Div 1", "Div 2", "Div 3"]
    for nm, y in zip(names, OFFICER_ROWS):
        step(f"офицер {nm}", 200, y, timeout=3.0)
    step("прокрутка списка офицеров (стрелка v)", 152, 376, timeout=3.0)
    step("офицер Div 4", 200, 366, timeout=3.0)
    for q in ("Are you satisfied?", "Use these generals?", "Are you ready for battle?"):
        step(q, 320, 240, timeout=3.0)
    end = time.time() + 45
    clicks = 0
    while time.time() < end:
        if is_strategy(frame()):
            log(f"стратегическая карта (реплик пропущено кликами: {clicks})")
            return True
        click_at(400, 440)                               # листаем реплики Supreme Commander / Chief of Staff
        clicks += 1
        time.sleep(0.6)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", choices=["mouse", "keyboard"], default="mouse")
    ap.add_argument("--to", choices=["menu", "scenarios", "newgame"], default="menu")
    ap.add_argument("--side", choices=["allies", "axis"], default="allies")
    ap.add_argument("--difficulty", choices=list(DIFF), default="veryeasy")
    ap.add_argument("--battles", choices=list(BATTLES), default="dont", help="показ боёв (по записи игрок выбирал view)")
    ap.add_argument("--timeout", type=float, default=150)
    ap.add_argument("--cycles", type=int, default=200000, help="скорость на время загрузки (после входа возвращается)")
    ap.add_argument("--after-cycles", type=int, default=50000, help="скорость после входа")
    a = ap.parse_args()

    for _ in range(60):  # ждём API
        try:
            d.call("/status")
            break
        except SystemExit:
            time.sleep(0.5)
    old = d.call("/cpu/cycles")
    log(f"cycles сейчас: {old}")
    d.call("/cpu/cycles", "PUT", {"cycles": a.cycles})

    last_esc = 0
    state = "intro"
    deadline = time.time() + a.timeout
    try:
        while time.time() < deadline:
            prog = program()
            if prog != getattr(main, "_last", None):
                log("программа: " + (prog or "(shell)"))
                main._last = prog
            if state == "intro":
                if prog == "OPEN":
                    if time.time() - last_esc > 0.4:
                        d.key("KBD_esc", 40)
                        last_esc = time.time()
                elif prog == "MAIN":
                    log("main.exe загружен, жду экран выбора ввода")
                    state = "select"
            if state == "select":
                # через koei экран выбора рисуется (графика); при прямом `fmdrv`+`main` он «невидим» (пустой текстовый режим)
                main_since = getattr(main, "_main_since", None) or time.time()
                main._main_since = main_since
                blank_text = mode()["bios_mode_number"] == 3 and time.time() - main_since > 1.5
                if blank_text or is_input_select(frame()):
                    if a.input == "mouse":
                        d.seq([{"type": "mouse_button", "button": "left", "pressed": True},
                               {"type": "mouse_button", "button": "left", "pressed": False, "delay_ms": 100}])
                    else:
                        d.key("KBD_space")
                    log(f"выбран ввод: {a.input}")
                    state = "title"
            elif state == "title":
                if is_title_menu(frame()):
                    log("главное меню (New Game / Load Game)")
                    if a.to == "menu":
                        break
                    if a.input == "mouse":
                        d.mouse_move(-4000, -4000)
                        time.sleep(0.15)
                        d.mouse_move(95, 211 * 2)
                        time.sleep(0.2)
                        d.seq([{"type": "mouse_button", "button": "left", "pressed": True},
                               {"type": "mouse_button", "button": "left", "pressed": False, "delay_ms": 100}])
                    else:
                        d.key("KBD_enter")
                    state = "scen"
            elif state == "scen":
                if is_scenarios(frame()):
                    log("список сценариев")
                    if a.to == "newgame":
                        if not newgame(a):
                            log("ТАЙМАУТ: стратегическая карта не появилась")
                            frame().save("boot_timeout.png")
                            sys.exit(1)
                    break
            time.sleep(0.25)
        else:
            log(f"ТАЙМАУТ в состоянии {state}, программа {program()}")
            frame().save("boot_timeout.png")
            sys.exit(1)
    finally:
        try:
            d.call("/cpu/cycles", "PUT", {"cycles": a.after_cycles})
        except SystemExit:
            pass
    log(f"готово (cycles -> {a.after_cycles})")


if __name__ == "__main__":
    main()
