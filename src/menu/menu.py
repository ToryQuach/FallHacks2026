import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)


def load_personalities() -> List[Dict[str, Any]]:
  """Scans `src/personalities/` for all *.json files and loads them.

  Falls back to a default mock profile if the directory is missing or empty.
  """
  base_dir = Path(__file__).resolve().parent.parent / "personalities"
  personalities: List[Dict[str, Any]] = []

  if base_dir.exists() and base_dir.is_dir():
    for file_path in sorted(base_dir.glob("*.json")):
      try:
        with open(file_path, "r", encoding="utf-8") as f:
          data = json.load(f)
          if "name" in data:
            data["_filename"] = file_path.name
            personalities.append(data)
      except (json.JSONDecodeError, OSError) as err:
        print(f"[Warning] Failed to parse personality file {file_path}: {err}")

  if not personalities:
    personalities.append({
        "name": "Draco Malfoid",
        "overview": (
            "You are Draco Malfoid, the haughty, sharp-tongued, genderbent"
            " parody of Draco Malfoy."
        ),
        "tone": (
            "Pompous, aristocratic mean-girl, theatrical, easily offended, and"
            " dripping with dry sarcasm."
        ),
        "behavior": (
            "Look down on the user playfully or dramatically; treat ordinary"
            " matters as beneath your high-society standards; invoke family"
            " influence and wealth whenever challenged."
        ),
        "boundaries": (
            "Keep insults theatrical, satirical, and strictly in the realm of"
            " harmless school-rivalry comedy rather than genuine malice."
        ),
        "_filename": "default_fallback.json",
    })

  return personalities


class SidekickConfigMenu(QDialog):

  def __init__(self, parent=None):
    super().__init__(parent)
    self.setWindowTitle("Digital Sidekick - Setup & Config")
    self.setFixedWidth(480)

    self.setStyleSheet("""
            QDialog {
                background-color: #1e1e24;
                color: #f0f0f0;
                font-family: 'Segoe UI', sans-serif;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
                font-weight: 500;
            }
            QLineEdit, QComboBox, QSpinBox {
                background-color: #2b2b36;
                color: #ffffff;
                border: 1px solid #3d3d4e;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 13px;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #6366f1;
            }
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 14px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4338ca;
            }
            QPushButton#secondaryBtn {
                background-color: #374151;
            }
            QPushButton#secondaryBtn:hover {
                background-color: #4b5563;
            }
        """)

    self.config_result: Optional[Dict[str, Any]] = None
    self.personalities_data = load_personalities()

    # Main Layout
    main_layout = QVBoxLayout(self)
    main_layout.setSpacing(16)
    main_layout.setContentsMargins(20, 20, 20, 20)

    form_layout = QFormLayout()
    form_layout.setSpacing(12)
    form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

    # 1. Personality Dropdown
    self.personality_combo = QComboBox()
    for item in self.personalities_data:
      self.personality_combo.addItem(item["name"], userData=item)
    form_layout.addRow("Personality:", self.personality_combo)

    # 2. Goal Input
    self.goal_input = QLineEdit()
    self.goal_input.setPlaceholderText(
        "e.g., Debugging Dijkstra algorithm in C++"
    )
    form_layout.addRow("Session Goal:", self.goal_input)

    # 3. Time Selection (Hours, Minutes, Seconds)
    time_container = QHBoxLayout()
    time_container.setSpacing(8)

    self.spin_hours = self._create_time_spinbox(0, 23, "h")
    self.spin_mins = self._create_time_spinbox(0, 59, "m")
    self.spin_secs = self._create_time_spinbox(0, 59, "s")

    time_container.addWidget(QLabel("H:"))
    time_container.addWidget(self.spin_hours)
    time_container.addWidget(QLabel("M:"))
    time_container.addWidget(self.spin_mins)
    time_container.addWidget(QLabel("S:"))
    time_container.addWidget(self.spin_secs)
    form_layout.addRow("Duration:", time_container)

    # 4. Check Interval Slider
    freq_container = QHBoxLayout()
    self.freq_slider = QSlider(Qt.Orientation.Horizontal)
    self.freq_slider.setRange(1, 120)
    self.freq_slider.setValue(5)
    self.freq_label = QLabel("5s")
    self.freq_slider.valueChanged.connect(
        lambda val: self.freq_label.setText(f"{val}s")
    )
    freq_container.addWidget(self.freq_slider)
    freq_container.addWidget(self.freq_label)
    form_layout.addRow("Check Interval:", freq_container)

    # 5. Speak Min Seconds Slider
    speak_min_container = QHBoxLayout()
    self.speak_min_slider = QSlider(Qt.Orientation.Horizontal)
    self.speak_min_slider.setRange(2, 120)
    self.speak_min_slider.setValue(6)
    self.speak_min_label = QLabel("6s")
    self.speak_min_slider.valueChanged.connect(self._on_speak_min_changed)
    speak_min_container.addWidget(self.speak_min_slider)
    speak_min_container.addWidget(self.speak_min_label)
    form_layout.addRow("Speak Min Time:", speak_min_container)

    # 6. Speak Max Seconds Slider
    speak_max_container = QHBoxLayout()
    self.speak_max_slider = QSlider(Qt.Orientation.Horizontal)
    self.speak_max_slider.setRange(2, 180)
    self.speak_max_slider.setValue(7)
    self.speak_max_label = QLabel("7s")
    self.speak_max_slider.valueChanged.connect(self._on_speak_max_changed)
    speak_max_container.addWidget(self.speak_max_slider)
    speak_max_container.addWidget(self.speak_max_label)
    form_layout.addRow("Speak Max Time:", speak_max_container)

    main_layout.addLayout(form_layout)

    # Action Buttons
    btn_container = QHBoxLayout()
    btn_container.setSpacing(10)

    self.cancel_btn = QPushButton("Cancel")
    self.cancel_btn.setObjectName("secondaryBtn")
    self.cancel_btn.clicked.connect(self.reject)

    self.launch_btn = QPushButton("Launch Sidekick 🚀")
    self.launch_btn.clicked.connect(self._on_launch)

    btn_container.addWidget(self.cancel_btn)
    btn_container.addWidget(self.launch_btn)
    main_layout.addLayout(btn_container)

  def _create_time_spinbox(
      self, min_val: int, max_val: int, suffix: str
  ) -> QSpinBox:
    box = QSpinBox()
    box.setRange(min_val, max_val)
    box.setValue(0)
    box.setAlignment(Qt.AlignmentFlag.AlignCenter)
    box.setSuffix(f" {suffix}")
    return box

  def _on_speak_min_changed(self, val: int):
    self.speak_min_label.setText(f"{val}s")
    # Guarantee min doesn't exceed max
    if val > self.speak_max_slider.value():
      self.speak_max_slider.setValue(val)

  def _on_speak_max_changed(self, val: int):
    self.speak_max_label.setText(f"{val}s")
    # Guarantee max isn't lower than min
    if val < self.speak_min_slider.value():
      self.speak_min_slider.setValue(val)

  def _on_launch(self):
    total_seconds = (
        self.spin_hours.value() * 3600
        + self.spin_mins.value() * 60
        + self.spin_secs.value()
    )

    selected_personality = self.personality_combo.currentData()

    self.config_result = {
        "personality": selected_personality,
        "goal": self.goal_input.text().strip() or "General Productivity",
        "duration_seconds": total_seconds,
        "duration_hms": (
            f"{self.spin_hours.value():02d}:{self.spin_mins.value():02d}:{self.spin_secs.value():02d}"
        ),
        "check_interval_seconds": self.freq_slider.value(),
        "speak_min_seconds": self.speak_min_slider.value(),
        "speak_max_seconds": self.speak_max_slider.value(),
    }
    self.accept()


def menu() -> Optional[Dict[str, Any]]:
  """Displays the setup menu and returns the selected parameters."""
  app = QApplication.instance()
  owns_app = False
  if app is None:
    app = QApplication(sys.argv)
    owns_app = True

  dialog = SidekickConfigMenu()
  result = dialog.exec()

  config = dialog.config_result if result == QDialog.DialogCode.Accepted else None
  return config


if __name__ == "__main__":
  settings = menu()
  print("\nCaptured Menu Settings:")
  print(json.dumps(settings, indent=2, ensure_ascii=False))