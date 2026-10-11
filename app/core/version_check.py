import sys

MIN_PYTHON_VERSION = (3, 11)
RECOMMENDED_PYTHON_VERSION = (3, 14)


def verify_python_version(abort_on_fail: bool = True) -> bool:
    """Verifies that the current system Python runtime meets DeskFlow PMS requirements.

    Minimum Required: Python 3.11+
    Recommended:      Python 3.14
    """
    major, minor, micro = sys.version_info[:3]
    current_str = f"{major}.{minor}.{micro}"
    min_str = f"{MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}"
    rec_str = f"{RECOMMENDED_PYTHON_VERSION[0]}.{RECOMMENDED_PYTHON_VERSION[1]}"

    is_compatible = sys.version_info >= MIN_PYTHON_VERSION

    if is_compatible:
        print("\n" + "=" * 65)
        print(f" [SUCCESS] Python Version Check Passed!")
        print(f" Current System Version : {current_str}")
        print(f" Product Requirement    : >={min_str} (Target: {rec_str})")
        print(" Status                 : System meets DeskFlow PMS requirements.")
        print("=" * 65 + "\n")
        return True
    else:
        print("\n" + "!" * 65)
        print(f" [FAILED] Incompatible Python Version Detected!")
        print(f" Current System Version : {current_str}")
        print(f" Product Requirement    : >={min_str} (Target: {rec_str})")
        print(" Status                 : Incompatible runtime. Aborting startup.")
        print(" Please switch to Python 3.11 - 3.14 or activate the correct venv.")
        print("!" * 65 + "\n")
        if abort_on_fail:
            sys.exit(1)
        return False


if __name__ == "__main__":
    verify_python_version(abort_on_fail=True)
