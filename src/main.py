import os
import cv2
import time
import subprocess
import random
import pytesseract
import re
from PIL import Image

__last_pos = False
_temp_path = "temp/temp.png"
battle_rounds = 0
battle_rounds_failure = 0

def adb_run(serial_num, command):
    return subprocess.run(
        f"adb -s {serial_num} {command}", stdout=subprocess.DEVNULL, check=True
    )


def adb_run(command):
    return subprocess.run(f"adb {command}", stdout=subprocess.DEVNULL, check=True)


def adb_screenshot():
    if not os.path.exists("temp"):
        os.makedirs("temp")
    if os.path.exists(_temp_path):
        os.remove(_temp_path)
    adb_run("shell screencap -p /data/screenshot.png")
    adb_run(f"pull /data/screenshot.png {_temp_path}")
    if not os.path.exists(_temp_path):
        print("Screenshot error.")
        return -1
    return 0


def adb_connect(address):
    os.system("adb kill-server")
    result = os.popen(f"adb connect {address}")
    if result.read().find("connected") == -1:
        print("Connect failed.")
        return -1
    else:
        print("ADB Connected.")
        return 0


def adb_click(center, rand_range=7):
    if center == False:
        return
    (x, y) = center
    x += random.randint(-rand_range, rand_range)
    y += random.randint(-rand_range, rand_range)
    # os.system(f"adb shell input tap {x} {y}")
    adb_run(f"shell input tap {x} {y}")


def image_to_pos(target, template, type=cv2.TM_CCOEFF_NORMED):
    targ_img = cv2.imread(target)
    temp_img = cv2.imread(template)
    assert (
        targ_img is not None
    ), "target file could not be read, check with os.path.exists()"
    assert (
        temp_img is not None
    ), "template file could not be read, check with os.path.exists()"
    image_h, image_w = temp_img.shape[:2]
    result = cv2.matchTemplate(targ_img, temp_img, type)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    # print("prob:", max_val)
    global __last_pos
    if type == cv2.TM_CCOEFF_NORMED:
        if max_val > 0.95:
            center = (max_loc[0] + image_w / 2, max_loc[1] + image_h / 2)
            __last_pos = center
            return center
        else:
            return False
    else:
        if min_val < 0.02:
            center = (min_loc[0] + image_w / 2, min_loc[1] + image_h / 2)
            __last_pos = center
            return center
        else:
            return False


def image_exists(target, template, type=cv2.TM_CCOEFF_NORMED):
    pos = image_to_pos(target, template, type)
    return pos != False


def image_press(template, colddown=0.5, target=_temp_path):
    adb_screenshot()
    pos = image_to_pos(target, template)
    if pos != False:
        adb_click(pos)
        time.sleep(colddown)
        return True
    time.sleep(0.25)
    return False


def general_check():
    if image_exists(_temp_path, "data/ok.png"):
        adb_click(__last_pos)
    else:
        adb_click([360, 640])


def stamina_recover():
    while True:
        adb_screenshot()
        if error_check():
            return
        if image_exists(_temp_path, "data/use.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/ok.png"):
            pos = __last_pos
            adb_click(pos)
            return
        elif image_exists(_temp_path, "data/stamina_limited.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/stamina_small.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/stamina_mid.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/stamina_large.png"):
            pos = __last_pos
            adb_click(pos)
        time.sleep(0.2)


def string_get_digits(_string):
    return "".join(list(filter(str.isdigit, _string)))


def acquire_bonus():
    print("进入无限池页面。")
    while True:
        adb_screenshot()
        if error_check():
            return
        if image_exists(_temp_path, "data/refresh_pool.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/ok.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/close.png"):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/gacha.png", cv2.TM_SQDIFF_NORMED):
            pos = __last_pos
            adb_click(pos)
        elif image_exists(_temp_path, "data/bonus_indicator.png"):
            img = Image.open(_temp_path)
            # Get coin remains
            cropImg = img.crop((123, 520, 205, 570))
            # cropImg.save("temp/get_digit.png")
            content = pytesseract.image_to_string(cropImg, lang="eng", config="--psm 6")
            coin_remain = string_get_digits(content)
            if coin_remain != "" and int(coin_remain) < 10:
                image_press("data/back.png")
        elif image_exists(_temp_path, "data/raid_event_main.png"):
            return
        time.sleep(0.25)


def error_check():
    if image_exists(_temp_path, "data/date_change.png"):
        print("检测到日期改变。")
        return True
    if image_exists(_temp_path, "data/start_page.png"):
        print("检测到退回主页面。")
        return True
    if image_exists(_temp_path, "data/error_0.png"):
        print("检测到联网错误。")
        return True
    return False


def raid_event():
    state = 0
    battle_start_time = 0
    BATTLE_TIME_THRESHOLD = 30
    BONUS_ROUND = 100
    global battle_rounds
    global battle_rounds_failure
    program_start_time = time.time()
    auto_tap = False
    goto_bonus = True
    auto_close_at_beginning = False
    auto_close_timer = 0
    AUTO_CLOSE_TIME = 1.0
    AUTO_POSITION = (44, 189)
    print("进入 RAID EVENT 活动主界面。")
    if auto_tap:
        print("注意：启用了连击。")
    while state >= 0:
        bad = adb_screenshot()
        if error_check():
            return
        if state == 0:  # Waiting for main page.
            pos = image_to_pos(_temp_path, "data/raid_event_main.png")
            if pos != False:
                print("检测到已经进入主界面。")
                if goto_bonus:
                    pos = image_to_pos(_temp_path, "data/bonus.png")
                    if pos != False:
                        adb_click(pos)
                        time.sleep(0.2)
                        acquire_bonus()
                        goto_bonus = False
                # Goto prepare page.
                else:
                    pos = image_to_pos(_temp_path, "data/raid_event_hell_diff.png")
                    if pos != False:
                        print("切换到准备界面。")
                        adb_click(pos)
                        state = 1
            pos = image_to_pos(_temp_path, "data/close.png")
            if pos != False:
                adb_click(pos)
            time.sleep(0.25)
        elif state == 1:  # In Prepare State.
            # Check if auto is enabled.
            if image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                pos = image_to_pos(_temp_path, "data/auto_disabled.png")
                if pos != False:
                    print("检测到自动模式关闭。打开自动模式。")
                    adb_click(pos)
                    time.sleep(0.2)
                # if image_exists(_temp_path, "data/auto_continue_disabled.png"):
                #     print("检测到自动续战关闭。打开自动续战。")
                #     adb_click(__last_pos)
                #     time.sleep(0.2)
                pos = image_to_pos(_temp_path, "data/raid_event_go.png")
                if pos != False:
                    adb_click(pos)
                    # Switch to battle waiting state.
                    state = 10
            time.sleep(0.25)
        elif state == 2:  # Battle State
            # Auto close for one sec
            if auto_close_at_beginning:
                if auto_close_timer == 0:
                    if image_exists(_temp_path, "data/auto_enabled_x1.png"):
                        adb_click(__last_pos)
                    elif image_exists(_temp_path, "data/auto_disabled_x0.png"):
                        auto_close_timer = time.time()
                elif time.time() - auto_close_timer > AUTO_CLOSE_TIME and image_exists(_temp_path, "data/auto_disabled_x0.png"):
                    adb_click(__last_pos)
            # If jump back to prepare state (Game over)
            if image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                state = 1
            # Else if time limit exceeds
            elif time.time() - battle_start_time > BATTLE_TIME_THRESHOLD:
                print("超时，重试战斗。")
                battle_rounds_failure += 1
                state = 4
            # Else if quest clear
            elif image_exists(_temp_path, "data/quest_clear.png") or image_exists(
                _temp_path, "data/quest_clear_2.png"
            ):
                print(
                    f"QUEST CLEAR ! Time used: {time.time() - battle_start_time:.2f}s"
                )
                # Every 100 rounds get to bonus page
                if (
                    battle_rounds - battle_rounds_failure
                ) % BONUS_ROUND == 0 and battle_rounds - battle_rounds_failure > 0:
                    print(f"检测到已经通过 {BONUS_ROUND} 轮。准备前往领取奖励。")
                    goto_bonus = True
                state = 3
            elif auto_tap:
                adb_click([300, 300])
            time.sleep(0.25)
        elif state == 3:  # Clear stage
            if image_exists(_temp_path, "data/continue.png"):
                # Disable show if enabled.
                pos = image_to_pos(_temp_path, "data/show_enabled.png")
                if pos != False:
                    adb_click(pos)
                    time.sleep(0.25)
                pos = image_to_pos(_temp_path, "data/continue.png")
                adb_click(pos)
            elif goto_bonus and image_exists(_temp_path, "data/quest_ok.png"):
                pos = __last_pos
                adb_click(pos)
                state = 0
                print("结算完毕，前往领取奖励。")
            elif not goto_bonus and image_exists(
                _temp_path, "data/retry_after_success.png"
            ):
                pos = __last_pos
                adb_click(pos)
                state = 1
                print("结算完毕，回到准备界面。")
            elif image_exists(_temp_path, "data/close.png"):
                pos = __last_pos
                adb_click(pos)
            elif image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                print("出现了某种错误。回到准备界面。")
                battle_rounds_failure += 1
                state = 1
            else:
                general_check()  # Speedup screen
            time.sleep(0.2)
        elif state == 4:  # Battle retrying State
            if image_exists(_temp_path, "data/pause.png") or image_exists(
                _temp_path, "data/battle_retry.png"
            ):
                adb_click(__last_pos)
            elif image_exists(_temp_path, "data/ok.png"):
                adb_click(__last_pos)
                state = 10
            time.sleep(0.1)
        elif state == 10:  # Battle Waiting State
            if image_exists(_temp_path, "data/battle_indicator.png"):
                state = 2
                battle_start_time = time.time()
                battle_rounds += 1
                auto_close_timer = 0
                failure_rate = 0.0
                if battle_rounds > 1:
                    failure_rate = battle_rounds_failure / (battle_rounds - 1) * 100
                print(f"战斗开始。当前第 {battle_rounds} 轮，翻车率为 {failure_rate:.2f}%。")
                print(f"目前通过共 {battle_rounds - 1 - battle_rounds_failure} 轮。")
                print(f"总耗时为 {time.time() - program_start_time:.2f}s。")
                if battle_rounds - 1 - battle_rounds_failure > 0:
                    print(
                        f"平均速度为 {(time.time() - program_start_time)/(battle_rounds - 1 - battle_rounds_failure):.2f} 秒/轮。"
                    )
                if auto_tap:
                    adb_click([300, 300])
            elif image_exists(_temp_path, "data/stamina_low.png"):
                stamina_recover()
            time.sleep(0.25)
        else:
            time.sleep(0.75)


def main():
    target = "RAID"
    target_state = 1

    # Decide target page
    if target == "RAID":
        target_state = 1

    state = 0
    print("进入主程序。")
    while True:
        adb_screenshot()
        if state == 0:  # If on main page
            # Page check & State switch
            if image_exists(_temp_path, "data/raid_event_main.png"):
                raid_event()
            elif image_exists(_temp_path, "data/events_main.png"):
                print("进入活动页面。")
                state = 1
            # If on main page
            elif (
                image_exists(_temp_path, "data/close.png")
                or image_exists(_temp_path, "data/close_red.png")
                or image_exists(_temp_path, "data/ok.png")
                or image_exists(_temp_path, "data/give_up.png")
                or image_exists(_temp_path, "data/back.png")
            ):
                adb_click(__last_pos)
            else:
                if target_state == 1 and image_exists(_temp_path, "data/events.png"):
                    adb_click(__last_pos)
                else:
                    adb_click([1024 / 2, 768 / 2])
        elif state == 1:  # If on event page
            if target == "RAID" and image_exists(
                _temp_path, "data/raid_event_banner.png"
            ):
                adb_click(__last_pos)
                raid_event()
            elif not image_exists(_temp_path, "data/events_main.png"):
                print("离开了活动页面。回到主程序。")
                state = 0
            else:
                print("警告 - 未检测到目标 / 未设定目标。")
        time.sleep(0.5)


if __name__ == "__main__":
    print("Script intializing.")
    # adb_addr = input("ADB Address:")
    adb_addr = 16384  # ADB Address/Port
    # adb_addr = 21543
    # adb_addr = 16448
    bad = adb_connect(adb_addr)
    if bad:
        exit()

    print("Script Initialized. Start main program.")
    while True:
        main()
