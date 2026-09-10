# data/interim/

정제 중간물. raw를 가공하는 과정에서 나오는 캐시·중간 산출물을 둔다.
예: `raw_inventory.csv`(STEP 1), `mtbf_mttr.parquet`(STEP 3).

재현 가능해야 하므로, 이 폴더가 통째로 사라져도 `src/` 스크립트를 다시 돌리면 복원되어야 한다.
