import os
import cv2
import time
import subprocess
import random


def adb_run(serial_num, command):
    return subprocess.run(
        f"adb -s {serial_num} {command}", stdout=subprocess.DEVNULL, check=True
    )


def adb_run(command):
    return subprocess.run(f"adb {command}", stdout=subprocess.DEVNULL, check=True)


def adb_screenshot():
    if os.path.exists("./tmp.png"):
        os.remove("./tmp.png")
    adb_run("shell screencap -p /data/screenshot.png")
    adb_run("pull /data/screenshot.png ./tmp.png")
    if not os.path.exists("./tmp.png"):
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


def image_to_pos(target, template):
    targ_img = cv2.imread(target)
    temp_img = cv2.imread(template)
    assert (
        targ_img is not None
    ), "target file could not be read, check with os.path.exists()"
    assert (
        temp_img is not None
    ), "template file could not be read, check with os.path.exists()"
    image_h, image_w = temp_img.shape[:2]
    result = cv2.matchTemplate(targ_img, temp_img, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    # print("prob:", max_val)
    if max_val > 0.95:
        center = (max_loc[0] + image_w / 2, max_loc[1] + image_h / 2)
        return center
    else:
        return False


def image_exists(target, template):
    pos = image_to_pos(target, template)
    return pos != False


def image_press(template, colddown=0.5, target="tmp.png"):
    adb_screenshot()
    pos = image_to_pos(target, template)
    if pos != False:
        adb_click(pos)
        time.sleep(colddown)
        return True
    time.sleep(0.25)
    return False


def stamina_recover():
    while True:
        adb_screenshot()
        if image_exists("tmp.png", "data/use.png"):
            pos = image_to_pos("tmp.png", "data/use.png")
            adb_click(pos)
        elif image_exists("tmp.png", "data/ok.png"):
            pos = image_to_pos("tmp.png", "data/ok.png")
            adb_click(pos)
            return
        elif image_exists("tmp.png", "data/stamina_limited.png"):
            pos = image_to_pos("tmp.png", "data/stamina_limited.png")
            adb_click(pos)
        elif image_exists("tmp.png", "data/stamina_small.png"):
            pos = image_to_pos("tmp.png", "data/stamina_small.png")
            adb_click(pos)
        elif image_exists("tmp.png", "data/stamina_mid.png"):
            pos = image_to_pos("tmp.png", "data/stamina_mid.png")
            adb_click(pos)
        elif image_exists("tmp.png", "data/stamina_large.png"):
            pos = image_to_pos("tmp.png", "data/stamina_large.png")
            adb_click(pos)
        time.sleep(0.2)


def main():
    state = 0
    battle_start_time = 0
    BATTLE_TIME_THRESHOLD = 45
    battle_rounds = 0
    battle_rounds_failure = 0
    program_start_time = time.time()
    combo_tap = False
    print("等待进入主界面。")
    if combo_tap:
        print("注意：启用了连击。")
    while state >= 0:
        bad = adb_screenshot()
        if state == 0:  # Waiting for main page.
            pos = image_to_pos("tmp.png", "data/raid_event_main.png")
            if pos != False:
                print("检测到已经进入主界面。")
                # Switch to HELL Difficulty.
                pos = image_to_pos("tmp.png", "data/raid_event_hell_diff.png")
                if pos != False:
                    print("切换到准备界面。")
                    adb_click(pos)
                    state = 1
                else:
                    print("获取位置失败。")
            pos = image_to_pos("tmp.png", "data/close.png")
            if pos != False:
                adb_click(pos)
            time.sleep(0.25)
        elif state == 1:  # In Prepare State.
            # Check if auto is enabled.
            if image_exists("tmp.png", "data/raid_event_hell_prepare.png"):
                pos = image_to_pos("tmp.png", "data/auto_disabled.png")
                if pos != False:
                    print("检测到自动模式关闭。打开自动模式。")
                    adb_click(pos)
                    time.sleep(0.75)
                pos = image_to_pos("tmp.png", "data/raid_event_go.png")
                if pos != False:
                    adb_click(pos)
                    # Switch to battle waiting state.
                    state = 10
            time.sleep(0.25)
        elif state == 2:  # Battle State
            # If jump back to prepare state (Game over)
            if image_exists("tmp.png", "data/raid_event_hell_prepare.png"):
                state = 1
            # Else if time limit exceeds
            elif time.time() - battle_start_time > BATTLE_TIME_THRESHOLD:
                print("超时，重试战斗。")
                battle_rounds_failure += 1
                # Battle retry.
                while image_press("data/pause.png"):
                    continue
                while image_press("data/battle_retry.png"):
                    continue
                while image_press("data/ok.png"):
                    continue
                state = 10
            # Else if quest clear
            elif image_exists("tmp.png", "data/quest_clear.png"):
                print(
                    f"QUEST CLEAR ! Time used: {time.time() - battle_start_time:.2f}s"
                )
                state = 3
            elif combo_tap:
                adb_click([300, 300])
            time.sleep(0.25)
        elif state == 3:  # Clear stage
            if image_exists("tmp.png", "data/continue.png"):
                # Disable show if enabled.
                pos = image_to_pos("tmp.png", "data/show_enabled.png")
                if pos != False:
                    adb_click(pos)
                    time.sleep(0.25)
                pos = image_to_pos("tmp.png", "data/continue.png")
                adb_click(pos)
            elif image_exists("tmp.png", "data/retry_after_success.png"):
                pos = image_to_pos("tmp.png", "data/retry_after_success.png")
                adb_click(pos)
                state = 1
                print("结算完毕，回到准备界面。")
            elif image_exists("tmp.png", "data/close.png"):
                pos = image_to_pos("tmp.png", "data/close.png")
                adb_click(pos)
            elif image_exists("tmp.png", "data/raid_event_hell_prepare.png"):
                print("出现了某种错误。回到准备界面。")
                battle_rounds_failure += 1
                state = 1
            else:
                adb_click([300, 300])  # Speedup screen
            time.sleep(0.2)
        elif state == 10:  # Battle Waiting State
            if image_exists("tmp.png", "data/battle_indicator.png"):
                state = 2
                battle_start_time = time.time()
                battle_rounds += 1
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
                if combo_tap:
                    adb_click([300, 300])
            elif image_exists("tmp.png", "data/stamina_low.png"):
                stamina_recover()
            time.sleep(0.25)
        else:
            time.sleep(0.75)


if __name__ == "__main__":
    print("Script intializing.")
    # adb_addr = input("ADB Address:")
    adb_addr = 21543  # ADB Address/Port
    bad = adb_connect(adb_addr)
    if bad:
        exit()

    print("Script Initialized. Start main program.")
    main()
