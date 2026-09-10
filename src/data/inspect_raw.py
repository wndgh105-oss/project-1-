"""data/raw/ 아래 모든 CSV를 스캔해서 행/열/결측률/용량을 보고하는 인벤토리 스크립트.

왜 필요한가: STEP 1~2 전까지는 원본 데이터의 실제 구조(행수, 결측률, 라벨 분포)를
모르는 채로 다음 단계를 설계하게 된다. 숫자를 지어내지 않는다는 프로젝트 규칙(절대 규칙 1)을
지키려면, 이후 모든 문서·코드가 참조할 "실측 인벤토리"를 가장 먼저 만들어야 한다.
"""
from pathlib import Path

import pandas as pd

# 경로 하드코딩 금지 규칙: 이 파일 위치 기준 상대경로로 raw/interim을 찾는다.
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
INTERIM_DIR = ROOT / "data" / "interim"
INTERIM_DIR.mkdir(parents=True, exist_ok=True)

# APS Scania처럼 CSV 앞에 라이선스/설명 텍스트가 몇 줄 붙어 있는 파일이 있다.
# 특정 파일명에 맞춰 skiprows를 하드코딩하면 다른 데이터셋에서 깨지므로,
# "실제 데이터 행들의 콤마 개수"를 보고 진짜 헤더 줄을 스스로 찾는다.
def _detect_header_row(path: Path, encoding: str, probe_lines: int = 60) -> int:
    with open(path, "r", encoding=encoding, errors="strict") as f:
        lines = [f.readline() for _ in range(probe_lines)]
    lines = [l for l in lines if l]  # 파일이 probe_lines보다 짧은 경우 대비
    comma_counts = [l.count(",") for l in lines]
    if not comma_counts:
        return 0
    # 가장 흔한 콤마 개수 = 데이터 본문의 콤마 개수(즉 컬럼수-1)라고 가정
    mode_count = max(set(comma_counts), key=comma_counts.count)
    if mode_count == 0:
        return 0  # 콤마가 아예 없으면 그냥 첫 줄을 헤더로 취급
    for i, c in enumerate(comma_counts):
        if c == mode_count:
            return i
    return 0


def _read_csv_robust(path: Path) -> tuple[pd.DataFrame, str]:
    """utf-8로 먼저 시도하고, 실패하면 cp949로 재시도한다 (절대 규칙: 한글 인코딩 대응)."""
    last_err = None
    for encoding in ("utf-8", "cp949"):
        try:
            header_row = _detect_header_row(path, encoding)
            df = pd.read_csv(
                path,
                encoding=encoding,
                skiprows=header_row,
                na_values=["na", "NA", "NaN", ""],
                low_memory=False,
            )
            return df, encoding
        except (UnicodeDecodeError, UnicodeError) as e:
            last_err = e
            continue
    raise last_err


def inspect_file(path: Path) -> dict:
    df, encoding = _read_csv_robust(path)
    size_mb = path.stat().st_size / (1024 * 1024)
    missing_pct = (df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100) if df.size else 0.0

    print(f"\n{'=' * 70}")
    print(f"파일: {path.relative_to(RAW_DIR)}")
    print(f"인코딩: {encoding} | 행: {df.shape[0]:,} | 열: {df.shape[1]} | 용량: {size_mb:.2f}MB | 전체 결측률: {missing_pct:.2f}%")
    print(f"열 목록: {list(df.columns)[:15]}{' ...' if df.shape[1] > 15 else ''}")
    print(df.dtypes.value_counts().to_string())

    # 라벨로 보이는 열(class, failure, label, target 등 이름 패턴) 분포 출력
    label_like_names = {"class", "label", "target", "failure", "y"}
    for col in df.columns:
        if col.lower() in label_like_names:
            print(f"\n[라벨 후보] {col} 값 분포 (비율):")
            print(df[col].value_counts(normalize=True).to_string())

    return {
        "file_path": str(path.relative_to(RAW_DIR)),
        "encoding": encoding,
        "n_rows": df.shape[0],
        "n_cols": df.shape[1],
        "columns": ";".join(map(str, df.columns)),
        "missing_pct": round(missing_pct, 4),
        "size_mb": round(size_mb, 4),
    }


def main():
    csv_paths = sorted(RAW_DIR.rglob("*.csv"))
    if not csv_paths:
        print(f"경고: {RAW_DIR} 아래에 CSV가 없습니다. 먼저 데이터를 받아주세요.")
        return

    records = [inspect_file(p) for p in csv_paths]
    inventory = pd.DataFrame(records)
    out_path = INTERIM_DIR / "raw_inventory.csv"
    inventory.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n{'=' * 70}")
    print(f"인벤토리 저장: {out_path.relative_to(ROOT)} ({len(inventory)}개 파일)")


if __name__ == "__main__":
    main()
