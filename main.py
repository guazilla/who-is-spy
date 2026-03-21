import os
import sys

def main():
    try:
        from gui import run_gui
        run_gui()
    except ImportError as e:
        print(f"无法加载 GUI 模块: {e}")
        print("请确保已安装依赖：pip install PyQt6")

if __name__ == "__main__":
    main()
