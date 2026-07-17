"""pytest 根配置。

将仓库根目录加入 ``sys.path``，使得无论从哪个目录调用 ``pytest``，
都能直接 ``import dac3d``（无需先 ``pip install -e .``）。
新人开箱即用：``python -m pytest -q`` 即可运行测试。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
