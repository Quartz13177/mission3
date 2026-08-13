"""
Mini NPU Simulator
==================

AI 칩(NPU)이 하는 가장 기본적인 계산인 MAC(Multiply-Accumulate, 곱하고 더하기)을
파이썬 반복문으로 직접 구현한 시뮬레이터.

외부 라이브러리 사용 금지 조건에 맞춰 표준 라이브러리(json, time, re)만 사용한다.
"""

import json
import re
import time

# ------------------------------------------------------------
# 설정 값
# ------------------------------------------------------------
EPSILON = 1e-9              # 두 점수 차이가 이보다 작으면 '동점'으로 본다
REPEAT = 10                 # 성능 측정 반복 횟수 (요구사항: 최소 10회)
OPTIMIZATION_REPEAT = 300   # 보너스 최적화 비교용 반복 횟수 (측정 오차를 줄이기 위해 더 많이)
DEFAULT_DATA_FILE = "data.json"
PERF_SIZES = (3, 5, 13, 25)

# 프로그램 내부에서 쓰는 '표준 라벨' 2가지
CROSS = "Cross"
X = "X"

# 여러 가지 표기를 표준 라벨로 바꿔 주는 표 (라벨 정규화)
LABEL_TABLE = {
    "+": CROSS,
    "cross": CROSS,
    "plus": CROSS,
    "십자가": CROSS,
    "x": X,
    "×": X,
    "엑스": X,
}

LINE = "-" * 52


# ============================================================
# 1. 라벨 정규화
# ============================================================
def normalize_label(value):
    """
    '+' / 'cross' / 'Cross' → 'Cross',  'x' / 'X' / '×' → 'X'
    해석할 수 없으면 None 을 돌려준다.
    왜 필요한가?
      데이터 파일에서는 expected 를 '+' 로, 필터 키는 'cross' 로 쓴다.
      표기가 서로 다르면 비교할 수 없으므로, 프로그램 안에서는
      항상 한 가지 표기(Cross / X)로 바꿔서 사용한다.
      비교 규칙이 바뀌는 경우와 표기를 바꾸는 경우 각각 함수와 표를 고치기 위해 나눠두었다.
    """
    if not isinstance(value, str):
        return None
    return LABEL_TABLE.get(value.strip().lower())


# ============================================================
# 2. 패턴 / 필터 만들기  (보너스 2: 패턴 생성기)
# ============================================================
def make_cross(size):
    """
    N×N 십자가(+) 패턴을 만든다. 가운데 행과 가운데 열이 1.
    짝수를 제외했기 때문에 가운데 1로 채우는 규칙이 아닌 단순히 정수 나눗셈만으로 구성하였다.
    """
    middle = size // 2
    return [
        [1 if (row == middle or col == middle) else 0 for col in range(size)]
        for row in range(size)
    ]


def make_x(size):
    """N×N X 패턴을 만든다. 두 대각선이 1."""
    return [
        [1 if (row == col or row + col == size - 1) else 0 for col in range(size)]
        for row in range(size)
    ]


def flatten(matrix):
    """2차원 배열 → 1차원 배열 (길이 N²). 보너스 1(최적화)에 사용."""
    flat = []
    for row in matrix:
        for value in row:
            flat.append(value)
    return flat


# ============================================================
# 3. MAC 연산 (이 프로그램의 심장)
# ============================================================
def mac(pattern, filter_matrix):
    """
    같은 위치의 값끼리 곱하고(Multiply) 전부 더한다(Accumulate).

    점수가 클수록 "입력 패턴이 이 필터와 닮았다"는 뜻이다.
    NumPy 같은 라이브러리 없이 이중 for 문으로 직접 구현한다.
    """
    total = 0.0
    size = len(pattern)
    for row in range(size):
        for col in range(size):
            total += pattern[row][col] * filter_matrix[row][col]
    return total


def mac_1d(flat_pattern, flat_filter):
    """[보너스 1] 1차원 배열 버전. 행 리스트를 한 번 더 꺼내는 과정이 없다."""
    total = 0.0
    for index in range(len(flat_pattern)):
        total += flat_pattern[index] * flat_filter[index]
    return total


# ============================================================
# 4. 연산 시간 측정
# ============================================================
def measure_mac(pattern, filter_matrix, repeat=REPEAT):
    """
    MAC 연산을 repeat 번 반복해서 (점수, 1회 평균 시간(ms)) 를 돌려준다.

    시간 측정은 '연산 함수 호출 구간'만 감싸므로
    입력/출력/파일 읽기 시간은 포함되지 않는다.
    """
    score = 0.0
    elapsed = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        score = mac(pattern, filter_matrix)
        elapsed += time.perf_counter() - start
    return score, (elapsed / repeat) * 1000.0


def measure_mac_1d(pattern, filter_matrix, repeat=REPEAT):
    """[보너스 1] 1차원 변환 후 측정. 변환 시간은 측정 구간에서 제외한다."""
    flat_pattern = flatten(pattern)
    flat_filter = flatten(filter_matrix)
    score = 0.0
    elapsed = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        score = mac_1d(flat_pattern, flat_filter)
        elapsed += time.perf_counter() - start
    return score, (elapsed / repeat) * 1000.0


# ============================================================
# 5. 점수 비교 정책 (부동소수점 / 동점 처리)
# ============================================================
def decide(score_a, score_b, label_a=CROSS, label_b=X):
    """
    두 점수를 비교해서 판정한다.

    컴퓨터의 소수 계산에는 아주 작은 오차가 생긴다.
    (예: 0.1 을 8번 더하면 0.8 이 아니라 0.7999999999999999)
    그래서 '완전히 같은가(==)' 대신 '차이가 아주 작은가(< 1e-9)' 로 비교하고,
    그 경우는 승자를 정하지 않고 UNDECIDED(판정 불가) 로 둔다.
    """
    if abs(score_a - score_b) < EPSILON:
        return "UNDECIDED"
    return label_a if score_a > score_b else label_b


# ============================================================
# 6. 검증 도우미 (잘못된 데이터를 걸러낸다)
# ============================================================
def validate_matrix(matrix, expected_size=None):
    """정상이면 None, 문제가 있으면 사람이 읽을 수 있는 오류 메시지를 돌려준다."""
    if not isinstance(matrix, list) or len(matrix) == 0:
        return "2차원 배열(리스트) 형태가 아닙니다."

    size = len(matrix)
    if expected_size is not None and size != expected_size:
        return "행 개수가 %d가 아닙니다. (현재 %d)" % (expected_size, size)

    for row_index, row in enumerate(matrix):
        if not isinstance(row, list):
            return "%d번째 행이 배열이 아닙니다." % (row_index + 1)
        if len(row) != size:
            return "%d번째 행의 길이(%d)가 행 개수(%d)와 다릅니다. (정사각형이 아님)" % (
                row_index + 1,
                len(row),
                size,
            )
        for col_index, value in enumerate(row):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return "(%d행 %d열)의 값이 숫자가 아닙니다: %r" % (
                    row_index + 1,
                    col_index + 1,
                    value,
                )
    return None


def parse_filter_key(key):
    """'size_5' → 5 / 형식이 다르면 None"""
    if not isinstance(key, str):
        return None
    matched = re.match(r"^size_(\d+)$", key.strip())
    return int(matched.group(1)) if matched else None


def parse_pattern_key(key):
    """'size_13_2' → (13, 2) / 형식이 다르면 None"""
    if not isinstance(key, str):
        return None
    matched = re.match(r"^size_(\d+)_(\d+)$", key.strip())
    if not matched:
        return None
    return int(matched.group(1)), int(matched.group(2))


# ============================================================
# 7. 출력 도우미
# ============================================================
def cell_text(value):
    """1.0 처럼 소수점이 의미 없는 값은 1 로 짧게 보여준다."""
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return str(number)


def print_matrix(matrix, indent="    "):
    for row in matrix:
        print(indent + " ".join(cell_text(value) for value in row))


def print_score(label, score):
    # repr 을 쓰면 0.7999999999999999 처럼 실제 저장된 값이 그대로 보인다.
    print("%s 점수: %r" % (label, score))


def header(title):
    print("")
    print("#" + LINE)
    print("# " + title)
    print("#" + LINE)


def ask_int(prompt, min_value, max_value):
    """범위 안의 정수를 받을 때까지 다시 묻는다."""
    while True:
        text = input(prompt).strip()
        if text == "":
            print("⚠️  입력이 비어 있습니다. %d~%d 중에서 선택하세요." % (min_value, max_value))
            continue
        try:
            value = int(text)
        except ValueError:
            print("⚠️  숫자만 입력할 수 있습니다. %d~%d 중에서 선택하세요." % (min_value, max_value))
            continue
        if value < min_value or value > max_value:
            print("⚠️  %d~%d 범위의 숫자를 입력하세요." % (min_value, max_value))
            continue
        return value


# ============================================================
# 8. 성능 분석
# ============================================================
def print_performance_table(sizes=PERF_SIZES, repeat=REPEAT):
    """크기별 MAC 평균 연산 시간을 표로 출력한다."""
    print("")
    print("%-10s %14s %12s %16s" % ("크기", "평균 시간(ms)", "연산 횟수", "1회 곱셈당(µs)"))
    print(LINE)

    rows = []
    for size in sizes:
        pattern = make_cross(size)
        filter_matrix = make_cross(size)
        _, average_ms = measure_mac(pattern, filter_matrix, repeat)
        operations = size * size
        per_operation_us = (average_ms * 1000.0) / operations
        rows.append((size, average_ms, operations, per_operation_us))
        print("%-10s %14.4f %12d %16.4f" % (
            "%d×%d" % (size, size),
            average_ms,
            operations,
            per_operation_us,
        ))

    print(LINE)
    print("* 연산 횟수 = N² (한 칸마다 곱셈 1번 + 누적 덧셈 1번)")
    print("* '1회 곱셈당' 시간이 거의 일정하면, 전체 시간이 N² 에 비례한다는 뜻 → O(N²)")
    return rows


# ============================================================
# 9. 모드 1 : 사용자 입력 (3×3)
# ============================================================
def read_matrix(title, size):
    """
    size 줄을 입력받아 size×size 배열을 만든다.
    행/열 개수가 맞지 않거나 숫자로 바꿀 수 없으면 처음부터 다시 입력받는다.
    """
    while True:
        print("")
        print("%s (%d줄 입력, 공백으로 구분)" % (title, size))

        rows = []
        failed = False
        for _ in range(size):
            line = input().strip()
            tokens = line.split()

            if len(tokens) != size:
                print(
                    "⚠️  입력 형식 오류: 각 줄에 %d개의 숫자를 공백으로 구분해 입력하세요. "
                    "(입력된 개수: %d) → 처음부터 다시 입력합니다." % (size, len(tokens))
                )
                failed = True
                break

            try:
                rows.append([float(token) for token in tokens])
            except ValueError:
                print("⚠️  숫자로 바꿀 수 없는 값이 있습니다. → 처음부터 다시 입력합니다.")
                failed = True
                break

        if failed:
            continue

        problem = validate_matrix(rows, size)
        if problem:
            print("⚠️  %s → 처음부터 다시 입력합니다." % problem)
            continue

        return rows


def run_user_mode(size=3):
    """필터 A, B 와 패턴을 직접 입력받아 판정한다."""
    header("[1] 필터 입력")
    filter_a = read_matrix("필터 A", size)
    filter_b = read_matrix("필터 B", size)

    print("")
    print("✓ 필터 A 저장 완료")
    print_matrix(filter_a)
    print("✓ 필터 B 저장 완료")
    print_matrix(filter_b)

    header("[2] 패턴 입력")
    pattern = read_matrix("패턴", size)
    print("")
    print("✓ 패턴 저장 완료")
    print_matrix(pattern)

    header("[3] MAC 결과")
    score_a, time_a = measure_mac(pattern, filter_a)
    score_b, time_b = measure_mac(pattern, filter_b)
    verdict = decide(score_a, score_b, "A", "B")

    print_score("A", score_a)
    print_score("B", score_b)
    print("연산 시간(평균/%d회): A %.4f ms / B %.4f ms" % (REPEAT, time_a, time_b))
    print("두 점수 차이: %r (기준 epsilon = %r)" % (abs(score_a - score_b), EPSILON))

    if verdict == "UNDECIDED":
        print("판정: 판정 불가 (|A-B| < %r)" % EPSILON)
    else:
        print("판정: %s" % verdict)

    header("[4] 성능 분석 (%d×%d, 평균/%d회)" % (size, size, REPEAT))
    print_performance_table((size,))


# ============================================================
# 10. 모드 2 : data.json 분석
# ============================================================
def load_json_file(path):
    """
    JSON 파일을 읽는다.
    실패하면 (None, 오류메시지) 를 돌려주고, 프로그램은 계속 실행된다.
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file), None
    except FileNotFoundError:
        return None, "파일을 찾을 수 없습니다: %s" % path
    except ValueError as error:
        return None, "JSON 형식이 잘못되었습니다: %s" % error
    except (OSError, UnicodeDecodeError) as error:
        return None, "파일을 읽지 못했습니다: %s" % error


def load_filters(raw_filters):
    """
    {"size_5": {"cross": [...], "x": [...]}}
      → {5: {"Cross": [...], "X": [...]}}
    로 정규화한다. 문제가 있는 항목은 건너뛰고 메시지로 남긴다.
    """
    filters = {}
    messages = []

    if not isinstance(raw_filters, dict):
        return filters, ["✗ filters 항목이 없거나 형식이 올바르지 않습니다."]

    # size_5, size_13, size_25 순서로 보이도록 크기 숫자 기준으로 정렬한다.
    ordered_keys = sorted(
        raw_filters.keys(),
        key=lambda k: (parse_filter_key(k) is None, parse_filter_key(k) or 0, str(k)),
    )

    for key in ordered_keys:
        size = parse_filter_key(key)
        if size is None:
            messages.append("✗ %s : 'size_N' 형식이 아닌 필터 키라서 건너뜁니다." % key)
            continue

        entry = raw_filters[key]
        if not isinstance(entry, dict):
            messages.append("✗ %s : 필터 항목이 객체(dict) 형태가 아닙니다." % key)
            continue

        table = {}
        for raw_label in sorted(entry.keys()):
            label = normalize_label(raw_label)
            if label is None:
                messages.append("✗ %s : '%s' 라벨을 해석할 수 없습니다." % (key, raw_label))
                continue

            matrix = entry[raw_label]
            problem = validate_matrix(matrix, size)
            if problem:
                messages.append("✗ %s / %s : %s" % (key, raw_label, problem))
                continue

            table[label] = matrix

        if CROSS in table and X in table:
            filters[size] = table
            messages.append("✓ size_%d 필터 로드 완료 (Cross, X)" % size)
        else:
            loaded = ", ".join(sorted(table.keys())) if table else "없음"
            messages.append(
                "✗ size_%d : Cross 와 X 필터가 모두 필요합니다. (로드됨: %s)" % (size, loaded)
            )

    return filters, messages


def evaluate_case(key, entry, filters):
    """패턴 한 건을 판정해서 결과 딕셔너리를 돌려준다. (예외로 중단되지 않는다)"""
    result = {
        "case": key,
        "cross": None,
        "x": None,
        "verdict": None,
        "expected": None,
        "status": "FAIL",
        "reason": "",
    }

    parsed = parse_pattern_key(key)
    if parsed is None:
        result["reason"] = "패턴 키 형식 오류 : 'size_{N}_{번호}' 형태여야 합니다."
        return result
    size = parsed[0]

    if not isinstance(entry, dict):
        result["reason"] = "패턴 항목이 객체(dict) 형태가 아닙니다."
        return result

    expected = normalize_label(entry.get("expected"))
    result["expected"] = expected
    if expected is None:
        result["reason"] = "expected 라벨을 해석할 수 없습니다: %r" % entry.get("expected")
        return result

    if size not in filters:
        result["reason"] = "size_%d 필터가 없어 비교할 수 없습니다." % size
        return result

    problem = validate_matrix(entry.get("input"), size)
    if problem:
        result["reason"] = "패턴 크기/형식 오류 : %s" % problem
        return result

    pattern = entry["input"]
    result["cross"] = mac(pattern, filters[size][CROSS])
    result["x"] = mac(pattern, filters[size][X])
    result["verdict"] = decide(result["cross"], result["x"])

    if result["verdict"] == expected:
        result["status"] = "PASS"
    elif result["verdict"] == "UNDECIDED":
        result["reason"] = "두 점수 차이가 epsilon(%r) 미만이라 동점(UNDECIDED) 처리" % EPSILON
    else:
        result["reason"] = "판정(%s)이 expected(%s)와 다릅니다." % (
            result["verdict"],
            expected,
        )
    return result


def case_sort_key(key):
    """size_5_1, size_5_2, size_13_1 ... 순서로 정렬하기 위한 기준."""
    parsed = parse_pattern_key(key)
    if parsed is None:
        return (1, 0, 0, str(key))
    return (0, parsed[0], parsed[1], str(key))


def run_json_mode(path=None):
    """data.json 을 읽어 모든 패턴을 일괄 판정한다."""
    if path is None:
        path = input("분석할 JSON 파일 (엔터 = %s): " % DEFAULT_DATA_FILE).strip()
        if path == "":
            path = DEFAULT_DATA_FILE

    raw, error = load_json_file(path)
    if error:
        print("")
        print("❌ %s" % error)
        print("   (모드를 다시 선택할 수 있습니다.)")
        return

    if not isinstance(raw, dict):
        print("")
        print("❌ JSON 최상위 구조가 객체(dict) 형태가 아닙니다.")
        return

    header("[1] 필터 로드  (파일: %s)" % path)
    filters, messages = load_filters(raw.get("filters"))
    for message in messages:
        print(message)
    if not filters:
        print("")
        print("⚠️  사용할 수 있는 필터가 없습니다. 모든 케이스가 FAIL 로 처리됩니다.")

    header("[2] 패턴 분석 (라벨 정규화 적용)")
    raw_patterns = raw.get("patterns")
    if not isinstance(raw_patterns, dict):
        print("❌ patterns 항목이 없거나 형식이 올바르지 않습니다.")
        return

    results = []
    for key in sorted(raw_patterns.keys(), key=case_sort_key):
        result = evaluate_case(key, raw_patterns[key], filters)
        results.append(result)

        print("")
        print("--- %s ---" % key)
        if result["cross"] is None:
            print("판정: 판정 불가 | expected: %s | %s" % (
                result["expected"] if result["expected"] else "?",
                result["status"],
            ))
            print("사유: %s" % result["reason"])
            continue

        print_score("Cross", result["cross"])
        print_score("X", result["x"])
        print("판정: %s | expected: %s | %s" % (
            result["verdict"],
            result["expected"],
            result["status"],
        ))
        if result["status"] == "FAIL":
            print("사유: %s" % result["reason"])

    header("[3] 성능 분석 (평균/%d회)" % REPEAT)
    print_performance_table(PERF_SIZES)

    header("[4] 결과 요약")
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] != "PASS"]
    print("총 테스트: %d개" % len(results))
    print("통과: %d개" % len(passed))
    print("실패: %d개" % len(failed))

    if failed:
        print("")
        print("실패 케이스:")
        for result in failed:
            print("- %s: %s" % (result["case"], result["reason"]))
    else:
        print("")
        print("실패 케이스 없음 (라벨 정규화 + epsilon 비교 정책이 정상 동작)")


# ============================================================
# 11. 보너스 1 : 2차원 vs 1차원 배열 최적화 비교
# ============================================================
def print_optimization_report(sizes=PERF_SIZES, repeat=OPTIMIZATION_REPEAT):
    """
    [보너스 1] 2차원 배열 접근 vs 1차원 배열 접근 성능 비교.

    한 번의 연산이 0.00x ms 수준이라 10회 평균으로는 측정 오차가 실제 차이보다 크다.
    그래서 이 비교만 반복 횟수를 늘려서(기본 300회) 값을 안정시킨다.
    """
    print("")
    print("(반복 %d회 평균 - 측정 오차를 줄이기 위해 성능 표보다 많이 반복합니다)" % repeat)
    print("%-10s %16s %16s %12s" % ("크기", "2차원(ms)", "1차원(ms)", "변화율"))
    print(LINE)

    for size in sizes:
        pattern = make_cross(size)
        filter_matrix = make_cross(size)

        score_2d, time_2d = measure_mac(pattern, filter_matrix, repeat)
        score_1d, time_1d = measure_mac_1d(pattern, filter_matrix, repeat)

        if time_2d > 0:
            change = (time_2d - time_1d) / time_2d * 100.0
        else:
            change = 0.0

        # 두 방식의 계산 결과가 같은지도 함께 확인한다.
        same = "같음" if abs(score_2d - score_1d) < EPSILON else "다름!"
        print("%-10s %16.4f %16.4f %11.1f%%  (결과 %s)" % (
            "%d×%d" % (size, size),
            time_2d,
            time_1d,
            change,
            same,
        ))

    print(LINE)
    print("* 변화율이 양수면 1차원 방식이 더 빠르다는 뜻 (행 리스트를 한 번 더 꺼내는 과정이 없어짐)")
    print("* 연산 횟수 N² 자체는 그대로이므로 시간 복잡도는 여전히 O(N²)")


# ============================================================
# 12. 메인 실행 흐름
# ============================================================
def print_menu():
    print("")
    print("[모드 선택]")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    print("3. 성능 분석 + 최적화 비교 (보너스)")
    print("4. 종료")


def main():
    print("")
    print("=== Mini NPU Simulator ===")

    while True:
        print_menu()
        choice = ask_int("선택: ", 1, 4)

        if choice == 1:
            run_user_mode(3)
        elif choice == 2:
            run_json_mode()
        elif choice == 3:
            header("성능 분석 (평균/%d회)" % REPEAT)
            print_performance_table(PERF_SIZES)
            header("[보너스] 1차원 배열 최적화 비교")
            print_optimization_report(PERF_SIZES)
        else:
            print("")
            print("프로그램을 종료합니다.")
            break


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        # Ctrl+C 나 입력 종료에도 오류 화면 없이 깔끔하게 끝낸다.
        print("")
        print("입력이 중단되었습니다. 프로그램을 종료합니다.")
