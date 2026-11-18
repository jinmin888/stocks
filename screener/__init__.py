from .config import DivergenceConfig, FractalConfig, ScreenConfig, Strength
from .screen import Signal, screen

__version__ = "2026.11.18"  # 每次发布时更新，网站「设置」页和 /api/health 会显示

__all__ = ["DivergenceConfig", "FractalConfig", "ScreenConfig", "Strength", "Signal", "screen"]
