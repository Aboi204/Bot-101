import io
import sys
from pathlib import Path

# Prevent NoneType AttributeError in --noconsole GUI mode
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).resolve().parent
    if str(BUNDLE_DIR) not in sys.path:
        sys.path.insert(0, str(BUNDLE_DIR))
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    APP_DIR = BUNDLE_DIR
    if str(BUNDLE_DIR) not in sys.path:
        sys.path.insert(0, str(BUNDLE_DIR))

if __name__ == "__main__":
    if "--cli" in sys.argv or "--no-gui" in sys.argv:
        import asyncio
        from src.bot import run_bot
        try:
            asyncio.run(run_bot())
        except KeyboardInterrupt:
            print("\n[!] Bot was shut down by user.")
        except Exception as e:
            print(f"\n[FATAL ERROR] An unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()
            input("\nPress Enter to exit...")
    else:
        from src.gui import main
        main()
