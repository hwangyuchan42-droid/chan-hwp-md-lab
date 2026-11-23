"""Print Markdown tables for complete, comparable baseline runs."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median

from baseline import ARMS, CASES


def read_runs(paths):
    inventory = None
    selected = {}
    for path in paths:
        groups = defaultdict(dict)
        with path.open(encoding="utf-8") as stream:
            header = json.loads(next(stream))
            if header.get("type") != "inventory" or (inventory and inventory != header):
                raise ValueError(f"{path}: tool or corpus inventory differs")
            inventory = header
            for line in stream:
                row = json.loads(line)
                key = row["arm"], row["round"]
                case = row["case"]
                if key in groups[case]:
                    raise ValueError(f"{path}: duplicate {case} {key}")
                groups[case][key] = row
        # A later file can replace a whole case. Never combine individual timed rounds.
        selected.update(groups)
    required = {(arm, turn) for arm in ARMS for turn in range(6)}
    for case, (count, _) in CASES.items():
        runs = selected.get(case, {})
        if runs.keys() != required:
            raise ValueError(f"{case}: expected one telemetry run and five timed runs per arm")
        for key, row in runs.items():
            if sum(row["counts"].values()) != count or row["passed"] + sum(row["errors"].values()) != count:
                raise ValueError(f"{case} {key}: source or output totals differ")
            if set(row["exit_codes"]) != {"0"} or row["extra_outputs"]:
                raise ValueError(f"{case} {key}: inspect process failures or unexpected output before ranking")
    return selected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", type=Path, nargs="+")
    args = parser.parse_args()
    groups = read_runs(args.logs)
    for case, (count, _) in CASES.items():
        print(f"\n### {case} ({count:,})\n")
        print("| 도구 | 통과 건/회 (범위) | 중앙값 초 | 최소~최대 초 | 통과 건/초¹ | 입력 MiB/초¹ | 관측 메모리 MiB² |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for arm in ARMS:
            rows = [groups[case][arm, turn] for turn in range(1, 6)]
            seconds = [r["seconds"] for r in rows]
            checked = [r["passed"] for r in rows]
            rates = [r["passed"] / r["seconds"] for r in rows]
            mib_rates = [r["input_bytes"] / 2**20 / r["seconds"] for r in rows]
            memory = groups[case][arm, 0]["sampled_peak_bytes"]
            peak = "—" if memory is None else f"{memory / 2**20:.1f}"
            passed = str(min(checked)) if min(checked) == max(checked) else f"{min(checked)}~{max(checked)}"
            print(f"| {arm} | {passed} | {median(seconds):.3f} | "
                  f"{min(seconds):.3f}~{max(seconds):.3f} | {median(rates):.1f} | "
                  f"{median(mib_rates):.2f} | {peak} |")
    print("\n¹ 5회 각각의 비율을 구한 뒤 중앙값을 표시했다. 입력량에는 실패 파일도 포함한다.")
    print("\n² 속도 측정 전 별도 1회에서 약 20ms 간격으로 관측한 자식 프로세스 RSS 합계의 최댓값이다.")


if __name__ == "__main__":
    main()
