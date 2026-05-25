# Project-NUC Test Plan

## 1. Directory Structure
* `docs/test_plan.md`: This document outlining the testing strategy.
* `tests/`: Directory containing all automated test scripts.
  * `tests/unit/`: Tests for utility functions, math, and backend hardware abstraction.
  * `tests/integration/`: Tests for Tkinter UI components and their interaction with the mocked backend.
  * `tests/conftest.py`: Shared pytest fixtures (e.g., mocked backends, fake UI root window).

## 2. Technology Stack
* **Test Framework:** `pytest` (Industry standard, highly readable, scalable test execution).
* **Mocking:** `pytest-mock` and Python's built-in `unittest.mock` (Crucial for simulating hardware file reads/writes without needing the actual NUC/QC71 laptop or root permissions).
* **Coverage:** `pytest-cov` (To measure how much of the application code is exercised by our tests).
* **UI Testing:** Tkinter's internal event generation (e.g., `widget.invoke()`, `widget.event_generate()`). For CI/CD environments, we can use `pytest-xvfb` to run the GUI tests headlessly.

## 3. Phase 1: Unit Testing (Backend & Utilities)
**Goal:** Ensure logic and hardware abstraction layers format data correctly.
* **Utilities:** Test color sanitization, hex conversions, and math helpers (e.g., making sure `#FFF` becomes `#ffffff`).
* **Backend Drivers (`backend/`):** 
  * Mock `open()`, `read()`, and `write()` for kernel/sysfs hardware files.
  * Verify that `set_lightbar_color()` writes the exact expected byte sequence/hex string to the correct mocked file path.
  * Verify that battery threshold settings convert percentage integers to the correct driver format.
  * Test error handling (e.g., ensure `BackendError` is raised gracefully if the sysfs file is missing or lacks read/write permissions).

## 4. Phase 2: Integration Testing (UI + State)
**Goal:** Ensure UI interactions trigger the correct backend calls and app state is maintained.
* **State Management:** Load a fake `config.json` payload into `app.load_state()` and assert Tkinter `StringVar`/`IntVar` variables update to reflect the saved settings.
* **UI Interactions:** Instantiate `LightbarTab` and `BatteryTab` with a `MockBackend`. Simulate user actions (button clicks, slider movements, radio button selections), then assert the mock backend received the expected function calls with correct arguments.
* **Graceful Degradation:** Instantiate the UI with a backend that returns `available = False` (simulating missing drivers) and ensure the "⚠ Lightbar not detected" warning labels appear and controls are handled safely.

## 5. Phase 3: Manual Hardware Testing Checklist
**Goal:** Verify integration on actual NUC/QC71 hardware.
* **Lightbar:** Compare the smoothness of the Tkinter canvas animation vs the actual physical lightbar. Verify the "Reset" button flushes embedded controller (EC) states correctly.
* **Battery Control:** Set a charge limit (e.g., 60%), drain the battery to 50%, plug in the AC adapter, and physically verify that charging stops at exactly 60%.
* **Driver Lifecycle:** Unload the kernel module (`nuc_wmi` or `qc71_laptop`) via terminal while the UI is running. Verify the app doesn't crash and displays a fallback error.