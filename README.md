# Claude-Buddy

A desk puppet that reacts to Claude Code: it shows when Claude is working, when it's done, and when it needs you.

## Run the laptop service

```sh
cd laptop
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn buddy.main:app --port 8765
```

Then open http://127.0.0.1:8765/ to see the buddy's mood page.

The mood page shows the current mood and how long it has lasted. You can also set the mood by hand to test the puppet, and edit the 16-character message the LCD shows for each mood. Saved messages live in `~/.config/claude-buddy/messages.json`; set `BUDDY_CONFIG` to use a different path.

## API

| Method | Path | What it does |
|---|---|---|
| POST | `/hooks/prompt-submit` | Claude Code `UserPromptSubmit` hook: mood becomes WORKING |
| POST | `/hooks/stop` | Claude Code `Stop` hook: mood becomes DONE |
| POST | `/hooks/notification` | Claude Code `Notification` hook: mood becomes NEEDS_YOU |
| GET | `/status` | Current mood, LCD text, seconds in mood, change counter, source (`hook` or `manual`) |
| POST | `/mood` | Body `{"state": "DONE"}` sets the mood by hand |
| GET / PUT / DELETE | `/messages` | Read, update (`{"DONE": "ALL DONE :)"}`), or reset the per-mood LCD text |

The hooks in `.claude/settings.json` only fire for Claude Code sessions opened in this repo.
