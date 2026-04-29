import sys
from pathlib import Path

# crawler/ 패키지 루트와 프로젝트 루트(shared/ 접근)를 path에 추가
_CRAWLER_ROOT = Path(__file__).parent.parent
_PROJECT_ROOT = _CRAWLER_ROOT.parent

for p in [str(_CRAWLER_ROOT), str(_PROJECT_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)
