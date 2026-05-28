"""
Flip Clock — Desktop Application
A premium, native Python desktop application built with PySide6.
Features highly detailed, hardware-accelerated 3D split-flap flip animations,
smooth pulsing ambient glow separators, custom styling, responsive aspect ratios,
and native Windows sleep prevention (Wake Lock).
"""

import os
import sys
import math
import time
import ctypes
import datetime

from PySide6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve, QSettings, QRectF, QPointF, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient, QRadialGradient, QPainterPath, QTransform
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSizePolicy


# --- Windows Sleep Prevention ---
ES_CONTINUOUS       = 0x80000000
ES_SYSTEM_REQUIRED  = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

_sleep_prevented = False


def prevent_sleep():
    """Prevent the system from sleeping / locking the screen."""
    global _sleep_prevented
    try:
        if sys.platform == "win32":
            ctypes.windll.kernel32.SetThreadExecutionState(
                ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
            )
            _sleep_prevented = True
            print("Sleep prevention activated.")
            return True
    except Exception as e:
        print(f"Failed to prevent sleep: {e}")
    return False


def allow_sleep():
    """Re-allow the system to sleep normally."""
    global _sleep_prevented
    try:
        if sys.platform == "win32":
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            _sleep_prevented = False
            print("Sleep prevention released.")
            return True
    except Exception as e:
        print(f"Failed to release sleep lock: {e}")
    return False


# --- Custom Switch Widget ---
class ModernToggleSwitch(QWidget):
    """Custom pill-shaped toggle switch for 12H/24H toggle."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(44, 24)
        self._checked = False
        self._knob_x = 2.0  # Left (False, 24H) is 2.0, Right (True, 12H) is 22.0
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(250)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.valueChanged.connect(self._animate_knob)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked, animate=True):
        if self._checked == checked:
            return
        self._checked = checked
        if animate:
            self.animation.setStartValue(self._knob_x)
            self.animation.setEndValue(22.0 if checked else 2.0)
            self.animation.start()
        else:
            self._knob_x = 22.0 if checked else 2.0
            self.update()

    def _animate_knob(self, value):
        self._knob_x = value
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setChecked(not self._checked)
            # Notify toggle switch row if parented to one
            parent = self.parent()
            if hasattr(parent, 'toggle_format'):
                parent.toggle_format(self._checked)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background Pill
        bg_rect = QRectF(0, 0, self.width(), self.height())
        bg_color = QColor(255, 255, 255, 25) if self.underMouse() else QColor(255, 255, 255, 15)
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.setBrush(QBrush(bg_color))
        painter.drawRoundedRect(bg_rect, 12, 12)

        # Knob (Amber Gradient)
        knob_rect = QRectF(self._knob_x, 2, 20, 20)
        knob_gradient = QLinearGradient(knob_rect.topLeft(), knob_rect.bottomRight())
        knob_gradient.setColorAt(0, QColor("#f59e0b"))
        knob_gradient.setColorAt(1, QColor("#d97706"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(knob_gradient))
        painter.drawEllipse(knob_rect)


class ToggleSwitchRow(QWidget):
    """Pill-shaped toggle with side labels '24H' and '12H'."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)

        self.label_24h = QLabel("24H", self)
        self.label_24h.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.label_24h.setStyleSheet("color: #f59e0b;")

        self.switch = ModernToggleSwitch(self)

        self.label_12h = QLabel("12H", self)
        self.label_12h.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.label_12h.setStyleSheet("color: #64748b;")

        self.layout.addWidget(self.label_24h)
        self.layout.addWidget(self.switch)
        self.layout.addWidget(self.label_12h)

    def toggle_format(self, checked):
        if checked:
            self.label_24h.setStyleSheet("color: #64748b;")
            self.label_12h.setStyleSheet("color: #f59e0b;")
        else:
            self.label_24h.setStyleSheet("color: #f59e0b;")
            self.label_12h.setStyleSheet("color: #64748b;")
        
        # Dispatch to Main Window
        main_win = self.window()
        if hasattr(main_win, 'set_12hour_mode'):
            main_win.set_12hour_mode(checked)


# --- Custom Split-Flap Widget ---
class FlipCardWidget(QWidget):
    """Highly detailed vector split-flap digit widget with 3D-simulated rotation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_digit = "0"
        self.target_digit = "0"
        self.animation_progress = 0.0
        
        self.anim = QVariantAnimation(self)
        self.anim.setDuration(550)  # Smooth snappy flip
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim.valueChanged.connect(self._on_anim_val)
        self.anim.finished.connect(self._on_anim_finished)

        # Allow expanding inside layout
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_digit(self, digit, animate=True):
        if self.current_digit == digit and self.target_digit == digit:
            return
        if not animate:
            self.current_digit = digit
            self.target_digit = digit
            self.animation_progress = 0.0
            self.update()
            return
        
        # If already animating, catch up instantly
        if self.anim.state() == QVariantAnimation.State.Running:
            self.anim.stop()
            self.current_digit = self.target_digit
        
        self.target_digit = digit
        self.animation_progress = 0.0
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _on_anim_val(self, val):
        self.animation_progress = val
        self.update()

    def _on_anim_finished(self):
        self.current_digit = self.target_digit
        self.animation_progress = 0.0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # ----------------------------------------------------
        # Aspect Ratio Preservation & Scaling
        # ----------------------------------------------------
        raw_w = self.width()
        raw_h = self.height()
        
        # Proportional dimensions (90 width : 130 height)
        aspect = 90.0 / 130.0
        if raw_w / raw_h > aspect:
            card_w = raw_h * aspect
            card_h = raw_h
        else:
            card_w = raw_w
            card_h = raw_w / aspect

        # Center card inside widget bounding box
        dx = (raw_w - card_w) / 2.0
        dy = (raw_h - card_h) / 2.0
        painter.translate(dx, dy)

        W = card_w
        H = card_h

        # Metrics based on card size
        radius = W * 0.1
        font_size = H * 0.7  # 70% of height for the digit
        font = QFont("Consolas", font_size, QFont.Weight.Bold)
        painter.setFont(font)

        # ----------------------------------------------------
        # Top/Bottom Shapes (Rounded Corners Only on Edges)
        # ----------------------------------------------------
        top_path = QPainterPath()
        top_path.moveTo(0, H / 2)
        top_path.lineTo(0, radius)
        top_path.quadTo(0, 0, radius, 0)
        top_path.lineTo(W - radius, 0)
        top_path.quadTo(W, 0, W, radius)
        top_path.lineTo(W, H / 2)
        top_path.closeSubpath()

        bottom_path = QPainterPath()
        bottom_path.moveTo(0, H / 2)
        bottom_path.lineTo(W, H / 2)
        bottom_path.lineTo(W, H - radius)
        bottom_path.quadTo(W, H, W - radius, H)
        bottom_path.lineTo(radius, H)
        bottom_path.quadTo(0, H, 0, H - radius)
        bottom_path.closeSubpath()

        # Premium Card Gradients (Slate Dark theme)
        top_grad = QLinearGradient(0, 0, 0, H / 2)
        top_grad.setColorAt(0, QColor("#1e293b"))
        top_grad.setColorAt(1, QColor("#141826"))

        bottom_grad = QLinearGradient(0, H / 2, 0, H)
        bottom_grad.setColorAt(0, QColor("#0f172a"))
        bottom_grad.setColorAt(1, QColor("#1a1f2e"))

        border_color = QColor("#2a3042")
        border_pen = QPen(border_color, max(1.0, W * 0.015))

        # ----------------------------------------------------
        # 1. Paint Static Background Top (Target Digit)
        # ----------------------------------------------------
        painter.save()
        painter.setClipPath(top_path)
        painter.fillPath(top_path, QBrush(top_grad))
        painter.setPen(border_pen)
        painter.drawPath(top_path)
        
        painter.setPen(QPen(QColor("#f0f4fc")))
        painter.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self.target_digit)
        painter.restore()

        # ----------------------------------------------------
        # 2. Paint Static Background Bottom (Current Digit)
        # ----------------------------------------------------
        painter.save()
        painter.setClipPath(bottom_path)
        painter.fillPath(bottom_path, QBrush(bottom_grad))
        painter.setPen(border_pen)
        painter.drawPath(bottom_path)
        
        painter.setPen(QPen(QColor("#f0f4fc")))
        painter.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self.current_digit)
        painter.restore()

        # ----------------------------------------------------
        # 3. Paint Rotating Animated Flap
        # ----------------------------------------------------
        progress = self.animation_progress
        if progress > 0.0 and progress < 1.0:
            if progress <= 0.5:
                # Top half falling down: scale height using cos
                painter.save()
                transform = QTransform()
                transform.translate(W / 2, H / 2)
                scale_y = math.cos(progress * math.pi)  # 1.0 -> 0.0
                transform.scale(1.0, scale_y)
                transform.translate(-W / 2, -H / 2)
                painter.setTransform(transform, combine=True)

                painter.setClipPath(top_path)
                painter.fillPath(top_path, QBrush(top_grad))
                painter.setPen(border_pen)
                painter.drawPath(top_path)
                
                painter.setPen(QPen(QColor("#f0f4fc")))
                painter.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self.current_digit)

                # Ambient shadow overlays on the flap as it rotates away from light
                shadow_opacity = int(progress * 2.0 * 180)  # Max 180 (70% opacity)
                painter.fillPath(top_path, QBrush(QColor(0, 0, 0, shadow_opacity)))
                painter.restore()
            else:
                # Bottom half falling down: scale height using sin
                painter.save()
                transform = QTransform()
                transform.translate(W / 2, H / 2)
                scale_y = math.sin((progress - 0.5) * math.pi)  # 0.0 -> 1.0
                transform.scale(1.0, scale_y)
                transform.translate(-W / 2, -H / 2)
                painter.setTransform(transform, combine=True)

                painter.setClipPath(bottom_path)
                painter.fillPath(bottom_path, QBrush(bottom_grad))
                painter.setPen(border_pen)
                painter.drawPath(bottom_path)
                
                painter.setPen(QPen(QColor("#f0f4fc")))
                painter.drawText(QRectF(0, 0, W, H), Qt.AlignmentFlag.AlignCenter, self.target_digit)

                # Ambient shadow overlay fades out as flap aligns with bottom
                shadow_opacity = int((1.0 - progress) * 2.0 * 180)
                painter.fillPath(bottom_path, QBrush(QColor(0, 0, 0, shadow_opacity)))
                painter.restore()

        # ----------------------------------------------------
        # 4. Paint Rivets & Central Split Line
        # ----------------------------------------------------
        # Center split line
        split_pen = QPen(QColor(0, 0, 0, 150), max(1.0, W * 0.012))
        painter.setPen(split_pen)
        painter.drawLine(0, H / 2, W, H / 2)

        # Side Split rivets
        rivet_radius = max(2.5, W * 0.035)
        rivet_y = H / 2
        left_rivet = QRectF(W * 0.03, rivet_y - rivet_radius, rivet_radius * 2, rivet_radius * 2)
        right_rivet = QRectF(W - W * 0.03 - rivet_radius * 2, rivet_y - rivet_radius, rivet_radius * 2, rivet_radius * 2)

        rivet_brush = QBrush(QColor("#3a4055"))
        rivet_border = QPen(QColor("#252a3a"), max(0.5, W * 0.005))
        
        painter.setBrush(rivet_brush)
        painter.setPen(rivet_border)
        painter.drawEllipse(left_rivet)
        painter.drawEllipse(right_rivet)


# --- Custom Pulsing Separator ---
class SeparatorWidget(QWidget):
    """Pulsing amber glowing separator dots representing the colon."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(24, 60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # Tick timer to drive smooth sine pulsing
        self.timer = QTimer(self)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.update)
        self.timer.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()

        t = time.time()
        # Modulate opacity using sine wave for ultra smooth breathing effect
        opacity = 0.60 + 0.40 * math.sin(t * math.pi * 2.0)
        
        dot_color = QColor(245, 158, 11, int(opacity * 255))
        glow_color = QColor(245, 158, 11, int(opacity * 70))

        cx = W / 2.0
        cy1 = H * 0.38
        cy2 = H * 0.62
        
        dot_r = min(W, H) * 0.12
        glow_r = dot_r * 2.5

        for cy in (cy1, cy2):
            # Glow aura
            radial_glow = QRadialGradient(cx, cy, glow_r)
            radial_glow.setColorAt(0, glow_color)
            radial_glow.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(radial_glow))
            painter.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

            # Central Core dot
            painter.setBrush(QBrush(dot_color))
            painter.drawEllipse(QPointF(cx, cy), dot_r, dot_r)


# --- Custom AM/PM Badge ---
class AmpmBadge(QWidget):
    """Glowing Amber AM/PM Badge that appears in 12-hour mode."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(60, 44)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._ampm_text = "AM"
        self._visible = False

    def set_ampm(self, text, visible):
        self._ampm_text = text
        self._visible = visible
        self.setVisible(visible)
        self.update()

    def paintEvent(self, event):
        if not self._visible:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()
        
        box_rect = QRectF(2, 2, W - 4, H - 4)
        
        bg_gradient = QLinearGradient(box_rect.topLeft(), box_rect.bottomRight())
        bg_gradient.setColorAt(0, QColor(245, 158, 11, 38))  # 15% opacity
        bg_gradient.setColorAt(1, QColor(245, 158, 11, 13))  # 5% opacity
        
        painter.setPen(QPen(QColor(245, 158, 11, 64), 1.5))  # 25% opacity
        painter.setBrush(QBrush(bg_gradient))
        painter.drawRoundedRect(box_rect, 8, 8)

        painter.setPen(QPen(QColor("#f59e0b")))
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(box_rect, Qt.AlignmentFlag.AlignCenter, self._ampm_text)


# --- Main Window Application ---
class FlipClockMainWindow(QMainWindow):
    """The central window wrapping the native PySide6 digital clock layout."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("✈ Flip Clock")
        self.setMinimumSize(700, 420)
        self.resize(960, 520)

        # Settings
        self.settings = QSettings("FlipClockApp", "Settings")
        self.is_12hour = self.settings.value("is_12hour", False, type=bool)

        # History tracking to only animate changes
        self.prev_digits = {
            "h_tens": None, "h_ones": None,
            "m_tens": None, "m_ones": None,
            "s_tens": None, "s_ones": None
        }

        self.setup_ui()

        # Trigger tick immediately, then set sync timers
        self.update_clock()
        
        # Start tick timer running at 100ms for accurate transitions
        self.tick_timer = QTimer(self)
        self.tick_timer.setInterval(100)
        self.tick_timer.timeout.connect(self.update_clock)
        self.tick_timer.start()

        # Prevent Windows sleep by default
        prevent_sleep()

    def setup_ui(self):
        # 1. Main Central Widget
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # Main vertical layout
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(40, 40, 40, 20)
        self.main_layout.setSpacing(20)

        # 2. Clock Row Layout
        self.clock_container = QWidget(self.central_widget)
        self.clock_layout = QHBoxLayout(self.clock_container)
        self.clock_layout.setContentsMargins(0, 0, 0, 0)
        self.clock_layout.setSpacing(12)
        self.clock_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Construct time columns
        self.h_group, self.h_tens, self.h_ones = self.make_time_group("Hours")
        self.m_group, self.m_tens, self.m_ones = self.make_time_group("Minutes")
        self.s_group, self.s_tens, self.s_ones = self.make_time_group("Seconds")

        self.sep1 = SeparatorWidget(self.clock_container)
        self.sep2 = SeparatorWidget(self.clock_container)

        self.ampm_badge = AmpmBadge(self.clock_container)

        # Assemble row
        self.clock_layout.addWidget(self.h_group)
        self.clock_layout.addWidget(self.sep1)
        self.clock_layout.addWidget(self.m_group)
        self.clock_layout.addWidget(self.sep2)
        self.clock_layout.addWidget(self.s_group)
        self.clock_layout.addWidget(self.ampm_badge, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.main_layout.addWidget(self.clock_container, stretch=1)

        # 3. Footer Bar Layout
        self.footer_widget = QWidget(self.central_widget)
        self.footer_layout = QHBoxLayout(self.footer_widget)
        self.footer_layout.setContentsMargins(0, 10, 0, 10)
        self.footer_layout.setSpacing(16)

        # Left side info
        self.info_widget = QWidget(self.footer_widget)
        self.info_layout = QHBoxLayout(self.info_widget)
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(8)

        self.date_label = QLabel("", self.info_widget)
        self.date_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
        self.date_label.setStyleSheet("color: #94a3b8; letter-spacing: 0.03em;")

        self.dot_label = QLabel("·", self.info_widget)
        self.dot_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.dot_label.setStyleSheet("color: #64748b; opacity: 0.5;")

        self.tz_label = QLabel("", self.info_widget)
        self.tz_label.setFont(QFont("Consolas", 9))
        self.tz_label.setStyleSheet("color: #64748b;")

        self.info_layout.addWidget(self.date_label)
        self.info_layout.addWidget(self.dot_label)
        self.info_layout.addWidget(self.tz_label)

        # Right side toggle switch row
        self.toggle_row = ToggleSwitchRow(self.footer_widget)
        self.toggle_row.switch.setChecked(self.is_12hour, animate=False)
        self.toggle_row.toggle_format(self.is_12hour)

        self.footer_layout.addWidget(self.info_widget)
        self.footer_layout.addStretch()
        self.footer_layout.addWidget(self.toggle_row)

        self.main_layout.addWidget(self.footer_widget)

    def make_time_group(self, name):
        """Helper to create time columns with dynamic digits and lower labels."""
        group = QWidget(self.clock_container)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Upper row of two digits
        row = QWidget(group)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        
        card_tens = FlipCardWidget(row)
        card_ones = FlipCardWidget(row)
        card_tens.setMinimumSize(90, 130)
        card_ones.setMinimumSize(90, 130)

        row_layout.addWidget(card_tens)
        row_layout.addWidget(card_ones)

        # Lower section title
        label = QLabel(name.upper(), group)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label_font = QFont("Segoe UI", 8, QFont.Weight.Bold)
        label_font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 140)
        label.setFont(label_font)
        label.setStyleSheet("color: #64748b;")

        layout.addWidget(row)
        layout.addWidget(label)

        return group, card_tens, card_ones

    def set_12hour_mode(self, enabled):
        self.is_12hour = enabled
        self.settings.setValue("is_12hour", enabled)
        
        # Reset transition history to trigger a snap recalculation
        self.prev_digits = {k: None for k in self.prev_digits}
        self.update_clock()

    def update_clock(self):
        now = datetime.datetime.now()
        hours = now.hour
        minutes = now.minute
        seconds = now.second

        period = ""
        if self.is_12hour:
            period = "PM" if hours >= 12 else "AM"
            hours = hours % 12
            if hours == 0:
                hours = 12

        h_str = f"{hours:02d}"
        m_str = f"{minutes:02d}"
        s_str = f"{seconds:02d}"

        # We only animate digit transitions after the app has fully loaded
        animate = self.prev_digits["h_tens"] is not None

        # Apply digit changes
        self.h_tens.set_digit(h_str[0], animate)
        self.h_ones.set_digit(h_str[1], animate)
        self.m_tens.set_digit(m_str[0], animate)
        self.m_ones.set_digit(m_str[1], animate)
        self.s_tens.set_digit(s_str[0], animate)
        self.s_ones.set_digit(s_str[1], animate)

        # Store states
        self.prev_digits = {
            "h_tens": h_str[0], "h_ones": h_str[1],
            "m_tens": m_str[0], "m_ones": m_str[1],
            "s_tens": s_str[0], "s_ones": s_str[1]
        }

        # AM/PM visibility
        self.ampm_badge.set_ampm(period, self.is_12hour)

        # Update Date Label
        self.date_label.setText(now.strftime("%a, %d %b %Y").upper())

        # Update Timezone Info
        tz_now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        tz_name = tz_now.tzname() or ""
        offset = tz_now.utcoffset()
        offset_seconds = offset.total_seconds() if offset else 0
        sign = "+" if offset_seconds >= 0 else "-"
        abs_seconds = int(abs(offset_seconds))
        tz_h = abs_seconds // 3600
        tz_m = (abs_seconds % 3600) // 60
        self.tz_label.setText(f"{tz_name}  UTC{sign}{tz_h:02d}:{tz_m:02d}")

    def paintEvent(self, event):
        """Draw gorgeous slate background gradient and subtle ambient radial glow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W = self.width()
        H = self.height()

        # Vignette Linear-Radial gradient
        bg_gradient = QRadialGradient(W / 2.0, H / 2.0, max(W, H) * 0.7)
        bg_gradient.setColorAt(0, QColor("#111827"))  # Dark slate gray
        bg_gradient.setColorAt(1, QColor("#0a0e17"))  # Deep midnight
        painter.fillRect(0, 0, W, H, QBrush(bg_gradient))

        # Core ambient radial glow centered behind layout
        ambient_glow = QRadialGradient(W / 2.0, H / 2.0, min(W, H) * 0.6)
        ambient_glow.setColorAt(0, QColor(245, 158, 11, 14))      # 5.5% Amber
        ambient_glow.setColorAt(0.35, QColor(56, 189, 248, 7))    # 2.7% Sky blue
        ambient_glow.setColorAt(1, QColor(0, 0, 0, 0))            # Transparent
        painter.fillRect(0, 0, W, H, QBrush(ambient_glow))

    def closeEvent(self, event):
        # Clean up sleep locks
        allow_sleep()
        super().closeEvent(event)


# --- Entry Point ---
def main():
    # Setup App
    app = QApplication(sys.argv)
    
    # Launch main window
    win = FlipClockMainWindow()
    win.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
