"""
Qt binding compatibility shim.

Krita switched from PyQt5 to PyQt6 starting with Krita 5.2. Import
everything this plugin needs through this module instead of importing
PyQt5/PyQt6 directly, so the same code runs on both old and new Krita
installs.
"""

try:
    import PyQt6  # noqa: F401
    IS_QT6 = True
except ImportError:
    IS_QT6 = False

if IS_QT6:
    from PyQt6.QtWidgets import (
        QFileDialog, QMessageBox, QProgressDialog, QPushButton,
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
        QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit,
        QDialogButtonBox, QLabel, QTabWidget, QWidget,
    )
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import QObject, pyqtSignal, QThread, QSettings
else:
    from PyQt5.QtWidgets import (
        QFileDialog, QMessageBox, QProgressDialog, QPushButton,
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
        QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit,
        QDialogButtonBox, QLabel, QTabWidget, QWidget,
    )
    from PyQt5.QtGui import QImage
    from PyQt5.QtCore import QObject, pyqtSignal, QThread, QSettings

# Scoped enum access (QImage.Format.Format_ARGB32, QMessageBox.StandardButton.Cancel,
# etc.) works identically on PyQt5 (5.11+) and PyQt6, so no shimming needed there —
# just use the scoped form everywhere and it works on both bindings.
