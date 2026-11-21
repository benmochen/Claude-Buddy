# Where the buddy "shows" its state. For now that's just the terminal.
# Later you add serial_output.py with the same show() method that sends
# the text to the STM32 instead, and nothing else in the code has to change.

from datetime import datetime

from buddy.state import BuddyState


class ConsoleOutput:
    # start() and stop() do nothing here. They exist so main.py can treat
    # ConsoleOutput and SerialOutput the same way.
    def start(self, on_button, on_slap) -> None:
        pass

    def stop(self) -> None:
        pass

    def show(self, state: BuddyState, text: str) -> None:
        # Time like 19:52:07, so you can see how long Claude took.
        now = datetime.now().strftime("%H:%M:%S")

        # :<10 pads the state name to 10 characters so the columns line up.
        print(f"[{now}] {state.value:<10} | {text}", flush=True)
