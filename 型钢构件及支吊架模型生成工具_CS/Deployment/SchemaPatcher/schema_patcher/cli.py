"""命令行入口，供批处理与离线检查使用；界面版见 gui.py。"""
import argparse

from .engine import PatchError, apply_plan, describe_plan, format_log, load_plan
from .features import FEATURES


def main(argv):
    parser = argparse.ArgumentParser(description="OpenPlant 工作集 Schema 增补（默认只读检查）")
    parser.add_argument("--schema-dir", required=True)
    parser.add_argument("--feature", required=True, choices=list(FEATURES))
    parser.add_argument("--backup-dir")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--log", help="把检查/修改记录另存到该文件")
    parser.add_argument("--skip-process-check", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    plan = load_plan(args.schema_dir, args.feature)
    for _, text in describe_plan(plan):
        print(text)
    text = format_log(plan)
    code = 2 if plan.blocked else 0
    if args.apply and not plan.blocked and plan.pending:
        try:
            result = apply_plan(plan, args.backup_dir, check_processes=not args.skip_process_check)
        except PatchError as error:
            print("失败：%s" % error)
            return 1
        print("已完成，备份与记录：%s" % result.run_dir)
        text = result.log_text
    if args.log:
        with open(args.log, "w", encoding="utf-8-sig") as stream:
            stream.write(text)
    return code
