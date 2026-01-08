"""
Progress indicators with spinner animation and progress bar.
Similar to Office/Windows installation progress displays.
"""

import sys
import time
import threading
from typing import Optional


class Spinner:
    """
    Animated spinner for indeterminate progress.

    Usage:
        with Spinner("Loading..."):
            do_something()
    """

    # Different spinner styles
    DOTS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    BARS = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█", "▇", "▆", "▅", "▄", "▃", "▂"]
    ARROWS = ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"]
    CLASSIC = ["|", "/", "-", "\\"]
    BLOCKS = ["█▁▁▁", "▁█▁▁", "▁▁█▁", "▁▁▁█", "▁▁█▁", "▁█▁▁"]
    BOUNCING = ["[    ]", "[=   ]", "[==  ]", "[=== ]", "[ ===]", "[  ==]", "[   =]", "[    ]", "[   =]", "[  ==]", "[ ===]", "[====]", "[=== ]", "[==  ]", "[=   ]"]

    def __init__(self, message: str = "Processing", style: str = "dots"):
        self.message = message
        self.running = False
        self.thread = None

        styles = {
            "dots": self.DOTS,
            "bars": self.BARS,
            "arrows": self.ARROWS,
            "classic": self.CLASSIC,
            "blocks": self.BLOCKS,
            "bouncing": self.BOUNCING,
        }
        self.frames = styles.get(style, self.DOTS)

    def _animate(self):
        idx = 0
        while self.running:
            frame = self.frames[idx % len(self.frames)]
            sys.stdout.write(f"\r{frame} {self.message}")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._animate)
        self.thread.start()

    def stop(self, final_message: Optional[str] = None):
        self.running = False
        if self.thread:
            self.thread.join()
        # Clear line and show final message
        sys.stdout.write("\r" + " " * (len(self.message) + 10) + "\r")
        if final_message:
            print(f"✓ {final_message}")
        sys.stdout.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


class ProgressBar:
    """
    Progress bar with spinner for determinate progress.

    Usage:
        progress = ProgressBar(total=100, description="Processing")
        for i in range(100):
            progress.update(1)
        progress.close()
    """

    SPINNER = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        total: int,
        description: str = "Progress",
        bar_length: int = 30,
        show_spinner: bool = True
    ):
        self.total = total
        self.description = description
        self.bar_length = bar_length
        self.show_spinner = show_spinner
        self.current = 0
        self.spinner_idx = 0
        self.start_time = time.time()

    def update(self, amount: int = 1):
        """Update progress by amount."""
        self.current += amount
        self._render()

    def _render(self):
        """Render the progress bar."""
        # Calculate percentage
        percent = min(100, (self.current / self.total) * 100) if self.total > 0 else 0

        # Calculate filled portion of bar
        filled = int(self.bar_length * self.current / self.total) if self.total > 0 else 0

        # Create bar with gradient effect
        bar = "█" * filled + "░" * (self.bar_length - filled)

        # Spinner
        spinner = ""
        if self.show_spinner and self.current < self.total:
            spinner = self.SPINNER[self.spinner_idx % len(self.SPINNER)] + " "
            self.spinner_idx += 1
        elif self.current >= self.total:
            spinner = "✓ "

        # Elapsed time
        elapsed = time.time() - self.start_time

        # Estimate remaining time
        if self.current > 0 and self.current < self.total:
            rate = self.current / elapsed
            remaining = (self.total - self.current) / rate
            time_str = f" | {elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining"
        else:
            time_str = f" | {elapsed:.1f}s"

        # Format numbers with commas
        current_fmt = f"{self.current:,}"
        total_fmt = f"{self.total:,}"

        # Build output line
        line = f"\r{spinner}{self.description}: |{bar}| {percent:5.1f}% ({current_fmt}/{total_fmt}){time_str}"

        # Pad to clear any previous longer line
        sys.stdout.write(line + " " * 10)
        sys.stdout.flush()

    def close(self, message: Optional[str] = None):
        """Complete the progress bar."""
        self.current = self.total
        self._render()
        print()  # New line
        if message:
            print(f"✓ {message}")


class MultiStageProgress:
    """
    Multi-stage progress indicator for complex operations.

    Usage:
        stages = MultiStageProgress([
            "Loading file",
            "Processing data",
            "Saving output"
        ])
        stages.start(0)
        # do stage 0
        stages.complete(0)
        stages.start(1)
        # etc.
    """

    def __init__(self, stages: list):
        self.stages = stages
        self.current_stage = -1
        self.completed = set()

    def _render(self):
        """Render all stages."""
        print("\n" + "=" * 50)
        for i, stage in enumerate(self.stages):
            if i in self.completed:
                status = "✓"
                color = ""
            elif i == self.current_stage:
                status = "►"
                color = ""
            else:
                status = "○"
                color = ""
            print(f"  {status} {stage}")
        print("=" * 50 + "\n")

    def start(self, stage_idx: int):
        """Mark a stage as in progress."""
        self.current_stage = stage_idx
        self._render()

    def complete(self, stage_idx: int):
        """Mark a stage as complete."""
        self.completed.add(stage_idx)
        if stage_idx == self.current_stage:
            self.current_stage = -1


# Simple function wrappers for common use cases
def with_spinner(message: str = "Processing"):
    """Decorator to show spinner during function execution."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            with Spinner(message):
                return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    # Demo
    print("=== Spinner Demo ===")
    with Spinner("Loading data...", style="dots") as s:
        time.sleep(2)
    print("Done!\n")

    print("=== Progress Bar Demo ===")
    progress = ProgressBar(total=100, description="Processing files")
    for i in range(100):
        time.sleep(0.03)
        progress.update(1)
    progress.close("Complete!")

    print("\n=== Bouncing Spinner Demo ===")
    with Spinner("Installing...", style="bouncing") as s:
        time.sleep(3)
    print("Done!")
