# Claude Desk Buddy (hackathon project, demo on Nov 22, 2026)

A 3D-printed Claude mascot that sits on the desk. When Claude Code finishes a task
and the user is distracted (scrolling their phone), it yells at them through a
speaker and shows an angry face on an LCD. A big "slam" button sends a
"that was bad, redo it" prompt to Claude Code.

## How it works

Claude Code hooks (HTTP) -> FastAPI daemon on the Mac -> (USB serial) -> STM32 -> LCD
STM32 button -> (USB serial "BTN") -> daemon -> `tmux send-keys` -> Claude Code
Daemon -> macOS `say` -> headphone jack -> speaker
Webcam (later) -> daemon decides "distracted or not"

Everything smart runs on the laptop. The STM32 only draws on the LCD and reports
button presses.

## Repo layout

- `.claude/settings.json`: HTTP hooks (UserPromptSubmit, Stop, Notification with
  matcher `permission_prompt` only) posting to `http://127.0.0.1:8765/hooks/...`
- `laptop/` (Python, FastAPI, run from this folder)
  - `buddy/main.py`: creates the app, includes routers
  - `buddy/state.py`: BuddyState enum: IDLE, WORKING, DONE, NEEDS_YOU, ANNOYED, YELLING
  - `buddy/dependencies.py`: builds the single BuddyService and picks its
    output / speaker / detector. Only file to edit when swapping implementations.
  - `buddy/api/hooks.py`: POST /hooks/prompt-submit, /hooks/stop, /hooks/notification (reply 204)
  - `buddy/api/status.py`: GET /status
  - `buddy/services/buddy_service.py`: all logic, including the nag timer
  - `buddy/outputs/console_output.py`: prints state (stand-in for the LCD)
  - `buddy/outputs/speaker.py`: macOS `say` via subprocess.Popen (list args, no shell)
  - `buddy/detectors/always_distracted.py`: stub, always returns True
- `firmware/`: empty, the STM32CubeIDE project goes here

## Running it (user's Mac, project at ~/Documents/desk-buddy)

- Terminal 1: `cd ~/Documents/desk-buddy/laptop && source .venv/bin/activate && uvicorn buddy.main:app --port 8765`
  (prefix `BUDDY_QUIET=1` to print `[SAY] ...` instead of speaking)
- Terminal 2: `cd ~/Documents/desk-buddy && claude` (hooks only fire when Claude
  Code starts in the folder containing `.claude/settings.json`; restart Claude Code
  after editing that file)
- IMPORTANT: hooks, `say`, the serial port and tmux all need the user's Mac. A cloud
  Claude Code session can edit this repo but cannot test any of that. Testing happens
  on the Mac after `git pull`.

## Behaviour implemented

- Prompt submitted -> WORKING ("thinking..."), cancels nag timer, cuts off speech
- Stop hook -> DONE ("DONE. LOOK UP."), starts nag timer
- Notification (permission_prompt) -> NEEDS_YOU ("NEEDS YOU!"), starts nag timer
- Nag timer (asyncio task): 10 s ANNOYED + speech, 25 s YELLING + speech, then repeat
  every 20 s, max 3 repeats, then gives up. Each nag checks detector.is_distracted().
- LCD text is max 16 chars; `_set_state` raises if longer.
- Hook payload values are never logged (they contain prompts and Claude's replies,
  which can contain secrets). Only field names, at DEBUG level.

## Decisions and why

- `127.0.0.1` not `localhost` in hooks: macOS can resolve localhost to IPv6 first,
  uvicorn listens on IPv4 only.
- Removed the `idle_prompt` Notification matcher: it fires while the user is idle
  after Stop, which would reset the nag timer mid-yell. Stop already covers it.
- Speaker is on the laptop (macOS `say`), not the STM32 DAC: far less work, better audio.
- Redo button injects text with `tmux send-keys` because hooks cannot start a new turn.
  Claude Code must be started inside tmux: `tmux new -s claude` then `claude`.
- Port 8765 to avoid clashing with other FastAPI apps on 8000.

## Hardware (exact parts)

- Board: STM32 B-L4S5I-IOT01A Discovery kit (STM32L4S5VIT6), powered and connected
  only through micro-USB on CN7 (ST-LINK). No batteries. JP4 on default 5V_ST_LINK.
- Serial: USART1 PB6/PB7 = ST-LINK Virtual COM port, 115200 8N1.
  On the Mac: `/dev/cu.usbmodem*`.
- LCD: 1602A (QAPASS), 16 pins, NO I2C backpack -> HD44780 4-bit parallel mode.
- Speaker: "hamburger" mini speaker, 3.5 mm aux into the MacBook headphone jack.
- Slam button: external button between Arduino D2 (PD14, EXTI14) and GND,
  internal pull-up, falling edge, ~200 ms software debounce. Onboard blue button
  PC13 (LOW when pressed) can be used for testing.

### LCD wiring (verified against UM2708)

| LCD pin | Name | Connect to |
|---|---|---|
| 1 | VSS | GND |
| 2 | VDD | 5V |
| 3 | V0 | 10k pot middle leg (outer legs 5V and GND); fallback: 1k to GND |
| 4 | RS | D8 (PB2) |
| 5 | RW | GND (write only, LCD never drives 5V into the STM32) |
| 6 | E | D3 (PB0) |
| 7-10 | D0-D3 | not connected (4-bit mode) |
| 11 | D4 | D4 (PA3) |
| 12 | D5 | D5 (PB4) |
| 13 | D6 | D6 (PB1) |
| 14 | D7 | D7 (PA4) |
| 15 | A | 5V through 220 ohm |
| 16 | K | GND |

### CubeMX settings

- SYS Debug = Serial Wire (frees PB4)
- PB2, PB0, PA3, PB4, PB1, PA4 = GPIO_Output
- PD14 = GPIO_EXTI14, falling edge, pull-up; NVIC "EXTI line[15:10]" enabled
- USART1 asynchronous 115200 on PB6/PB7 with global interrupt

### LCD driver plan (HD44780, 4-bit)

Functions: send_nibble (set D4-D7, pulse E high then low), send_byte (RS, high
nibble then low), set_cursor (0x80 | addr, row 0 = 0x00, row 1 = 0x40),
create_char (0x40 | slot << 3, then 8 bytes). Init: wait 50 ms; nibble 0x3, 5 ms;
0x3, 1 ms; 0x3, 1 ms; 0x2; cmd 0x28; 0x08; 0x01 (wait 2 ms); 0x06; 0x0C.
Shortcut: RW tied low, so no busy flag; use HAL_Delay(1) after each E pulse.
Faces: row 1 = eyes using `>` and `<` (the mascot's eyes), row 2 = status text.

### Serial protocol (newline-terminated text)

- laptop -> board: `F:WORK`, `F:DONE`, `F:MAD`, `F:IDLE` (face on row 1), `T:<text>` (row 2, max 16 chars)
- board -> laptop: `BTN`
- Firmware: receive UART one byte at a time by interrupt into a line buffer; handle
  full lines and do LCD writes in the main loop, never inside the interrupt.

## Status

- Done and tested on the Mac: hook server, hooks firing from real Claude Code
  (WORKING then DONE confirmed).
- Delivered, not yet confirmed on the Mac: nag timer + `say` (milestone 2).
- STM32: not started. First step is an LED blink on PB14 (LED2) in STM32CubeIDE
  (board selector B-L4S5I-IOT01A, init peripherals in default mode).

## Next steps, in order

1. Redo button on the laptop side: POST /button endpoint (fake press for testing) ->
   service -> `tmux send-keys -t claude "<redo message>" Enter`. Redo message should
   ask Claude to list what may be wrong with its last answer, then try a different
   approach (a bare "redo it" gives Claude nothing to work with).
2. STM32: LED blink, then serial hello to the Mac, then LCD text.
3. `outputs/serial_output.py` (pyserial) replacing ConsoleOutput, plus a reader
   thread for `BTN`.
4. Webcam detector (OpenCV + small YOLO "cell phone" class, distracted if phone seen
   ~3 s) replacing AlwaysDistracted. macOS needs Camera permission for the terminal app.
5. Optional: Claude Haiku-generated roasts using last_assistant_message.

## Known gaps (keep this list current)

- Shortcut: AlwaysDistracted, so it nags even when the user is reading Claude's reply.
- Shortcut: spoken lines are fixed text.
- Only one Claude Code session supported (session_id ignored, two sessions would clash).
- State is in memory; restart resets to IDLE.
- No automated tests yet.
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
