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
