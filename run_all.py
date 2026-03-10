import subprocess
import sys
from pathlib import Path

from src.main_generate_demo_data import main as generate_demo_data
from src.main_load_benchmarks import main as load_benchmarks


def main() -> None:
    print("Step 1/3: Loading benchmark assumptions...")
    load_benchmarks()

    print("Step 2/3: Generating demo media and KPI data...")
    generate_demo_data()

    print("Step 3/3: Starting Streamlit app...")
    app_path = Path(__file__).resolve().parent / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path)],
        check=True,
    )


if __name__ == "__main__":
    main()
