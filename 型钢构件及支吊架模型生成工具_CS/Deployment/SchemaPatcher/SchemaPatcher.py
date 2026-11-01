"""OpenPlant 工作集 Schema 增补工具入口：无参数打开界面，带参数走命令行。"""
import sys


def main():
    if len(sys.argv) > 1 and sys.stdout is not None:
        from schema_patcher.cli import main as cli_main
        sys.exit(cli_main(sys.argv[1:]))
    from schema_patcher.gui import run
    run()


if __name__ == "__main__":
    main()
