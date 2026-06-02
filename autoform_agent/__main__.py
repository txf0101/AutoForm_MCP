"""这个文件让用户可以运行 `python -m autoform_agent`。它不处理业务，只把工作交给命令行入口。

This file lets users run `python -m autoform_agent`. It keeps business logic out of the module entry point and delegates all command parsing to the CLI.
"""

from .cli import main


if __name__ == "__main__":
    # Convert the integer return value from `main` into the process exit status.
    raise SystemExit(main())
