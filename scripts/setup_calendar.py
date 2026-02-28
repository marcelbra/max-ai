#!/usr/bin/env python
"""One-time Calendar permission setup. Run with: make setup-calendar"""

import subprocess
import sys

PROBE = 'Application("Calendar").calendars().map(c => c.name()).join(", ")'


def run_probe() -> tuple[bool, str]:
    result = subprocess.run(
        ["osascript", "-l", "JavaScript", "-e", PROBE],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, result.stdout.strip()


def main() -> None:
    print("Requesting macOS Calendar access...")
    print()
    print("macOS requires one-time consent to access Calendar.")
    print("A permission dialog should appear — click Allow.")
    print()

    ok, output = run_probe()

    if not ok:
        print(f"Access denied or error: {output}")
        print()
        print("If no dialog appeared, grant access manually:")
        print("  System Settings → Privacy & Security → Calendars → enable your terminal app")
        sys.exit(1)

    if not output:
        print("Access granted but no calendars found (Calendar app may be empty).")
    else:
        print(f"Access granted. Calendars found: {output}")

    print()
    print("Setup complete. Calendar tools are ready in max-ai.")


if __name__ == "__main__":
    main()
