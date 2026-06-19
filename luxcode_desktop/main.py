from __future__ import annotations

from luxcode_desktop.app import create_app
from luxcode_desktop.config import DEFAULT_MAIN_REPOSITORY
from luxcode_runtime_settings import (
    acquire_single_instance_lock,
    apply_persistent_runtime_environment,
    release_single_instance_lock,
    show_single_instance_notice,
)


def main() -> None:
    apply_persistent_runtime_environment(DEFAULT_MAIN_REPOSITORY)
    instance_lock = acquire_single_instance_lock(DEFAULT_MAIN_REPOSITORY)
    if instance_lock is None:
        show_single_instance_notice()
        return

    try:
        root, app = create_app()
        root.protocol("WM_DELETE_WINDOW", app.close)
        root.mainloop()
    finally:
        release_single_instance_lock(instance_lock)


if __name__ == "__main__":
    main()
