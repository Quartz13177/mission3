"""
data.json 생성기.

main.py 의 패턴 생성기(make_cross / make_x)를 그대로 재활용한다.  [보너스 2 활용]
25×25 필터는 값이 625개라 손으로 적을 수 없으므로 규칙으로 만들어 낸다.

실행:  python make_data.py
"""

import json
import re

from main import make_cross, make_x

# ------------------------------------------------------------
# 부동소수점 함정 패턴 (5×5)
#
#   십자가 위치 8칸에 0.1 을 놓고, X 위치 2칸에 0.4 를 놓았다.
#   수학적으로는  0.1 × 8 = 0.8,  0.4 × 2 = 0.8  로 완전히 같다.
#   그러나 컴퓨터는 0.1 을 정확히 저장하지 못하므로
#     Cross 점수 = 0.7999999999999999
#     X     점수 = 0.8
#   처럼 미세하게 달라진다. epsilon 정책을 검증하기 위한 의도적 케이스.
# ------------------------------------------------------------
FLOAT_TRAP = [
    [0.4, 0, 0.1, 0, 0],
    [0, 0, 0.1, 0, 0],
    [0.1, 0.1, 0, 0.1, 0.1],
    [0, 0, 0.1, 0, 0],
    [0, 0, 0.1, 0, 0.4],
]


def build():
    """과제 명세에 나온 구조대로 데이터를 조립한다."""
    filters = {}
    for size in (5, 13, 25):
        # 필터 키는 일부러 소문자('cross', 'x')로 둔다 → 라벨 정규화 검증용
        filters["size_%d" % size] = {
            "cross": make_cross(size),
            "x": make_x(size),
        }

    patterns = {
        # 5×5
        "size_5_1": {"input": make_x(5), "expected": "x"},
        "size_5_2": {"input": make_cross(5), "expected": "+"},
        "size_5_3": {"input": FLOAT_TRAP, "expected": "x"},   # 부동소수점 함정
        # 13×13
        "size_13_1": {"input": make_cross(13), "expected": "+"},
        "size_13_2": {"input": make_x(13), "expected": "x"},
        # 25×25
        "size_25_1": {"input": make_cross(25), "expected": "+"},
        "size_25_2": {"input": make_x(25), "expected": "x"},
    }

    return {"filters": filters, "patterns": patterns}


def build_broken():
    """
    예외 처리 검증용 데이터. 일부러 여러 종류의 오류를 넣었다.
    프로그램이 중단되지 않고 케이스 단위로 FAIL 처리하는지 확인한다.
    """
    return {
        "filters": {
            "size_5": {"cross": make_cross(5), "x": make_x(5)},
        },
        "patterns": {
            # ① 크기 불일치 : 키는 size_5 인데 실제로는 4×4
            "size_5_1": {
                "input": [[0, 1, 0, 0], [1, 1, 1, 0], [0, 1, 0, 0], [0, 0, 0, 0]],
                "expected": "+",
            },
            # ② 숫자가 아닌 값이 섞임
            "size_5_2": {
                "input": [
                    [0, 1, 0, 1, 0],
                    [1, 1, "?", 1, 1],
                    [0, 1, 0, 1, 0],
                    [1, 1, 1, 1, 1],
                    [0, 1, 0, 1, 0],
                ],
                "expected": "x",
            },
            # ③ expected 라벨을 해석할 수 없음
            "size_5_3": {"input": make_x(5), "expected": "동그라미"},
            # ④ 해당 크기의 필터가 없음
            "size_13_1": {"input": make_cross(13), "expected": "+"},
            # ⑤ 패턴 키 형식 위반
            "pattern_A": {"input": make_x(5), "expected": "x"},
        },
    }


def dumps_matrix_friendly(data):
    """
    행렬의 한 행을 한 줄로 붙여서 보여주는 JSON 문자열을 만든다.

    왜 필요한가?
      json 모듈의 indent 옵션은 모든 배열을 똑같이 취급해서
      [0, 0, 1, 0, 0] 같은 한 행도 5줄로 펼쳐 버린다.
      25x25 필터 하나가 625줄이 되어 행렬 모양을 눈으로 확인할 수 없다.

      그래서 일단 평소대로 만든 다음,
      '안에 다른 배열이 없는 가장 안쪽 배열'(= 행렬의 한 행)만 한 줄로 합친다.
      공백은 JSON 문법에서 의미가 없으므로 데이터는 전혀 바뀌지 않는다.
    """
    text = json.dumps(data, ensure_ascii=False, indent=2)

    def collapse(match):
        # match.group(1) = 대괄호 사이의 내용. 줄바꿈과 공백을 한 칸으로 정리한다.
        return "[" + " ".join(match.group(1).split()) + "]"

    # [^\[\]] = 대괄호가 아닌 글자 → 안에 배열이 없는 '가장 안쪽 배열'만 걸린다
    return re.sub(r"\[([^\[\]]*)\]", collapse, text)


def save(data, path):
    with open(path, "w", encoding="utf-8") as file:
        file.write(dumps_matrix_friendly(data))
        file.write("\n")
    print("생성 완료: %s" % path)


if __name__ == "__main__":
    save(build(), "data.json")
    save(build_broken(), "data_broken.json")
