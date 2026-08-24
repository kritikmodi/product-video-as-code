#!/usr/bin/env python3
"""Stage 4a - you log in by hand, in a browser profile the tour can reuse.

Deliberately interactive. An assistant driving this pipeline should not be typing
your credentials, and does not need to: you sign in once here, the session is
saved into a local Chromium profile, and every later recording reuses it.

    python3 scripts/capture/login.py https://app.example.com/login

The profile lives in capture/profile/ and contains a live session. It is
gitignored, and it must stay that way.
"""
import pathlib, sys, time
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent.parent.parent / "capture"
PROFILE = HERE / "profile"
WAIT_MIN = 10


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: login.py <login-url>")
    url = sys.argv[1]
    PROFILE.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            headless=False,
            viewport={"width": 1440, "height": 810},
            device_scale_factor=1,
            args=["--force-color-profile=srgb", "--hide-scrollbars",
                  "--window-size=1440,920"],
        )
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(url)

        print("\n  A browser window is open at your login page.")
        print("  Sign in there. Nothing you type is read or stored by this script.")
        print(f"  Waiting up to {WAIT_MIN} minutes...\n", flush=True)

        deadline = time.time() + WAIT_MIN * 60
        while time.time() < deadline:
            try:
                if "login" not in pg.url.lower() and "signin" not in pg.url.lower():
                    time.sleep(3)
                    if "login" not in pg.url.lower():
                        (HERE / "logged_in.marker").write_text(pg.url)
                        print(f"  Logged in - now at {pg.url}")
                        time.sleep(2)
                        ctx.close()
                        print("\n  Profile saved. You can run capture/tour.py now.")
                        return
            except Exception:
                pass
            time.sleep(2)

        print("  Timed out. Re-run when you're ready.")
        ctx.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
