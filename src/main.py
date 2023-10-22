import os
import cv2
import time
import subprocess
import random
import pytesseract
import re
import json
from PIL import Image

__last_pos = False
_temp_path = "temp/temp.png"
battle_rounds = 0
battle_rounds_failure = 0
__DEBUG = False


def output_log(log):
    global device_tag
    print(f"[{device_tag}] {log}")


def adb_run(serial_num, command):
    if __DEBUG:
        return subprocess.run(f"adb -s {serial_num} {command}", check=True)
    else:
        return subprocess.run(
            f"adb -s {serial_num} {command}", stdout=subprocess.DEVNULL, check=True
        )


def adb_screenshot():
    global device_id
    if not os.path.exists("temp"):
        os.makedirs("temp")
    if os.path.exists(_temp_path):
        os.remove(_temp_path)
    adb_run(device_id, "shell screencap -p /data/screenshot.png")
    adb_run(device_id, f"pull /data/screenshot.png {_temp_path}")
    if not os.path.exists(_temp_path):
        print("Screenshot error.")
        return -1
    return 0


def adb_reset():
    os.system("adb kill-server")
    os.system("adb start-server")


def adb_connect(address):
    result = os.popen(f"adb connect {address}")
    if result.read().find("connected") == -1:
        print("Connect failed.")
        return -1
    else:
        print("ADB Connected.")
        return 0


def adb_click(center, rand_range=7):
    global device_id
    if center == False:
        return
    (x, y) = center
    x += random.randint(-rand_range, rand_range)
    y += random.randint(-rand_range, rand_range)
    # os.system(f"adb shell input tap {x} {y}")
    adb_run(device_id, f"shell input tap {x} {y}")


def image_to_pos(target, template, type=cv2.TM_CCOEFF_NORMED):
    if __DEBUG:
        output_log(f"与文件 {template} 进行比较。")
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
    output_log("进入无限池页面。")
    finished = False
    ensurance = 0
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
            getIn = True
            img = Image.open(_temp_path)
            # Get coin remains
            cropImg = img.crop((123, 520, 205, 570))
            # cropImg.save("temp/get_digit.png")
            content = pytesseract.image_to_string(cropImg, lang="eng", config="--psm 6")
            coin_remain = string_get_digits(content)
            if coin_remain != "" and int(coin_remain) < 10:
                image_press("data/back.png")
                finished = True
        elif finished and not image_exists(
            _temp_path, "data/bonus_indicator_type2.png"
        ):
            ensurance += 1
            if ensurance > 3:
                return
        time.sleep(0.25)


def error_check():
    if image_exists(_temp_path, "data/date_change.png"):
        output_log("检测到日期改变。")
        return True
    if image_exists(_temp_path, "data/start_page.png"):
        output_log("检测到退回主页面。")
        return True
    if image_exists(_temp_path, "data/error_0.png"):
        output_log("检测到联网错误。")
        return True
    return False


def raid_event(tconfig):
    state = 0
    battle_start_time = 0
    BATTLE_TIME_THRESHOLD = tconfig.get("timeout", -1)
    BONUS_ROUND = tconfig.get("bonus_round", 100)
    global battle_rounds
    global battle_rounds_failure
    program_start_time = time.time()
    # auto_tap = False
    auto_tap = tconfig.get("auto_tap", False)
    goto_bonus = True

    auto_close_timer = 0
    auto_closed = False
    limit_rounds = tconfig.get("limit_round", -1)
    auto_close_conf = tconfig.get("auto_close", {"enabled": False, "time": 0})
    auto_close_at_beginning = auto_close_conf["enabled"]
    AUTO_CLOSE_TIME = auto_close_conf["time"]

    AUTO_POSITION = (44, 189)
    output_log("进入 RAID EVENT 活动主界面。")
    if auto_tap:
        output_log("注意：启用了连击。")
    while state >= 0:
        bad = adb_screenshot()
        if error_check():
            return
        if state == 0:  # Waiting for main page.
            pos = image_to_pos(_temp_path, "data/raid_event_main.png")
            if pos != False:
                output_log("检测到已经进入主界面。")
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
                        output_log("切换到准备界面。")
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
                    output_log("检测到自动模式关闭。打开自动模式。")
                    adb_click(pos)
                    time.sleep(0.2)
                # if image_exists(_temp_path, "data/auto_continue_disabled.png"):
                #     output_log("检测到自动续战关闭。打开自动续战。")
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
                if time.time() - auto_close_timer > AUTO_CLOSE_TIME and auto_closed:
                    adb_click(AUTO_POSITION)
                    time.sleep(0.05)
                    adb_click((300, 300))
                    auto_closed = False
            # If jump back to prepare state (Game over)
            if image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                state = 1
            # Else if time limit exceeds
            elif (
                BATTLE_TIME_THRESHOLD > 0
                and time.time() - battle_start_time >= BATTLE_TIME_THRESHOLD
            ):
                output_log("超时，重试战斗。")
                battle_rounds_failure += 1
                state = 4
            # Else if quest clear
            elif (
                image_exists(_temp_path, "data/quest_clear.png")
                or image_exists(_temp_path, "data/quest_clear_2.png")
                or image_exists(_temp_path, "data/stage_clear.png")
            ):
                output_log(
                    f"QUEST CLEAR ! Time used: {time.time() - battle_start_time:.2f}s"
                )
                # Every 100 rounds get to bonus page
                if (
                    battle_rounds - battle_rounds_failure
                ) % BONUS_ROUND == 0 and battle_rounds - battle_rounds_failure > 0:
                    output_log(f"检测到已经通过 {BONUS_ROUND} 轮。准备前往领取奖励。")
                    goto_bonus = True
                state = 3
            elif auto_tap:
                adb_click([300, 300])
            time.sleep(0.1)
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
                output_log("结算完毕，前往领取奖励。")
            elif not goto_bonus and image_exists(
                _temp_path, "data/retry_after_success.png"
            ):
                pos = __last_pos
                adb_click(pos)
                state = 1
                output_log("结算完毕，回到准备界面。")
                if limit_rounds > 0 and battle_rounds >= limit_rounds:
                    output_log("战斗达到限制上限。退出该任务。")
                    return
            elif image_exists(_temp_path, "data/close.png"):
                pos = __last_pos
                adb_click(pos)
            elif image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                output_log("出现了某种错误。回到准备界面。")
                battle_rounds_failure += 1
                state = 1
            else:
                general_check()  # Speedup screen
            time.sleep(0.2)
        elif state == 4:  # Battle retrying State
            if image_exists(_temp_path, "data/stage_clear.png"):
                state = 3
            elif image_exists(_temp_path, "data/raid_event_hell_prepare.png"):
                state = 1
            elif image_exists(_temp_path, "data/raid_event_main.png"):
                state = 0
            elif image_exists(_temp_path, "data/pause.png") or image_exists(
                _temp_path, "data/battle_retry.png"
            ):
                adb_click(__last_pos)
            elif image_exists(_temp_path, "data/ok.png"):
                adb_click(__last_pos)
                state = 10
            time.sleep(0.2)
        elif state == 10:  # Battle Waiting State
            if image_exists(_temp_path, "data/battle_indicator.png"):
                state = 2
                battle_start_time = time.time()
                battle_rounds += 1
                auto_close_timer = 0
                failure_rate = 0.0
                if battle_rounds > 1:
                    failure_rate = battle_rounds_failure / (battle_rounds - 1) * 100
                output_log(f"战斗开始。当前第 {battle_rounds} 轮，翻车率为 {failure_rate:.2f}%。")
                output_log(f"目前通过共 {battle_rounds - 1 - battle_rounds_failure} 轮。")
                output_log(f"总耗时为 {time.time() - program_start_time:.2f}s。")
                if battle_rounds - 1 - battle_rounds_failure > 0:
                    output_log(
                        f"平均速度为 {(time.time() - program_start_time)/(battle_rounds - 1 - battle_rounds_failure):.2f} 秒/轮。"
                    )
                if auto_tap:
                    adb_click([300, 300])
                if auto_close_at_beginning:
                    adb_click(AUTO_POSITION)
                    auto_close_timer = time.time()
                    auto_closed = True
            elif image_exists(_temp_path, "data/stamina_low.png"):
                stamina_recover()
            time.sleep(0.1)
        else:
            time.sleep(0.75)


def match_tag_check(matchTag):
    state = 0
    while True:
        adb_screenshot()
        if error_check():
            return
        if state == 0:
            matchCount = 0
            for i in range(0, 3):
                if image_exists(
                    _temp_path,
                    f"data/matchTags/s/{'on' if matchTag & (1<<i) else 'off'}{i}.png",
                ):
                    matchCount += 1
            if matchCount == 3:
                return
            if image_exists(_temp_path, "data/recruit.png"):
                adb_click(__last_pos)
                state = 1
                output_log("开始招募。")
            else:
                return
        elif state == 1:
            matchCount = 0
            for i in range(0, 3):
                if not image_exists(
                    _temp_path,
                    f"data/matchTags/{'on' if matchTag & (1<<i) else 'off'}{i}.png",
                ):
                    image_press(
                        f"data/matchTags/{'off' if matchTag & (1<<i) else 'on'}{i}.png",
                        0.3,
                        _temp_path,
                    )
                else:
                    matchCount += 1
            # if matchCount == 3:
            state = 2
        elif state == 2:
            if image_exists(_temp_path, "data/recruit_start.png"):
                adb_click(__last_pos)
                output_log("招募完毕。")
                time.sleep(0.2)
                return
        time.sleep(0.2)


def story_events(tconfig):
    # Setup event config.
    targetEvent = tconfig["event"]
    targetBoss = tconfig["boss"]
    action = tconfig["action"]
    matchTag = tconfig.get("match_tag", 1)

    state = 0
    battle_start_time = 0
    BATTLE_TIME_THRESHOLD = tconfig.get("timeout", -1)
    BONUS_ROUND = tconfig.get("bonus_round", 100)
    global battle_rounds
    global battle_rounds_failure
    program_start_time = time.time()
    # auto_tap = False
    auto_tap = tconfig.get("auto_tap", False)
    goto_bonus = not __DEBUG
    recruited = False

    auto_close_timer = 0
    auto_closed = False
    limit_rounds = tconfig.get("limit_round", -1)
    auto_close_conf = tconfig.get("auto_close", {"enabled": False, "time": 0})
    auto_close_at_beginning = auto_close_conf["enabled"]
    AUTO_CLOSE_TIME = auto_close_conf["time"]

    AUTO_POSITION = (44, 189)
    output_log("进入活动主界面。")
    if auto_tap:
        output_log("注意：启用了连击。")
    while state >= 0:
        bad = adb_screenshot()
        if error_check():
            return
        if state == 0:  # Waiting for main page.
            pos = image_to_pos(_temp_path, "data/story_event_indicator.png")
            if pos != False and __DEBUG:
                output_log("检测到已经进入活动主界面。")
            if goto_bonus:
                pos = image_to_pos(_temp_path, "data/bonus.png")
                if pos != False:
                    adb_click(pos)
                    time.sleep(0.2)
                    acquire_bonus()
                    goto_bonus = False
                    output_log("无限池领取完毕。")
                elif image_exists(_temp_path, "data/multiplayer.png"):
                    image_press("data/back.png", 0.3, _temp_path)
            # Goto prepare page.
            else:
                if image_exists(_temp_path, "data/event_multi.png"):
                    adb_click(__last_pos)
                elif image_exists(
                    _temp_path, f"data/events/{targetEvent}/{targetBoss}.png"
                ):
                    adb_click(__last_pos)
                elif image_exists(_temp_path, "data/multiplayer.png"):
                    adb_click(__last_pos)
                    state = 1
                    output_log("进入准备界面。")
            pos = image_to_pos(_temp_path, "data/close.png")
            if pos != False:
                adb_click(pos)
            time.sleep(0.25)
        elif state == 1:  # In Prepare State.
            if goto_bonus:
                if image_exists(_temp_path, "data/back.png"):
                    adb_click(__last_pos)
            # Check if auto is enabled.
            elif image_exists(_temp_path, "data/auto_disabled.png") or image_exists(
                _temp_path, "data/auto_continue_disabled_type2.png"
            ):
                output_log("检测到自动模式关闭。打开自动模式。")
                adb_click(__last_pos)
                time.sleep(0.2)
            elif image_exists(_temp_path, "data/auto_continue_disabled.png"):
                output_log("检测到自动续战关闭。打开自动续战。")
                adb_click(__last_pos)
                time.sleep(0.2)
            elif (
                not recruited
                and matchTag != 0
                and image_exists(_temp_path, "data/recruit.png")
            ):
                recruited = True
                match_tag_check(matchTag)
            elif image_exists(_temp_path, "data/stamina_low.png"):
                stamina_recover()
            # elif image_exists(_temp_path, "data/raid_event_go.png"):
            #     adb_click(__last_pos)
            # Switch to battle waiting state.
            # state = 10
            elif image_exists(_temp_path, "data/battle_indicator.png"):
                state = 10
                recruited = False
            time.sleep(0.25)
        elif state == 2:  # Battle State
            # Auto close for one sec
            if auto_close_at_beginning:
                if time.time() - auto_close_timer > AUTO_CLOSE_TIME and auto_closed:
                    adb_click(AUTO_POSITION)
                    time.sleep(0.05)
                    adb_click((300, 300))
                    auto_closed = False
            # If jump back to prepare state (Game over)
            if image_exists(_temp_path, "data/copy_room_number.png"):
                state = 1
            # Else if time limit exceeds
            elif (
                BATTLE_TIME_THRESHOLD > 0
                and time.time() - battle_start_time >= BATTLE_TIME_THRESHOLD
            ):
                output_log("超时，重试战斗。")
                battle_rounds_failure += 1
                state = 4
            # Else if quest clear
            elif (
                image_exists(_temp_path, "data/quest_clear.png")
                or image_exists(_temp_path, "data/quest_clear_2.png")
                or image_exists(_temp_path, "data/stage_clear.png")
            ):
                output_log(
                    f"QUEST CLEAR ! Time used: {time.time() - battle_start_time:.2f}s"
                )
                # Every 100 rounds get to bonus page
                if (
                    battle_rounds - battle_rounds_failure
                ) % BONUS_ROUND == 0 and battle_rounds - battle_rounds_failure > 0:
                    output_log(f"检测到已经通过 {BONUS_ROUND} 轮。准备前往领取奖励。")
                    goto_bonus = True
                state = 3
            elif auto_tap:
                adb_click([300, 300])
            time.sleep(0.1)
        elif state == 3:  # Clear stage
            if image_exists(_temp_path, "data/continue.png"):
                # Disable show if enabled.
                pos = image_to_pos(_temp_path, "data/show_enabled.png")
                if pos != False:
                    adb_click(pos)
                    time.sleep(0.25)
                pos = image_to_pos(_temp_path, "data/continue.png")
                adb_click(pos)
            elif goto_bonus and (image_exists(_temp_path, "data/disband_type2.png")):
                adb_click(__last_pos)
                state = 0
                output_log("结算完毕，前往领取奖励。")
            elif goto_bonus and (image_exists(_temp_path, "data/cancel.png")):
                adb_click(__last_pos)
            elif not goto_bonus and image_exists(_temp_path, "data/back_to_room.png"):
                pos = __last_pos
                adb_click(pos)
                output_log("结算完毕，回到准备界面。")
                if limit_rounds > 0 and battle_rounds >= limit_rounds:
                    output_log("战斗达到限制上限。退出该任务。")
                    return
            elif image_exists(_temp_path, "data/close.png"):
                pos = __last_pos
                adb_click(pos)
            elif image_exists(_temp_path, "data/stamina_low.png"):
                stamina_recover()
            elif image_exists(_temp_path, "data/copy_room_number.png"):
                output_log("回到准备界面。")
                battle_rounds_failure += 1
                state = 1
            time.sleep(0.5)
        elif state == 4:  # Battle retrying State
            if image_exists(_temp_path, "data/stage_clear.png"):
                state = 3
            elif image_exists(_temp_path, "data/copy_room_number.png"):
                state = 1
            elif image_exists(_temp_path, "data/story_event_indicator.png"):
                state = 0
            elif image_exists(_temp_path, "data/pause.png") or image_exists(
                _temp_path, "data/battle_retry.png"
            ):
                adb_click(__last_pos)
            elif image_exists(_temp_path, "data/ok.png"):
                adb_click(__last_pos)
                state = 10
            time.sleep(0.2)
        elif state == 10:  # Battle Waiting State
            if image_exists(_temp_path, "data/battle_indicator.png"):
                state = 2
                battle_start_time = time.time()
                battle_rounds += 1
                auto_close_timer = 0
                failure_rate = 0.0
                if battle_rounds > 1:
                    failure_rate = battle_rounds_failure / (battle_rounds - 1) * 100
                output_log(f"战斗开始。当前第 {battle_rounds} 轮，翻车率为 {failure_rate:.2f}%。")
                output_log(f"目前通过共 {battle_rounds - 1 - battle_rounds_failure} 轮。")
                output_log(f"总耗时为 {time.time() - program_start_time:.2f}s。")
                if battle_rounds - 1 - battle_rounds_failure > 0:
                    output_log(
                        f"平均速度为 {(time.time() - program_start_time)/(battle_rounds - 1 - battle_rounds_failure):.2f} 秒/轮。"
                    )
                if auto_tap:
                    adb_click([300, 300])
                if auto_close_at_beginning:
                    adb_click(AUTO_POSITION)
                    auto_close_timer = time.time()
                    auto_closed = True
            elif image_exists(_temp_path, "data/stamina_low.png"):
                stamina_recover()
            time.sleep(0.1)
        else:
            time.sleep(0.75)


def main(dev_config):
    global device_id
    device_id = dev_config["address"]
    global device_tag
    device_tag = dev_config["tag"]
    global _temp_path
    _temp_path = f"temp/temp_{device_id}.png"
    target = "RAID"
    target_state = 1

    state = 0
    output_log("进入主程序。")
    task_loop = dev_config.get("task_loop", False)
    while True:
        for task in dev_config["tasks"]:
            target = task["type"]
            if not task.get("enabled", True):
                output_log(f"任务（{target}）已停用。跳过。")
                continue
            # Decide target page
            if target == "RAID" or target == "EVENTS":
                target_state = 1
            while True:
                adb_screenshot()
                if state == 0:  # If on main page
                    # Page check & State switch
                    if image_exists(_temp_path, "data/raid_event_main.png"):
                        raid_event(task["settings"])
                    elif image_exists(_temp_path, "data/events_main.png"):
                        output_log("进入活动页面。")
                        state = 1
                    elif (
                        image_exists(_temp_path, "data/close.png")
                        or image_exists(_temp_path, "data/close_red.png")
                        or image_exists(_temp_path, "data/ok.png")
                        or image_exists(_temp_path, "data/give_up.png")
                        or image_exists(_temp_path, "data/back.png")
                        or image_exists(_temp_path, "data/disband.png")
                        or image_exists(_temp_path, "data/cancel.png")
                    ):
                        adb_click(__last_pos)
                    # If on main page
                    else:
                        if target_state == 1 and (
                            image_exists(_temp_path, "data/events.png")
                            or image_exists(_temp_path, "data/events_type2.png")
                        ):
                            adb_click(__last_pos)
                        else:
                            adb_click([1024 / 2, 768 / 2])
                elif state == 1:  # If on event page
                    if target == "RAID" and image_exists(
                        _temp_path, "data/raid_event_banner.png"
                    ):
                        adb_click(__last_pos)
                        raid_event(task["settings"])
                        break
                    elif target == "EVENTS":
                        targetEvent = task["settings"]["event"].lower()
                        if image_exists(
                            _temp_path, f"data/event_{targetEvent}_banner.png"
                        ):
                            adb_click(__last_pos)
                            time.sleep(1)
                            story_events(task["settings"])
                            break
                        else:
                            output_log(f"未在屏幕上找到目标活动 {targetEvent}。")
                    elif not image_exists(_temp_path, "data/events_main.png"):
                        output_log("离开了活动页面。回到主程序。")
                        state = 0
                    else:
                        output_log("警告 - 未检测到目标 / 未设定目标。尝试回到主页面。")
                        if image_exists(_temp_path, "data/back.png"):
                            adb_click(__last_pos)
                time.sleep(0.5)
        if not task_loop:
            break


def dev_loop(dev):
    main(dev)
    output_log("所有任务执行完毕。退出程序。")


import multiprocessing as mp

if __name__ == "__main__":
    print("Script intializing.")
    global config
    with open("config.json", encoding="utf-8") as f:
        if not f.readable:
            print("Config file not exists.")
            exit()
        config = json.loads(f.read())

    adb_reset()
    print("Script Initialized. Start main program.")

    devices = config["devices"]
    p_list = []
    for dev in devices:
        if dev.get("enabled", True):
            dev.setdefault("tag", "unknown device")
            try:
                bad = adb_connect(dev["address"])
                if bad:
                    raise
            except:
                print(f"Connect failed. Skip device {dev['tag']}")
                continue
            print(f"Start subprocess of device {dev['tag']}")
            p = mp.Process(target=dev_loop, args=(dev,))
            p.start()
            p_list.append(p)
    for p in p_list:
        p.join()
