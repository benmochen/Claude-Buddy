# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Delegated: a single static page (HTML/CSS/JS, no build step) served by the existing FastAPI laptop service at `/`. The service already has to be running for Claude Code's hooks to reach the puppet, so the UI ships with it and works the same on Linux, macOS and Windows. It can be wrapped in a tray icon or desktop window later without a rewrite.

## Users

People who own a Claude Buddy puppet and use Claude Code. That starts with the two builders, but the page has to work for someone else setting up a puppet with no help, on their own laptop. They open it to get the puppet connected and working, to check that it reacts, and occasionally to change what it says.

## Product Purpose

Claude Buddy is a physical desk puppet that reacts to Claude Code. When you send a prompt it shows that Claude is working. When Claude finishes or needs your permission or input, it gets your attention, so you can stop watching the terminal. The setup page connects the laptop service, Claude Code and the puppet, and makes the puppet's current mood visible on screen. Success means a new owner goes from plugging in to "it reacted to my prompt" without reading code.

## Positioning

A physical object in the room, not another desktop notification. It's driven directly by Claude Code's own hooks (UserPromptSubmit, Stop, Notification).

## Operating Context

- The laptop service (`laptop/buddy/`, FastAPI on `127.0.0.1:8765`) receives Claude Code hook POSTs and holds the state.
- States: IDLE, WORKING, DONE, NEEDS_YOU. The puppet's LCD shows a message of at most 16 characters per state.
- The puppet is an STM32 board connected over USB serial. It shows up as `/dev/ttyACM*` on Linux, `/dev/cu.usbmodem*` on macOS, or `COM*` on Windows, with ST's USB vendor ID 0x0483.
- Hooks fire only for Claude Code sessions whose settings include them. A project-level `.claude/settings.json` covers one repo; `~/.claude/settings.json` covers every project.

## Capabilities and Constraints

- The UI runs on localhost only, and the service binds to 127.0.0.1.
- Desktop browsers come first, since the page runs on the laptop next to the puppet. Phone layouts only need to not break; they get no polish.
- Hook payloads contain prompts and Claude's replies. Never display, log or transmit their contents.
- LCD text has a hard limit of 16 characters.
- The serial protocol between the laptop and the STM32 firmware is not finalized yet (open decision).
- End users are not expected to flash firmware. The board is assumed to ship pre-flashed (open decision).

## Brand Commitments

- Name: Claude Buddy.
- Mascot: a chunky orange pixel-art critter in the spirit of Claude Code's terminal character, with a face that shows the buddy's current mood.
- Voice: playful and simple.

## Evidence on Hand

No photos of the physical puppet, no testimonials and no usage data. Don't invent any.

## Product Principles

1. The mood comes first: you should be able to tell the buddy's state from across the room.
2. Setup should feel like plugging in a toy: detect automatically, and fall back to manual only when needed.
3. Privacy by default: the page shows state, never what you or Claude wrote.
4. Playful, but never in the way of fixing a broken connection.
