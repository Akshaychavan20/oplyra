"""
Legacy entry point — redirects to handcrafted production builder.

OpenCV tracing is NOT used for production output.
Reference PNG is visual calibration only; see build_oplyra_symbol.py.
"""
from build_oplyra_symbol import main

if __name__ == "__main__":
    main()
