##########################################################################
#
#    WooferBot, an interactive BrowserSource Bot for streamers
#    Copyright (C) 2019  Tomaae
#    (https://wooferbot.com/)
#
#    This file is part of WooferBot.
#
#    WooferBot is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
##########################################################################

from uuid import uuid4
from random import SystemRandom
from threading import Timer, Thread
from time import time, sleep
from os import path, system
from pynput.keyboard import Key, Controller
from lib.twitch import twitch_get_user, twitch_get_last_activity


# ---------------------------
#   Woofer logic
# ---------------------------
class Woofer:
    def __init__(self, settings, overlay, nanoleaf, hue, yeelight, chatbot):
        self.settings = settings
        self.overlay = overlay
        self.nanoleaf = nanoleaf
        self.hue = hue
        self.yeelight = yeelight
        self.chatbot = chatbot

        self.keyboard = Controller()

        self.queue = []
        self.greetedUsers = []
        self.greetedUsers.append(self.settings.TwitchChannel)
        self.greetedUsers.append(self.settings.TwitchChannel + "bot")

        self.lurkingUsers = []
        self.unlurkingUsers = []
        self.hostingUsers = []
        self.shoutoutUsers = []
        self.commandsViewerOnce = {}
        self.commandsViewerTimeout = {}
        self.commandsGlobalTimeout = {}

        self.changedLightsNanoleaf = ""
        self.changedLightsHue = {}
        self.changedLightsYeelight = {}

        # Start timer for ScheduledMessages
        Timer(300, self.woofer_timers).start()

    # ---------------------------
    #   ProcessJson
    # ---------------------------
    def ProcessJson(self, jsonData):
        #
        # Commands
        #
        if jsonData["custom-tag"] == "command":
            # Shoutout
            if jsonData["command"] in ["!so", "!shoutout"]:
                self.woofer_shoutout(jsonData)

            # Lurk/unlurk
            elif jsonData["command"] in ["!lurk", "!unlurk", "!back"]:
                if jsonData["command"] == "!lurk":
                    self.woofer_lurk(jsonData)
                else:
                    self.woofer_unlurk(jsonData)

            # Custom commands
            elif jsonData["command"] in self.settings.Commands:
                self.woofer_commands(jsonData)

            # Search command aliases
            else:
                for action in self.settings.Commands:
                    for alias in self.settings.Commands[action]["Aliases"]:
                        if jsonData["command"] == alias:
                            jsonData["command"] = action
                            self.woofer_commands(jsonData)

        #
        # Messages
        #
        elif jsonData["custom-tag"] == "message":
            common_bots = set(self.settings.commonBots)
            custom_bots = set(self.settings.Bots)
            # Alerts from chatbots
            if jsonData["sender"] in common_bots or jsonData["sender"] in custom_bots:
                # Follow
                if jsonData["message"].find(self.settings.FollowMessage) > 0:
                    line = jsonData["message"].split(" ")
                    jsonData["display-name"] = line[0].rstrip(",")
                    jsonData["custom-tag"] = "follow"
                    self.woofer_alert(jsonData)

                return

            # MinLines increase for timers
            self.settings.scheduleLines += 1

            # Greeting
            if jsonData["sender"] not in common_bots and jsonData["sender"] not in custom_bots:
                self.woofer_greet(jsonData)

            # Channel points default
            elif jsonData["msg-id"] == "highlighted-message":
                print("Channel points, claimed reward: Redeemed Highlight My Message")

            # Channel points custom w/message
            elif jsonData["custom-reward-id"]:
                print("Channel points, claimed custom reward: {}".format(jsonData["custom-reward-id"]))

            # Bits
            elif int(jsonData["bits"]) > 0 and int(jsonData["bits"]) >= self.settings.MinBits:
                jsonData["custom-tag"] = "bits"
                self.woofer_alert(jsonData)

        #
        # Rituals
        #
        elif jsonData["custom-tag"] in \
                ["new_chatter", "raid", "host", "autohost", "sub", "resub", "subgift", "anonsubgift"]:
            self.woofer_alert(jsonData)

    # ---------------------------
    #   woofer_queue
    # ---------------------------
    def woofer_queue(self, queue_id, jsonData):
        #
        # Check if there is somethign in queue
        #
        if not self.queue:
            return

        #
        # Check if overlay is connected
        #
        if self.overlay.active < 1:
            print("waiting for overlay")
            Timer(3, self.woofer_queue, args=(queue_id, jsonData)).start()
            return

        #
        # Check if our turn in queue
        #
        if self.queue[0] != queue_id:
            Timer(0.5, self.woofer_queue, args=(queue_id, jsonData)).start()
            return

        #
        # Send to overlay, retry later if overlay buffer is full
        #
        if self.overlay.Send("EVENT_WOOFERBOT", jsonData) == 1:
            Timer(1, self.woofer_queue, args=(queue_id, jsonData)).start()
            return

        #
        # Execute custom scripts
        #
        if "script" in jsonData and jsonData["script"] != "":
            system("\"" + jsonData["script"] + "\"")

        #
        # Execute hotkey
        #
        if "hotkey" in jsonData and jsonData["hotkey"] != "":
            keylist = {"space": Key.space,
                       "alt": Key.alt,
                       "ctrl": Key.ctrl,
                       "shift": Key.shift,
                       "f1": Key.f1,
                       "f2": Key.f2,
                       "f3": Key.f3,
                       "f4": Key.f4,
                       "f5": Key.f5,
                       "f6": Key.f6,
                       "f7": Key.f7,
                       "f8": Key.f8,
                       "f9": Key.f9,
                       "f10": Key.f10,
                       "f11": Key.f11,
                       "f12": Key.f12,
                       "left": Key.left,
                       "right": Key.right,
                       "up": Key.up,
                       "down": Key.down,
                       "backspace": Key.backspace,
                       "cmd": Key.cmd,
                       "delete": Key.delete,
                       "end": Key.end,
                       "enter": Key.enter,
                       "esc": Key.esc,
                       "home": Key.home,
                       "insert": Key.insert,
                       "page_down": Key.page_down,
                       "page_up": Key.page_up,
                       "pause": Key.pause,
                       "print_screen": Key.print_screen,
                       "tab": Key.tab
                       }

            for key in jsonData["hotkey"]:
                if key in keylist:
                    try:
                        self.keyboard.press(keylist[key])
                    except:
                        print("Invalid hotkey in {}".format(jsonData["id"]))
                else:
                    try:
                        self.keyboard.press(key)
                    except:
                        print("Invalid hotkey in {}".format(jsonData["id"]))

            sleep(0.05)

            for key in reversed(jsonData["hotkey"]):
                if key in keylist:
                    try:
                        self.keyboard.release(keylist[key])
                    except:
                        print("Invalid hotkey in {}".format(jsonData["id"]))
                else:
                    try:
                        self.keyboard.release(key)
                    except:
                        print("Invalid hotkey in {}".format(jsonData["id"]))

        #
        # Turn on Nanoleaf
        #
        if "nanoleaf" in jsonData and jsonData["nanoleaf"] != "":
            self.nanoleaf.scene(jsonData["nanoleaf"])
            if "nanoleafpersistent" in jsonData and jsonData["nanoleafpersistent"]:
                self.changedLightsNanoleaf = jsonData["nanoleaf"]

        #
        # Turn on Hue
        #
        if "hue" in jsonData:
            for device in jsonData["hue"]:
                if "Brightness" in jsonData["hue"][device] and jsonData["hue"][device]["Brightness"] >= 1 and \
                        "Color" in jsonData["hue"][device] and 6 <= len(jsonData["hue"][device]["Color"]) <= 7:
                    self.hue.state(device=device,
                                   bri=jsonData["hue"][device]["Brightness"],
                                   col=jsonData["hue"][device]["Color"])

            if "huepersistent" in jsonData and jsonData["huepersistent"]:
                self.changedLightsHue = jsonData["hue"]

        #
        # Turn on Yeelight
        #
        if "yeelight" in jsonData:
            for device in jsonData["yeelight"]:
                if "Brightness" in jsonData["yeelight"][device] and jsonData["yeelight"][device]["Brightness"] >= 1 \
                        and "Color" in jsonData["yeelight"][device] and \
                        6 <= len(jsonData["yeelight"][device]["Color"]) <= 7:
                    self.yeelight.state(device=device,
                                        brightness=jsonData["yeelight"][device]["Brightness"],
                                        color=jsonData["yeelight"][device]["Color"],
                                        transition=jsonData["yeelight"][device]["Transition"],
                                        transitionTime=jsonData["yeelight"][device]["TransitionTime"])

            if "yeelightpersistent" in jsonData and jsonData["yeelightpersistent"]:
                self.changedLightsYeelight = jsonData["yeelight"]

        #
        # Reset to default after X seconds
        #
        Timer(jsonData["time"] / 1000, self.woofer_queue_default, args=(queue_id, jsonData)).start()

    # ---------------------------
    #   woofer_queue_default
    # ---------------------------
    def woofer_queue_default(self, queue_id, old_jsonData):
        #
        # Set default Idle image
        #
        mascotIdleImage = self.settings.mascotImages["Idle"]["Image"]
        if not path.isfile(mascotIdleImage):
            mascotIdleImage = ""

        #
        # Check mapping for custom Idle image
        #
        if "Idle" in self.settings.PoseMapping and "Image" in self.settings.PoseMapping["Idle"] and \
                self.settings.PoseMapping["Idle"]["Image"] in self.settings.mascotImages:
            tmp = self.settings.mascotImages[self.settings.PoseMapping["Idle"]["Image"]]["Image"]
            if path.isfile(tmp):
                mascotIdleImage = tmp

        #
        # Send to overlay, retry later if overlay buffer is full
        #
        jsonData = {
            "mascot": mascotIdleImage
        }
        if self.overlay.Send("EVENT_WOOFERBOT", jsonData) == 1:
            Timer(1, self.woofer_queue_default, args=(queue_id, old_jsonData)).start()
            return

        #
        # Reset Nanoleaf to Idle
        #
        if "nanoleaf" in old_jsonData and old_jsonData["nanoleaf"]:
            # Reset to persistent lights
            if self.changedLightsNanoleaf:
                self.nanoleaf.scene(self.changedLightsNanoleaf)
            # Reset to Idle lights
            elif "Idle" in self.settings.PoseMapping and "Nanoleaf" in self.settings.PoseMapping["Idle"]:
                self.nanoleaf.scene(self.settings.PoseMapping["Idle"]["Nanoleaf"])
            # Turn off lights
            else:
                self.nanoleaf.scene()

        #
        # Reset Hue to Idle
        #
        if "hue" in old_jsonData:
            # Reset to persistent lights
            if self.changedLightsHue:
                for device in self.changedLightsHue:
                    if "Brightness" in self.changedLightsHue[device] and \
                            self.changedLightsHue[device]["Brightness"] >= 1 and \
                            "Color" in self.changedLightsHue[device] and \
                            6 <= len(self.changedLightsHue[device]["Color"]) <= 7:
                        self.hue.state(device=device, bri=self.changedLightsHue[device]["Brightness"],
                                       col=self.changedLightsHue[device]["Color"])

                for device in old_jsonData["hue"]:
                    if "Brightness" in old_jsonData["hue"][device] and old_jsonData["hue"][device]["Brightness"] >= 1 \
                            and "Color" in old_jsonData["hue"][device] \
                            and 6 <= len(old_jsonData["hue"][device]["Color"]) <= 7:
                        if device not in self.changedLightsHue:
                            self.hue.state(device=device)

            # Reset to Idle lights
            elif "Idle" in self.settings.PoseMapping and "Hue" in self.settings.PoseMapping["Idle"]:
                for device in self.settings.PoseMapping["Idle"]["Hue"]:
                    if "Brightness" in self.settings.PoseMapping["Idle"]["Hue"][device] and \
                            self.settings.PoseMapping["Idle"]["Hue"][device]["Brightness"] >= 1 and \
                            "Color" in self.settings.PoseMapping["Idle"]["Hue"][device] and \
                            6 <= len(self.settings.PoseMapping["Idle"]["Hue"][device]["Color"]) <= 7:
                        self.hue.state(device=device,
                                       bri=self.settings.PoseMapping["Idle"]["Hue"][device]["Brightness"],
                                       col=self.settings.PoseMapping["Idle"]["Hue"][device]["Color"])

                for device in old_jsonData["hue"]:
                    if "Brightness" in old_jsonData["hue"][device] and old_jsonData["hue"][device]["Brightness"] >= 1 \
                            and "Color" in old_jsonData["hue"][device] and \
                            6 <= len(old_jsonData["hue"][device]["Color"]) <= 7:
                        if device not in self.settings.PoseMapping["Idle"]["Hue"]:
                            self.hue.state(device=device)

            # Turn off lights
            else:
                for device in old_jsonData["hue"]:
                    if "Brightness" in old_jsonData["hue"][device] and old_jsonData["hue"][device]["Brightness"] >= 1 \
                            and "Color" in old_jsonData["hue"][device] and \
                            6 <= len(old_jsonData["hue"][device]["Color"]) <= 7:
                        self.hue.state(device=device)

        #
        # Reset Yeelight to Idle
        #
        if "yeelight" in old_jsonData:
            # Reset to persistent lights
            if self.changedLightsYeelight:
                for device in self.changedLightsYeelight:
                    if "Brightness" in self.changedLightsYeelight[device] and \
                            self.changedLightsYeelight[device]["Brightness"] >= 1 and \
                            "Color" in self.changedLightsYeelight[device] and \
                            6 <= len(self.changedLightsYeelight[device]["Color"]) <= 7:
                        self.yeelight.state(device=device, brightness=self.changedLightsYeelight[device]["Brightness"],
                                            color=self.changedLightsYeelight[device]["Color"],
                                            transition=self.changedLightsYeelight[device]["Transition"],
                                            transitionTime=self.changedLightsYeelight[device]["TransitionTime"])

                for device in old_jsonData["yeelight"]:
                    if "Brightness" in old_jsonData["yeelight"][device] and \
                            old_jsonData["yeelight"][device]["Brightness"] >= 1 and \
                            "Color" in old_jsonData["yeelight"][device] and \
                            6 <= len(old_jsonData["yeelight"][device]["Color"]) <= 7:
                        if device not in self.changedLightsYeelight:
                            self.yeelight.state(device=device)

            # Reset to Idle lights
            elif "Idle" in self.settings.PoseMapping and "Yeelight" in self.settings.PoseMapping["Idle"]:
                for device in self.settings.PoseMapping["Idle"]["Yeelight"]:
                    if "Brightness" in self.settings.PoseMapping["Idle"]["Yeelight"][device] and \
                            self.settings.PoseMapping["Idle"]["Yeelight"][device]["Brightness"] >= 1 and \
                            "Color" in self.settings.PoseMapping["Idle"]["Yeelight"][device] and \
                            6 <= len(self.settings.PoseMapping["Idle"]["Yeelight"][device]["Color"]) <= 7:
                        self.yeelight.state(device=device,
                                            brightness=self.settings.PoseMapping["Idle"]["Yeelight"][device]["Brightness"],
                                            color=self.settings.PoseMapping["Idle"]["Yeelight"][device]["Color"],
                                            transition=self.settings.PoseMapping["Idle"]["Yeelight"][device]["Transition"],
                                            transitionTime=self.settings.PoseMapping["Idle"]["Yeelight"][device]["TransitionTime"])

                for device in old_jsonData["yeelight"]:
                    if "Brightness" in old_jsonData["yeelight"][device] and \
                            old_jsonData["yeelight"][device]["Brightness"] >= 1 and \
                            "Color" in old_jsonData["yeelight"][device] and \
                            6 <= len(old_jsonData["yeelight"][device]["Color"]) <= 7:
                        if device not in self.settings.PoseMapping["Idle"]["Yeelight"]:
                            self.yeelight.state(device=device)

            # Turn off lights
            else:
                for device in old_jsonData["yeelight"]:
                    if "Brightness" in old_jsonData["yeelight"][device] and \
                            old_jsonData["yeelight"][device]["Brightness"] >= 1 and \
                            "Color" in old_jsonData["yeelight"][device] and \
                            6 <= len(old_jsonData["yeelight"][device]["Color"]) <= 7:
                        self.yeelight.state(device=device)

        #
        # Remove notification from queue
        #
        if self.queue:
            self.queue.remove(queue_id)

    # ---------------------------
    #   woofer_addtoqueue
    # ---------------------------
    def woofer_addtoqueue(self, jsonResponse):
        print("{}: {}".format(jsonResponse["id"], jsonResponse["sender"]))

        if "message" not in jsonResponse or jsonResponse["message"] == "":
            if jsonResponse["id"] in self.settings.Messages:
                jsonResponse["message"] = SystemRandom().choice(self.settings.Messages[jsonResponse["id"]])
            else:
                jsonResponse["message"] = ""

        jsonResponse["mascot"] = self.mascotImagesFile(jsonResponse["id"])
        jsonResponse["mascotmouth"] = self.mascotImagesMouthHeight(jsonResponse["id"])
        jsonResponse["time"] = self.mascotImagesTime(jsonResponse["id"])
        jsonResponse["audio"] = self.mascotAudioFile(jsonResponse["id"])
        jsonResponse["volume"] = self.mascotAudioVolume(jsonResponse["id"])
        jsonResponse["nanoleaf"] = self.mascotNanoleafScene(jsonResponse["id"])
        jsonResponse["nanoleafpersistent"] = self.mascotNanoleafPersistent(jsonResponse["id"])
        jsonResponse["hue"] = self.mascotHueDevices(jsonResponse["id"])
        jsonResponse["huepersistent"] = self.mascotHuePersistent(jsonResponse["id"])
        jsonResponse["yeelight"] = self.mascotYeelightDevices(jsonResponse["id"])
        jsonResponse["yeelightpersistent"] = self.mascotYeelightPersistent(jsonResponse["id"])

        # Add to queue
        queue_id = uuid4()
        self.queue.append(queue_id)
        Thread(target=self.woofer_queue, args=(queue_id, jsonResponse)).start()

    # ---------------------------
    #   woofer_alert
    # ---------------------------
    def woofer_alert(self, jsonData):
        customId = jsonData["custom-tag"]
        if not self.settings.Enabled[customId]:
            return

        jsonFeed = {
            "sender": jsonData["display-name"]
        }

        #
        # sub/resub
        #
        if customId in ("sub", "resub"):
            for customObj in self.settings.CustomSubs:
                if customObj["Tier"] == "" and int(jsonData["months"]) >= int(customObj["From"]) and int(
                        jsonData["months"]) <= int(customObj["To"]):
                    customId = customObj["Name"]

            sub_tier = ""
            if jsonData["sub_tier"] == "Tier 1":
                sub_tier = "1"
            if jsonData["sub_tier"] == "Tier 2":
                sub_tier = "2"
            if jsonData["sub_tier"] == "Tier 3":
                sub_tier = "3"
            if jsonData["sub_tier"] == "Prime":
                sub_tier = "prime"

            for customObj in self.settings.CustomSubs:
                if sub_tier == customObj["Tier"] and int(jsonData["months"]) >= int(customObj["From"]) and int(
                        jsonData["months"]) <= int(customObj["To"]):
                    customId = customObj["Name"]

            jsonFeed["months"] = jsonData["months"]
            jsonFeed["months_streak"] = jsonData["months_streak"]
            jsonFeed["sub_tier"] = jsonData["sub_tier"]

        #
        # subgift/anonsubgift
        #
        if customId in ("subgift", "anonsubgift"):
            if jsonData["custom-tag"] == "anonsubgift":
                jsonData["display-name"] = "anonymous"

            jsonFeed["recipient"] = jsonData["msg-param-recipient-display-name"]
            jsonFeed["sub_tier"] = jsonData["sub_tier"]

        #
        # bits
        #
        if customId == "bits":
            for customObj in self.settings.CustomBits:
                if int(customObj["From"]) <= int(jsonData["bits"]) <= int(customObj["To"]):
                    customId = customObj["Name"]

            jsonFeed["bits"] = jsonData["bits"]

        #
        # host/raid
        #
        if customId in ("host", "raid"):
            # Check if user has already raided/hosted
            s = set(self.hostingUsers)
            if jsonData["sender"] in s:
                return

            self.hostingUsers.append(jsonData["sender"])

            if customId == "host":
                jsonFeed["sender"] = jsonData["sender"]

            if customId == "raid":
                jsonFeed["viewers"] = jsonData["viewers"]

        #
        # Send data
        #
        jsonFeed["id"] = customId
        self.woofer_addtoqueue(jsonFeed)

        if customId in ("host", "raid") and self.settings.AutoShoutout:
            jsonData["subscriber"] = "1"
            jsonData["vip"] = "1"
            jsonData["moderator"] = "1"
            jsonData["broadcaster"] = "1"
            jsonData["command_parameter"] = jsonData["display-name"]
            jsonData["custom-tag"] = "shoutout"
            Timer(self.settings.AutoShoutoutTime, self.woofer_shoutout, args=[jsonData]).start()

    # ---------------------------
    #   woofer_timers
    # ---------------------------
    def woofer_timers(self):
        # Check if overlay is connected
        if self.overlay.active < 1:
            Timer(30, self.woofer_timers).start()
            return

        # Check if timer is enabled
        MinLinesTimer = ""
        for action in self.settings.ScheduledMessages:
            if not action["Enabled"]:
                continue

            currentEpoch = int(time())
            if (currentEpoch - self.settings.scheduleTable[action["Name"]]) >= (action["Timer"] * 60):

                # Timers without MinLines limits
                if action["MinLines"] == 0:
                    self.settings.scheduleTable[action["Name"]] = currentEpoch

                    if "Command" in action:
                        self.woofer_commands({
                            "command": action["Command"],
                            "broadcaster": 1,
                            "sender": self.settings.TwitchChannel.lower(),
                            "display-name": self.settings.TwitchChannel,
                            "custom-tag": "command"
                        })
                    else:
                        self.woofer_addtoqueue({
                            "message": SystemRandom().choice(self.settings.Messages[action["Name"]]),
                            "image": self.settings.pathRoot + self.settings.slash + "images" + self.settings.slash + action["Image"],
                            "sender": "",
                            "customtag": "ScheduledMessage",
                            "id": action["Name"]
                        })

                # Check if timer with MinLines limits is executable
                if action["MinLines"] > 0:
                    if self.settings.scheduleLines < action["MinLines"]:
                        continue

                    if MinLinesTimer == "" or self.settings.scheduleTable[action["Name"]] < self.settings.scheduleTable[MinLinesTimer]:
                        MinLinesTimer = action["Name"]

        # Timers with MinLines limits
        if MinLinesTimer != "":
            for action in self.settings.ScheduledMessages:
                if action["Name"] != MinLinesTimer:
                    continue

                self.settings.scheduleLines = 0
                self.settings.scheduleTable[action["Name"]] = int(time())
                if "Command" in action:
                    self.woofer_commands({
                        "command": action["Command"],
                        "broadcaster": 1,
                        "sender": self.settings.TwitchChannel.lower(),
                        "display-name": self.settings.TwitchChannel,
                        "custom-tag": "command"
                    })
                else:
                    self.woofer_addtoqueue({
                        "message": SystemRandom().choice(self.settings.Messages[action["Name"]]),
                        "image": self.settings.pathRoot + self.settings.slash + "images" + self.settings.slash + action["Image"],
                        "sender": "",
                        "customtag": "ScheduledMessage",
                        "id": action["Name"]
                    })

        # Reset to default after X seconds
        Timer(30, self.woofer_timers).start()

    # ---------------------------
    #   woofer_commands
    # ---------------------------
    def woofer_commands(self, jsonData):
        #
        # Check if command is enabled
        #
        if not self.settings.Commands[jsonData["command"]]["Enabled"]:
            return

        #
        # Check access rights
        #
        if self.settings.Commands[jsonData["command"]]["Access"] != "":
            if int(jsonData["broadcaster"]) == 1:
                if self.settings.Commands[jsonData["command"]]["Access"] not in ["sub", "subs", "subscriber",
                                                                                 "subscribers", "vip", "vips", "mod",
                                                                                 "mods", "moderator", "moderators",
                                                                                 "broadcaster"]:
                    return
            elif int(jsonData["moderator"]) == 1:
                if self.settings.Commands[jsonData["command"]]["Access"] not in ["sub", "subs", "subscriber",
                                                                                 "subscribers", "vip", "vips", "mod",
                                                                                 "mods", "moderator", "moderators"]:
                    return
            elif int(jsonData["vip"]) == 1:
                if self.settings.Commands[jsonData["command"]]["Access"] not in ["sub", "subs", "subscriber",
                                                                                 "subscribers", "vip", "vips"]:
                    return
            elif int(jsonData["subscriber"]) == 1:
                if self.settings.Commands[jsonData["command"]]["Access"] not in ["sub", "subs", "subscriber",
                                                                                 "subscribers"]:
                    return
            else:
                return

        #
        # ViewerOnce
        #
        if self.settings.Commands[jsonData["command"]]["ViewerOnce"]:
            if jsonData["command"] in self.commandsViewerOnce and \
                    jsonData["sender"] in self.commandsViewerOnce[jsonData["command"]]:
                return

            if jsonData["command"] not in self.commandsViewerOnce:
                self.commandsViewerOnce[jsonData["command"]] = []

            self.commandsViewerOnce[jsonData["command"]].append(jsonData["sender"])

        #
        # ViewerTimeout
        #
        if self.settings.Commands[jsonData["command"]]["ViewerTimeout"] > 0:
            currentEpoch = int(time())

            if jsonData["command"] in self.commandsViewerTimeout and \
                    jsonData["sender"] in self.commandsViewerTimeout[jsonData["command"]] and \
                    (currentEpoch - self.commandsViewerTimeout[jsonData["command"]][jsonData["sender"]]) < self.settings.Commands[jsonData["command"]]["ViewerTimeout"]:
                return

            if jsonData["command"] not in self.commandsViewerTimeout:
                self.commandsViewerTimeout[jsonData["command"]] = {}

            self.commandsViewerTimeout[jsonData["command"]][jsonData["sender"]] = currentEpoch

        #
        # GlobalTimeout
        #
        if self.settings.Commands[jsonData["command"]]["GlobalTimeout"] > 0:
            currentEpoch = int(time())
            if jsonData["command"] in self.commandsGlobalTimeout and (
                    currentEpoch - self.commandsGlobalTimeout[jsonData["command"]]) < \
                    self.settings.Commands[jsonData["command"]]["GlobalTimeout"]:
                return

            self.commandsGlobalTimeout[jsonData["command"]] = currentEpoch

        #
        # Check custom image
        #
        image = ""
        if self.settings.Commands[jsonData["command"]]["Image"] != "":
            image = self.settings.pathRoot + self.settings.slash + "images" + self.settings.slash + \
                    self.settings.Commands[jsonData["command"]]["Image"]
            if not path.isfile(image):
                image = ""

        #
        # Check custom script
        #
        script = ""
        if self.settings.Commands[jsonData["command"]]["Script"] != "":
            script = self.settings.pathRoot + self.settings.slash + "scripts" + self.settings.slash + \
                     self.settings.Commands[jsonData["command"]]["Script"]
            if not path.isfile(script):
                script = ""

        self.woofer_addtoqueue({
            "image": image,
            "script": script,
            "hotkey": self.settings.Commands[jsonData["command"]]["Hotkey"],
            "sender": jsonData["display-name"],
            "id": jsonData["command"]
        })

    # ---------------------------
    #   woofer_greet
    # ---------------------------
    def woofer_greet(self, jsonData):
        if not self.settings.Enabled["greet"]:
            return

        # Check if user was already greeted
        s = set(self.greetedUsers)
        if jsonData["sender"] in s:
            return

        self.greetedUsers.append(jsonData["sender"])

        # Check for custom greeting definitions
        customMessage = ""
        if "viewer_" + jsonData["display-name"] in self.settings.Messages:
            customMessage = SystemRandom().choice(self.settings.Messages["viewer_" + jsonData["display-name"]])

        customId = "greet"
        if "viewer_" + jsonData["display-name"] in self.settings.PoseMapping:
            customId = "viewer_" + jsonData["display-name"]

        self.woofer_addtoqueue({
            "message": customMessage,
            "sender": jsonData["display-name"],
            "id": customId
        })

    # ---------------------------
    #   woofer_lurk
    # ---------------------------
    def woofer_lurk(self, jsonData):
        if not self.settings.Enabled["lurk"]:
            return

        # Check if user was already lurking
        s = set(self.lurkingUsers)
        if jsonData["sender"] in s:
            return

        self.lurkingUsers.append(jsonData["sender"])

        self.woofer_addtoqueue({
            "sender": jsonData["display-name"],
            "id": "lurk"
        })

    # ---------------------------
    #   woofer_unlurk
    # ---------------------------
    def woofer_unlurk(self, jsonData):
        if not self.settings.Enabled["lurk"]:
            return

        # Check if user was already lurking
        s = set(self.lurkingUsers)
        if jsonData["sender"] not in s:
            return

        # Check if user already used unlurk
        s = set(self.unlurkingUsers)
        if jsonData["sender"] in s:
            return

        self.unlurkingUsers.append(jsonData["sender"])

        self.woofer_addtoqueue({
            "sender": jsonData["display-name"],
            "id": "unlurk"
        })

    # ---------------------------
    #   woofer_shoutout
    # ---------------------------
    def woofer_shoutout(self, jsonData):
        if not self.settings.Enabled["shoutout"]:
            return
        #
        # Check access rights
        #
        if self.settings.ShoutoutAccess != "":
            if int(jsonData["broadcaster"]) == 1:
                if self.settings.ShoutoutAccess not in ["sub", "subs", "subscriber", "subscribers", "vip", "vips",
                                                        "mod", "mods", "moderator", "moderators", "broadcaster"]:
                    return
            elif int(jsonData["moderator"]) == 1:
                if self.settings.ShoutoutAccess not in ["sub", "subs", "subscriber", "subscribers", "vip", "vips",
                                                        "mod", "mods", "moderator", "moderators"]:
                    return
            elif int(jsonData["vip"]) == 1:
                if self.settings.ShoutoutAccess not in ["sub", "subs", "subscriber", "subscribers", "vip", "vips"]:
                    return
            elif int(jsonData["subscriber"]) == 1:
                if self.settings.ShoutoutAccess not in ["sub", "subs", "subscriber", "subscribers"]:
                    return
            else:
                return

        #
        # Check if channel parameter was specified
        #
        if not jsonData["command_parameter"]:
            return

        if jsonData["command_parameter"].find("@") == 0:
            jsonData["command_parameter"] = jsonData["command_parameter"][1:]

        #
        # Get user info
        #
        jsonResult = twitch_get_user(self.settings.twitchClientID, jsonData["command_parameter"])
        if not jsonResult:
            return

        s = set(self.shoutoutUsers)
        if jsonResult["display_name"] in s:
            return

        self.shoutoutUsers.append(jsonResult["display_name"])

        #
        # Get channel last game
        #
        activity = twitch_get_last_activity(self.settings.twitchClientID, jsonResult["_id"])
        activity_text = ""
        if activity:
            activity_text = SystemRandom().choice(self.settings.Activities["Game"])
            if activity in self.settings.Activities:
                activity_text = SystemRandom().choice(self.settings.Activities[activity])

        self.woofer_addtoqueue({
            "message": SystemRandom().choice(self.settings.Messages["shoutout"]) + activity_text,
            "sender": jsonData["display-name"],
            "recipient": jsonResult["display_name"],
            "activity": activity,
            "image": jsonResult["logo"],
            "id": "shoutout"
        })

    # ---------------------------
    #   mascotImagesFile
    # ---------------------------
    def mascotImagesFile(self, action):
        if action in self.settings.PoseMapping and self.settings.PoseMapping[action]["Image"] in self.settings.mascotImages:
            tmp = self.settings.mascotImages[self.settings.PoseMapping[action]["Image"]]["Image"]
            if path.isfile(tmp):
                return tmp

        return self.settings.mascotImages[self.settings.PoseMapping["DEFAULT"]["Image"]]["Image"]

    # ---------------------------
    #   mascotImagesMouthHeight
    # ---------------------------
    def mascotImagesMouthHeight(self, action):
        if action in self.settings.PoseMapping and \
                self.settings.PoseMapping[action]["Image"] in self.settings.mascotImages and \
                "MouthHeight" in self.settings.mascotImages[self.settings.PoseMapping[action]["Image"]]:
            MouthHeight = self.settings.mascotImages[self.settings.PoseMapping[action]["Image"]]["MouthHeight"]
            if MouthHeight in ("", 0):
                return 80
            return MouthHeight - 5

        return self.settings.mascotImages[self.settings.PoseMapping["DEFAULT"]["Image"]]["MouthHeight"] - 5

    # ---------------------------
    #   mascotImagesTime
    # ---------------------------
    def mascotImagesTime(self, action):
        if action in self.settings.PoseMapping and self.settings.PoseMapping[action]["Image"] in self.settings.mascotImages:
            return self.settings.mascotImages[self.settings.PoseMapping[action]["Image"]]["Time"]

        return self.settings.mascotImages[self.settings.PoseMapping["DEFAULT"]["Image"]]["Time"]

    # ---------------------------
    #   mascotAudioFile
    # ---------------------------
    def mascotAudioFile(self, action):
        if action in self.settings.PoseMapping and self.settings.PoseMapping[action]["Audio"] in self.settings.mascotAudio:
            tmp = SystemRandom().choice(self.settings.mascotAudio[self.settings.PoseMapping[action]["Audio"]]["Audio"])
            if path.isfile(tmp):
                return tmp

        if self.settings.PoseMapping["DEFAULT"]["Audio"] in self.settings.mascotAudio:
            return SystemRandom().choice(self.settings.mascotAudio[self.settings.PoseMapping["DEFAULT"]["Audio"]]["Audio"])

        return ""

    # ---------------------------
    #   mascotAudioVolume
    # ---------------------------
    def mascotAudioVolume(self, action):
        if action in self.settings.PoseMapping and self.settings.PoseMapping[action]["Audio"] in self.settings.mascotAudio:
            return self.settings.mascotAudio[self.settings.PoseMapping[action]["Audio"]]["Volume"]

        return self.settings.GlobalVolume

    # ---------------------------
    #   mascotNanoleafScene
    # ---------------------------
    def mascotNanoleafScene(self, action):
        if action in self.settings.PoseMapping and "Nanoleaf" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["Nanoleaf"]

        if "Nanoleaf" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["Nanoleaf"]

        return ""

    # ---------------------------
    #   mascotNanoleafPersistent
    # ---------------------------
    def mascotNanoleafPersistent(self, action):
        if action in self.settings.PoseMapping and "NanoleafPersistent" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["NanoleafPersistent"]

        if "NanoleafPersistent" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["NanoleafPersistent"]

        return ""

    # ---------------------------
    #   mascotHueDevices
    # ---------------------------
    def mascotHueDevices(self, action):
        if action in self.settings.PoseMapping and "Hue" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["Hue"]

        if "Hue" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["Hue"]

        return ""

    # ---------------------------
    #   mascotHuePersistent
    # ---------------------------
    def mascotHuePersistent(self, action):
        if action in self.settings.PoseMapping and "HuePersistent" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["HuePersistent"]

        if "HuePersistent" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["HuePersistent"]

        return ""

    # ---------------------------
    #   mascotYeelightDevices
    # ---------------------------
    def mascotYeelightDevices(self, action):
        if action in self.settings.PoseMapping and "Yeelight" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["Yeelight"]

        if "Yeelight" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["Yeelight"]

        return ""

    # ---------------------------
    #   mascotYeelightPersistent
    # ---------------------------
    def mascotYeelightPersistent(self, action):
        if action in self.settings.PoseMapping and "YeelightPersistent" in self.settings.PoseMapping[action]:
            return self.settings.PoseMapping[action]["YeelightPersistent"]

        if "YeelightPersistent" in self.settings.PoseMapping["DEFAULT"]:
            return self.settings.PoseMapping["DEFAULT"]["YeelightPersistent"]

        return ""
