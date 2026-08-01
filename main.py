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
    """
    if not isinstance(value, str):
        return None
    return LABEL_TABLE.get(value.strip().lower())


# ============================================================
# 2. 패턴 / 필터 만들기  (보너스 2: 패턴 생성기)
# ============================================================
def make_cross(size):
    """N×N 십자가(+) 패턴을 만든다. 가운데 행과 가운데 열이 1."""
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
