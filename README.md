# ✈ Flip Clock — Desktop Application

A premium, native Python desktop application built with **PySide6** (Qt for Python). It features highly detailed vector-based split-flap digit displays, smooth custom animations, and live local date/timezone tracking.

---

## 🌟 Features

* **3D Split-Flap Animations**: Snappy, custom-rendered vector split-flap displays simulating real 3D hardware flap rotation with falling shadows.
* **Pulsing Separators**: Breathing amber glow colons between hours, minutes, and seconds using sine wave transparency modulation.
* **Format Toggler**: Seamlessly switch between **12-Hour** and **24-Hour** formats with an animated, modern toggle switch.
* **Persisted Settings**: Your preferred time format (12H vs 24H) is automatically saved and restored on the next startup.
* **System Metadata**: Live display of current date and timezone offset (e.g., UTC+05:30).
* **Responsive Layouts**: Designed with strict aspect-ratio preservation so it looks balanced at any window size or scale.

---

## 🛠 Prerequisites

* **Python 3.10** or higher is recommended.
* **PySide6** library.

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/agenticgemini-hub/flip-clock.git
cd flip-clock
```

### 2. Set Up a Virtual Environment (Recommended)
Creating a virtual environment ensures dependencies do not conflict with your global Python system:

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

**On macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
```bash
python app.py
```

---

## ⚙ Configuration & Customization

### Native Sleep Prevention (Wake Lock)
By default, the application has sleep prevention disabled to allow your monitor to sleep normally. If you want the clock to serve as a continuous screensaver and prevent your PC from turning off the screen:
1. Open `app.py`.
2. Locate the end of the `__init__` constructor for `FlipClockMainWindow` (around line 494).
3. Uncomment the `prevent_sleep()` line:
   ```python
   # Prevent Windows sleep by default
   prevent_sleep()
   ```

---

## 📄 License
This project is open-source and available under the MIT License.
