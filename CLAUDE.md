# Claude Desk Buddy (hackathon project, demo on Nov 22, 2026)

A 3D-printed Claude mascot that sits on the desk. When Claude Code finishes a task
and the user is distracted (scrolling their phone), it yells at them through a
speaker and shows an angry face on a 2.8" TFT display. A big "slam" button sends a
"that was bad, redo it" prompt to Claude Code.

## How it works

Claude Code hooks (HTTP) -> FastAPI daemon on the Mac -> (USB serial) -> STM32 -> TFT face
STM32 button -> (USB serial "BTN") -> daemon -> `tmux send-keys` -> Claude Code
Phone in the toy opens http://<laptop IP>:8765/face: it draws the face AND plays the voice
(daemon sets a sound order in /face/state, the page plays /face/sounds/<clip>.mp3). Falls back to
`afplay` on the laptop when no phone with sound on is polling, or always with BUDDY_AUDIO=laptop.
(The STM32 speaker on D7 was ditched on Nov 21; the firmware audio code is still there, unused.)
Webcam -> MediaPipe (head angle + eyes) -> daemon decides "looking at the screen or not"

Everything smart runs on the laptop. The STM32 only draws the face and reports
button presses.

## Repo layout

- `.claude/buddy-hooks.json` (NOT settings.json, Nov 22): HTTP hooks, loaded only by a chat started
  with `claude --settings .claude/buddy-hooks.json` (knock-knock chats start that way). In
  settings.json every Claude chat in the folder fired them, including the VS Code chat used for
  building: it set WORKING (taps ignored), nagged after its replies, and a tap undid ITS edits.
  Hooks: (UserPromptSubmit, Stop, Notification with
  matcher `permission_prompt` only, PreToolUse with matcher `Edit|Write|MultiEdit|NotebookEdit`,
  PostToolUse for every tool) posting to `http://127.0.0.1:8765/hooks/...`
- `laptop/` (Python, FastAPI, run from this folder)
  - `buddy/main.py`: creates the app, includes routers
  - `buddy/state.py`: BuddyState enum: IDLE, WORKING, DONE, NEEDS_YOU, ANNOYED, YELLING
  - `buddy/dependencies.py`: builds the single BuddyService and picks its
    output / speaker / detector. Only file to edit when swapping implementations.
  - `buddy/api/hooks.py`: POST /hooks/prompt-submit, /hooks/stop, /hooks/notification,
    /hooks/pre-tool-use (file path only; reply 204, never blocks), /hooks/post-tool-use (ends
    the permission nag once the prompt was answered; payload not read)
  - `buddy/checkpoint.py`: TurnCheckpoint, in-memory copies of files from before Claude's
    first edit of each file in the latest turn; undo() restores them, deletes files Claude created
  - `buddy/api/status.py`: GET /status (also state text, change_id, source for the mood page)
  - `buddy/api/mood.py`: POST /mood, GET/PUT/DELETE /messages (used by the mood page)
  - `buddy/messages.py`: MessageStore, the editable LCD text per mood (16 chars, printable ASCII)
  - `buddy/static/`: the mood page, served at http://127.0.0.1:8765/
  - `buddy/api/face.py` + `buddy/static/face.html`: the phone face (the TFT broke). GET /face is
    the page (canvas eyes, same drawing as firmware face.c, eyes at the screen edges); it polls
    GET /face/state ({state, reaction_id, sound_id, sound}) every 0.3 s. reaction_id goes up on
    each slap and button press, and the page shows `> <` for 1.5 s. The page is also the speaker:
    "Tap for sound" until tapped once (phones block sound without a tap), then it polls with
    `?audio=1` and plays /face/sounds/<sound>.mp3 whenever sound_id changes (sound null = stop).
    GET /face/sounds lists the clips (the page preloads them).
  - `buddy/outputs/phone_audio.py`: PhoneAudio, the latest sound order (sound_id, sound) and when a
    page with sound on last polled; is_connected() = polled with audio=1 in the last 2 s.
  - `buddy/main.py` middleware `local_only`: requests from other devices may only GET /face,
    /face/state, /face/sounds and /face/sounds/* (403 for everything else), because the server
    listens on the network for the phone. Clip names are checked against the sounds folder.
  - `buddy/api/camera.py`: POST /calibrate (re-measure the "working" head position, 3 s)
  - `buddy/api/button.py`: POST /button (redo button by curl; the STM32 button calls the same
    service method through serial_output). POST /slap (fake head slap). Replies {"result": ...}
  - `buddy/services/buddy_service.py`: all logic, including the nag timer
  - `buddy/outputs/console_output.py`: prints state to the terminal (used with BUDDY_NO_SERIAL=1)
  - `buddy/outputs/serial_output.py`: sends `F:`/`T:` lines to the STM32 (pyserial, auto-finds
    `/dev/cu.usbmodem*`), also prints like ConsoleOutput; reader thread turns `BTN` into
    `on_button_pressed()` via `asyncio.run_coroutine_threadsafe` (wired in main.py lifespan)
  - `buddy/outputs/speaker.py`: play(name): phone connected -> PhoneAudio.play(name), busy time
    from clip lengths measured with `afinfo` at startup (+0.5 s polling delay); else
    `afplay sounds/<name>.mp3` (list args, no shell). Cuts off the previous clip.
    is_busy(), current_sound(), stop().
    speak(text) (macOS `say`) is no longer used. has_sound(name) checks the .mp3 exists.
  - `buddy/sounds/*.mp3`: voice lines made with ElevenLabs (free plan: non-commercial use,
    credit "Voice: ElevenLabs"). Custom voice "Claude Buddy": deadpan, tired, passive-aggressive,
    young adult American man. Grouped by moment in SOUND_GROUPS (buddy_service.py): a random line per
    moment, never the same twice in a row; names without an .mp3 yet are skipped (just record them:
    busy_1, busy_2, redo_failed, yay_2, annoyed_3, yelling_3, undo_2 were planned but not recorded).
  - `buddy/outputs/window_focuser.py`: `lsappinfo` tells which app is in front; `open -b <id>`
    brings the Claude Code app to the front (BUDDY_CLAUDE_APP_ID, default com.apple.Terminal).
    is_in_front() is True for any work app: Terminal or VS Code.
  - `buddy/outputs/tmux_typer.py`: types text into tmux session `claude`, waits 0.5 s, presses Enter
  - `buddy/detectors/attention_detector.py`: webcam + MediaPipe Face Landmarker in a
    background thread (15 fps). Not looking = head down > 10 deg vs calibrated working
    position, head turned > 30 deg, eyeLookDown or eyeBlink 0.35 above baseline, or no
    face. is_distracted() = not looking for 2 s (0.5 s gaps ignored). Calibrates during
    the first 3 s with a face. Model auto-downloads to laptop/models/ (gitignored).
  - `buddy/detectors/always_distracted.py`: stub, always True (BUDDY_NO_CAMERA=1)
  - `camera_test.py`: run the detector alone with a video window and live numbers
    (c = recalibrate, q = quit). `python camera_test.py 1` for another camera.
- `firmware/Claude-buddy/`: STM32CubeIDE 2.x project (code generated by standalone STM32CubeMX
  from `Claude-buddy.ioc`; CubeIDE 2.x has no built-in CubeMX). Own code: `Core/Src/ili9341.c`
  (display driver), `face.c` (eyes and moods), `link.c` (serial protocol), `accel.c` (slap
  detection with the onboard LSM6DSL), `audio.c` (voice clips: DAC1 ch1 on PA4/D7, TIM6 interrupt
  at 8 kHz writes DHR8R1; direct registers, no CubeMX/HAL DAC, PA4 is unconfigured in the .ioc),
  `audio_clips.c` (GENERATED by `firmware/tools/make_audio_clips.py` from laptop/buddy/sounds/*.mp3:
  8 kHz unsigned 8-bit, peak-normalised, VOLUME 0.6, plus a 0.25 s `beep` played at boot),
  user sections of `main.c`. After changing a clip: run the script, rebuild, flash.
- `firmware/legacy-lcd1602/`: old 1602 LCD driver, not built, kept for reference

## Running it (user's Mac, project at ~/Documents/desk-buddy)

- Terminal 1: `cd ~/Documents/desk-buddy/laptop && source .venv/bin/activate && uvicorn buddy.main:app --host 0.0.0.0 --port 8765`
  (`--host 0.0.0.0` lets the phone connect; the log prints `Phone face: open http://<ip>:8765/face`).
  Phone and laptop on the same network: easiest is the phone's hotspot with the laptop joined to it
  (hackathon Wi-Fi often blocks device-to-device traffic). Phone: auto-lock Never; iPhone: Safari
  "Add to Home Screen" for full screen.
  Env vars in front: `BUDDY_QUIET=1` prints `[PLAY] <file>` instead of playing sounds;
  `BUDDY_NO_CAMERA=1` uses AlwaysDistracted; `BUDDY_CAMERA=1` picks camera index 1;
  `BUDDY_NO_SERIAL=1` skips the STM32; `BUDDY_SERIAL=/dev/cu.usbmodemXXXX` picks the port;
  `BUDDY_CLAUDE_APP_ID=com.apple.Terminal` changes the app a tap brings forward (default com.apple.Terminal);
  `BUDDY_AUDIO=laptop` plays the voice on the laptop even when the phone has sound on.
  Plug the board in BEFORE starting the server (the port is only looked for at startup).
  Look at the screen while it starts (calibration). Recalibrate: `curl -X POST http://127.0.0.1:8765/calibrate`
- Terminal 2: `cd ~/Documents/desk-buddy && tmux new -s claude` (or `tmux attach -t claude`), then
  `claude --settings .claude/buddy-hooks.json` inside it (tmux session MUST be named `claude`:
  a bare `tmux` makes session `1` and taps/knocks go to the hidden `claude` one; only chats started
  with --settings drive the buddy; restart that chat after editing buddy-hooks.json)
- Fake button press: `curl -X POST http://127.0.0.1:8765/button`
- Fake head slap: `curl -X POST http://127.0.0.1:8765/slap`
- Plain `claude` (or the VS Code chat) in this folder fires NO hooks, so building doesn't disturb
  the buddy.
- IMPORTANT: hooks, `say`, the serial port and tmux all need the user's Mac. A cloud
  Claude Code session can edit this repo but cannot test any of that. Testing happens
  on the Mac after `git pull`.

## Behaviour implemented

- LCD text per mood comes from the message store (editable on the mood page, saved to
  ~/.config/claude-buddy/messages.json). Defaults: IDLE "zzz", WORKING "...", DONE "Done",
  NEEDS_YOU "!!!". ANNOYED/YELLING use the fixed lines in ESCALATION_STEPS.
- Prompt submitted -> WORKING, stops the watch loop, cuts off the current clip (except `slam`,
  so the redo prompt the button types doesn't cut off its own "Ow").
- Stop hook also plays a `yay` line.
  The camera is ignored while Claude works.
- Stop hook -> DONE, starts the watch loop
- Notification (permission_prompt) -> NEEDS_YOU, starts the watch loop
- "Locked in" = camera says you're looking at the screen AND a work app (Terminal or VS Code) is
  in front. Another app in front for 2 s (OTHER_APP_GRACE_SECONDS) or looking away (camera, 2 s)
  = not locked in.
- Watch loop (asyncio task, every 0.25 s, after Stop / permission Notification). Waits until
  you're not locked in, then nags: after DONE: ANNOYED `done` (0 s), `annoyed` (8 s), another
  `annoyed` (16 s), YELLING `yelling` (24 s), then a `yelling` line every 12 s FOREVER. After
  NEEDS_YOU: `needs_you` (0 s), `yelling` (8 s), same repeats. Never starts a line while one is
  playing. It stops when you're locked in again (looking at the screen AND Terminal / VS Code in
  front; the current line finishes first, then `thanks_finally` if it yelled, else `thanks`), on a
  tap, a new prompt, or when the permission prompt is answered (PostToolUse -> WORKING). Only
  looking back, or only switching back to Terminal, is not enough.
  Steps: ESCALATION_STEPS / NEEDS_YOU_STEPS; lines: SOUND_GROUPS (comments give each clip's
  actual words). `annoyed2` ("I wrote 400 lines for you") only plays when Claude wrote at least
  BIG_TURN_LINES (100) lines that turn (TurnCheckpoint.lines_added(), Edit/Write tools only).
  `gave_up` is no longer used. Phone vs other app (Nov 22): when the camera sees you LOOKING at the
  screen (so the nag is because another app is in front, e.g. Firefox), `annoyed` / `yelling` steps
  use `annoyed_app` / `yelling_app` instead (no "phone" lines). Recorded so far for that case:
  only `yelling_4` ("I can see you, you know.") and `annoyed2` (big turns); `other_app_1..4` are
  planned names, record them.
- Head slap / tap (accelerometer, `SLAP:<mg>` from the STM32, or POST /slap). While Claude is
  WORKING a single tap is ignored completely (no focus, no `> <`); only a yes to "New chat?" counts,
  and a knock-knock still opens a chat. Otherwise three cases:
  1. Nagging -> forgiven: bring Terminal to the front, `thanks_finally` ("Finally, thank you.") if
     it yelled, else `thanks`; back to DONE / NEEDS_YOU, watching restarts from scratch.
  2. Not nagging, another app in front -> bring Terminal to the front (no state change).
  3. Locked in (work app in front, not nagging) -> in DONE: undo the files Claude changed in its
     latest turn (PreToolUse checkpoint), play `slam` ("Rude! Redoing it."), WORKING "redoing...",
     type REDO_AFTER_UNDO_MESSAGE (or REDO_MESSAGE if no files changed) into tmux `claude`.
     Ignored in WORKING (`busy`, not recorded) and NEEDS_YOU (typing would pick a menu option);
     IDLE -> `nothing_to_undo`. tmux failure -> DONE "REDO FAILED", files stay undone.
  Firmware: jolt = distance of the reading from a slow running average; > 700 mg = a tap. The
  board then waits 0.8 s for a second knock (so a single tap is reported 0.8 s late), then 1 s
  cooldown so the spring wobble is not counted again.
- Knock-knock (two taps about HALF A SECOND apart; `KNOCK:<mg>` from the STM32, or POST /knock):
  opens ANOTHER Claude chat: `tmux new-window -t claude: -c <project> claude` (TmuxTyper.
  open_new_chat). The current chat keeps running in its window (Ctrl+b then n / p to switch).
  Terminal comes to the front; stops nagging (IDLE). Allowed in any state. Voice `new_chat` (not
  recorded yet). Firmware (accel.c): second jolt >= 1500 mg AND >= 35 % of the first tap, between
  0.25 and 0.8 s after it. Measured Nov 21 on the toy: a single tap's spring bounce comes back at
  0.15-0.2 s at up to 60 % of the tap, then stays < ~900 mg; a deliberate second knock at
  0.25-0.4 s was 3000-3800 mg. A FAST double tap (0.15-0.2 s) looks like the bounce and can't be
  detected as a knock, so the board flags it:
- Unsure tap (`MAYBE:<mg>`, or POST /maybe): a jolt 0.1-0.25 s after the tap of at least 80 % of
  the tap (MAYBE_RATIO; single-tap bounce measured <= 64 % over 16 taps, fast second tap 94-181 %).
  The buddy asks "New chat?" (phone shows "New chat? Tap me = yes (4)", voice `confirm_new_chat`
  not recorded) for CONFIRM_SECONDS = 4 (+1 s grace because a tap is reported 0.8 s late). Any tap
  in that time (SLAP / KNOCK / MAYBE) = yes -> new chat (never undo/redo); nothing = no. Replayed
  on all recordings: every known single tap stays a single tap; fast double taps -> MAYBE or KNOCK.
  The board's 1 s cooldown after MAYBE ignores a yes-tap in the first ~1 s after the question.
- Other voice moments: Stop -> `yay`; Notification (permission) -> `needs_you` right away.
- Button (POST /button, or `BTN` from the STM32; the physical button is gone): old redo path,
  only in DONE, ANNOYED, YELLING, never while nagging about NEEDS_YOU. Plays `slam`, types
  REDO_MESSAGE.
- Mood page (POST /mood): sets IDLE/WORKING/DONE/NEEDS_YOU by hand (source "manual"),
  stops the watch loop. ANNOYED/YELLING are refused (422), only the watch loop sets them.
- LCD text is max 16 chars; `_set_state` raises if longer.
- Hook payload values are never logged (they contain prompts and Claude's replies,
  which can contain secrets). Only field names, at DEBUG level.

## Decisions and why

- `127.0.0.1` not `localhost` in hooks: macOS can resolve localhost to IPv6 first,
  uvicorn listens on IPv4 only.
- Removed the `idle_prompt` Notification matcher: it fires while the user is idle
  after Stop, which would reset the nag timer mid-yell. Stop already covers it.
- Voice comes from the phone in the toy (Nov 21), not the STM32 DAC: better sound (full mp3 instead
  of 8 kHz 8-bit), no wiring, and the phone is already there for the face. The DAC version
  (D7/PA4, 10 uF cap to a 3.5 mm plug, audio.c) worked on the board but was ditched.
- Pre-made voice clips instead of live TTS: no internet or credits needed during the demo, and
  ElevenLabs acting (deadpan -> exasperated) is far better than `say`.
- Redo button injects text with `tmux send-keys` because hooks cannot start a new turn.
  Claude Code must be started inside tmux: `tmux new -s claude` then `claude`.
- Port 8765 to avoid clashing with other FastAPI apps on 8000.
- Attention (head/eyes) instead of phone detection: tried YOLO "cell phone" first, but a
  phone held normally is below the webcam's view, and a phone-camera stream was too
  laggy. Trade-off: any looking away counts (notes, a teammate), not just the phone.
- Head down only counts DOWN (signed pitch; pitch rises when looking down on Ben's Mac).
  eyeBlink is used too because MediaPipe often reports lowered eyelids, not eyeLookDown,
  when looking down at a phone.

## Hardware (exact parts)

- Board: STM32 B-L4S5I-IOT01A Discovery kit (STM32L4S5VIT6), powered and connected
  only through micro-USB on CN7 (ST-LINK). No batteries. JP4 on default 5V_ST_LINK.
  Needs a DATA micro-USB cable (a charge-only one powers the board but the Mac sees nothing).
- Serial: USART1 PB6/PB7 = ST-LINK Virtual COM port, 115200 8N1, RX interrupt enabled.
  On the Mac: `/dev/cu.usbmodem*`.
- Display: red "2.8 TFT SPI 240X320 V1.2" module, ILI9341 controller (ID 0x9341 read back),
  XPT2046 touch and SD slot unused. Landscape 320x240.
- Speaker: the phone's own speaker (the phone sits in the toy and shows the face).
- Slap sensor: onboard LSM6DSL accelerometer (no wiring). The head sits on two springs on the
  legs; the board is in the head, so a slap makes it jolt.
- Undo/slam button: external button between Arduino D8 (PB2) and GND, internal pull-up,
  polled with 30 ms debounce in the main loop. Button LED on D9 (PA15).
  Onboard blue button PC13 (LOW when pressed) cycles the faces for testing.
- Heartbeat: green LD2 (PB14) blinks at 2 Hz while the main loop runs.

### TFT wiring

| TFT pin | Connect to | STM32 pin / use |
|---|---|---|
| VCC | 5V | module has its own 3.3 V regulator (J1 open) |
| GND | GND | |
| CS | D10 | PA2, GPIO output, starts high |
| RESET | D6 | PB1, GPIO output, starts high |
| DC | D4 | PA3, GPIO output (moved off D7 = PA4, the DAC audio pin) |
| SDI(MOSI) | D11 | PA7, SPI1_MOSI |
| SCK | D13 | PA5, SPI1_SCK (LD1 flickers with it, normal) |
| LED | D3 | PB0, TIM3_CH3 PWM 20 kHz, backlight fixed at 70 % |
| SDO(MISO) | D12 | PA6, SPI1_MISO, only for reading the ID |
| T_* and SD pins | not connected | |

### CubeMX settings

- SYS Debug = Serial Wire; toolchain STM32CubeIDE, generate under root, copy only needed libraries
- SPI1 full-duplex master, 8-bit, mode 0, prescaler 4 (30 MHz), software CS
- TIM3 CH3 PWM on PB0: prescaler 5, period 999 (20 kHz)
- PA2, PA3, PB1, PB14, PA15 = GPIO_Output; PB2 = GPIO_Input pull-up; PC13 = GPIO_Input
- USART1 asynchronous 115200 on PB6/PB7 with global interrupt
- I2C2 on PB10/PB11 (onboard sensor bus) for the LSM6DSL accelerometer, address 0x6A
  (was I2C1 on PB8/PB9, unused, swapped out)

### Faces (firmware `face.c`)

Orange background (#D97757), black pixel-art eyes pushed to the screen edges. Each eye is
drawn into an off-screen buffer and sent in one SPI transfer (no flicker).
normal (tall rectangles, random blinks and glances), happy `^ ^` (bounce),
sad `/. .\` (small eyes, slanted brows), ouch `> <` (shake). `Face_SetMood` is permanent;
`Face_React(mood, ms)` plays a reaction and then returns to the permanent mood.

### Serial protocol (newline-terminated text, firmware `link.c`)

- laptop -> board: `F:IDLE` and `F:WORK` (normal), `F:DONE` (happy), `F:NEED` (sad),
  `F:MAD` (ouch), `T:<text>` (accepted, not shown: the TFT has no text yet), `PING` (board replies `PONG`),
  `S:<clip>` (play voice clip), `S:STOP` (still in the firmware, no longer sent by the laptop)
- board -> laptop: `KNOCK:<mg>` (knock-knock), `MAYBE:<mg>` (unsure, laptop asks), `BTN` (undo button; the board also shows `> <` for 1.5 s on its own),
  `SLAP:<mg>` (head slapped, strength in milli-g; also `> <`), `ERR:ACCEL` (accelerometer
  missing at startup, logged as a warning)
- State to face mapping lives in `FACE_FOR_STATE` in serial_output.py:
  IDLE/WORKING -> normal, DONE -> happy, NEEDS_YOU -> sad, ANNOYED/YELLING -> ouch.
- Firmware: UART receives one byte at a time by interrupt into a ring buffer; lines are
  handled and the display is drawn in the main loop, never inside the interrupt.

## Status

- Done and tested on the Mac: hook server, hooks firing from real Claude Code,
  nag timer + `say` (milestone 2), redo button via curl + tmux, attention detector in
  camera_test.py (Nov 20). Camera-driven buddy confirmed working with the server (Nov 20).
- STM32: TFT face with 4 moods, backlight PWM and both buttons tested on the board (Nov 21).
- Serial link (Nov 21): firmware `link.c` builds; laptop `serial_output.py` tested only
  against a fake serial port (pty), including BTN -> redo logic. NOT yet tested with the
  real board and Mac.

- Head slap (Nov 21): firmware builds (test-compiled with CubeIDE's GCC), laptop path tested
  with a fake serial port (SLAP -> Terminal comes to the front). NOT yet tested on the board:
  threshold 700 mg is a guess.

## Next steps, in order

1. Tune timings and spoken lines for the demo (ESCALATION_STEPS in buddy_service.py).
2. Test the serial link on the Mac with the real board (flash, `pip install pyserial`,
   start the server, send a prompt, see the happy face; press the undo button).
3. Optional: Claude Haiku-generated roasts using last_assistant_message.

## Known gaps (keep this list current)

- Phone face: no password; anyone on the same network can VIEW the face and mood and download the
  voice clips (nothing else). Phone voice needs one tap after every page load, and the phone
  screen must stay on (Auto-Lock Never); otherwise the laptop plays the voice.
  Polling every 0.3 s, not pushed. The laptop's address can change when the network changes:
  re-read it from the log.

- Detector limits were tuned on one test (Ben, his desk, his lighting). Different
  lighting or seating on demo day: recalibrate, maybe retune.
- Camera light is on the whole time the server runs.
- Shortcut: spoken lines are fixed text.
- Only one Claude Code session supported (session_id ignored): after a knock-knock opens a second
  chat, both chats' hooks drive the same buddy state (for example the old chat finishing makes it
  happy while you work in the new one). The redo tap types into the tmux window in front.
- Shortcut: tmux session name `claude` is hardcoded in dependencies.py.
- State is in memory; restart resets to IDLE.
- No automated tests yet.
- Shortcut: the serial port is only opened at server start; unplugging the board means
  restarting the server (no reconnect).
- Slap threshold (700 mg) and cooldown (1.5 s) are untuned guesses; tune in accel.c from the
  logged strengths.
- Undo only covers Edit/Write/MultiEdit/NotebookEdit. Changes made through Bash (rm, mv, sed,
  git) are NOT undone. Claude is not told about the undo, so its memory of the files is stale.
- Undo copies are in memory only: restarting the server loses them. Files outside the project
  folder are never saved or restored.
- Shortcut: a tap focuses the whole Terminal app, not the tmux window running Claude; with
  several Terminal windows, macOS shows the last used one.
- Yelling never gives up: if you leave the desk it yells every 12 s until you're back and locked in,
  a tap, or a prompt.
- Shortcut: `T:` status text is sent but not shown on the TFT.
- `firmware/Claude-buddy/Debug/` (build output, about 20 MB) is committed; should be gitignored.
- Production version would: keep state per session_id, require a token header on hooks.

## Demo-day notes

- User's Claude Pro subscription is cancelled and ends Nov 22 (demo day), exact time
  unknown. Backup plans: resubscribe, log in with a teammate's account via /login,
  or an API key (never paste or commit keys). Record a backup demo video on Nov 21.
- Run /login the morning of the demo.

## How to work with Ben (the user)

- He is a computer engineering student, comfortable with Python, Java, C++, FastAPI
  and Spring Boot, new to backend and embedded details. Explain plainly, no jargon
  without explanation, no analogies, no idioms. Concrete examples.
- He asked for the code to be written for this project. Comment every line's purpose.
- One small step at a time, each with a clear "done when" check. Explain every new
  command before asking him to run it. Say exactly which file and whether new or edited.
- Never use em dashes in anything you write.
- No Python list comprehensions; use for loops with append.
- Flag every shortcut in one sentence when taken; end each milestone with a gaps list
  (built, skipped and why, debt, what production would do).
- Never ask for output that could contain secrets (env vars, keys). If he pastes a
  secret, tell him immediately and walk him through rotating it.
- If he says he's lost: short orientation (where we are, what works, what's next).
- Diagrams must be properly rendered, not ASCII art.
- Never refer back to earlier steps by label; reprint the full steps.
