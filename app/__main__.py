"""支持 python -m app 方式启动"""
import sys

from app.main import main

if __name__ == "__main__":
    sys.exit(main())
