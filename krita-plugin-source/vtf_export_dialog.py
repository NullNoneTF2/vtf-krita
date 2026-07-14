from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QComboBox,
    QCheckBox, QDoubleSpinBox, QSpinBox, QLineEdit, QPlainTextEdit,
    QDialogButtonBox, QLabel, QTabWidget, QWidget,
)
from PyQt5.QtCore import QSettings

from . import vtf_bindings as vtf


class VTFExportDialog(QDialog):
    def __init__(self, parent=None, default_name="texture"):
        super().__init__(parent)
        self.setWindowTitle("Export as VTF")
        self.setMinimumWidth(420)
        self._build_ui(default_name)

    def _build_ui(self, default_name):
        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        layout.addWidget(tabs)

        # Load persistent settings
        self._settings = QSettings("VTFKrita", "vtf_plugin")

        # ---------------- Basic tab -----------------------------------
        basic = QWidget()
        form = QFormLayout(basic)

        self.format_combo = QComboBox()
        # Start with a compact, user-friendly list; allow expanding to
        # the full list via the 'Full Options' checkbox below.
        self.format_combo.addItems(vtf.EXPORTABLE_FORMATS_CORE)
        self.format_combo.setCurrentText(self._settings.value("format", "DXT5"))
        form.addRow("Format:", self.format_combo)

        self.full_options_check = QCheckBox("Full Options (show advanced formats)")
        self.full_options_check.setChecked(self._settings.value("full_options", False, type=bool))
        def _toggle_formats(checked):
            cur = self.format_combo.currentText()
            self.format_combo.clear()
            if checked:
                self.format_combo.addItems(vtf.EXPORTABLE_FORMATS_FULL)
            else:
                self.format_combo.addItems(vtf.EXPORTABLE_FORMATS_CORE)
            # restore selection if present
            if cur in [self.format_combo.itemText(i) for i in range(self.format_combo.count())]:
                self.format_combo.setCurrentText(cur)
        self.full_options_check.stateChanged.connect(lambda s: _toggle_formats(bool(s)))
        # initialize formats list based on saved preference
        _toggle_formats(self.full_options_check.isChecked())
        form.addRow(self.full_options_check)

        self.version_combo = QComboBox()
        self.version_combo.addItems(vtf.VTF_VERSIONS)
        self.version_combo.setCurrentText(self._settings.value("version", "7.4"))
        form.addRow("VTF version:", self.version_combo)

        self.mipmaps_check = QCheckBox("Generate mipmaps")
        self.mipmaps_check.setChecked(self._settings.value("generate_mipmaps", True, type=bool))
        form.addRow(self.mipmaps_check)

        self.mip_filter_combo = QComboBox()
        self.mip_filter_combo.addItems(sorted(vtf.MIPMAP_FILTER,
                                               key=lambda k: vtf.MIPMAP_FILTER[k]))
        self.mip_filter_combo.setCurrentText("TRIANGLE")
        form.addRow("Mipmap filter:", self.mip_filter_combo)

        self.thumbnail_check = QCheckBox("Generate thumbnail")
        self.thumbnail_check.setChecked(self._settings.value("generate_thumbnail", True, type=bool))
        form.addRow(self.thumbnail_check)

        tabs.addTab(basic, "Basic")

        # ---------------- Resize tab -------------------------------------
        resize_tab = QWidget()
        rform = QFormLayout(resize_tab)
        self.resize_method_combo = QComboBox()
        self.resize_method_combo.addItems(
            ["NONE", "NEAREST_POWER2", "BIGGEST_POWER2", "SMALLEST_POWER2", "SET"])
        rform.addRow("Resize method:", self.resize_method_combo)
        note = QLabel(
            "Note: VTF textures must be power-of-two sized. If your canvas "
            "isn't already, it will be resized to the nearest power of two "
            "automatically even if you leave this as NONE."
        )
        note.setWordWrap(True)
        rform.addRow(note)
        self.resize_w_spin = QSpinBox()
        self.resize_w_spin.setRange(1, 8192)
        self.resize_w_spin.setValue(512)
        self.resize_h_spin = QSpinBox()
        self.resize_h_spin.setRange(1, 8192)
        self.resize_h_spin.setValue(512)
        rform.addRow("Set width:", self.resize_w_spin)
        rform.addRow("Set height:", self.resize_h_spin)
        tabs.addTab(resize_tab, "Resize")

        # ---------------- Normal map tab ----------------------------------
        nm_tab = QWidget()
        nform = QFormLayout(nm_tab)
        self.normalmap_check = QCheckBox("Convert to normal map")
        nform.addRow(self.normalmap_check)
        self.nm_height_combo = QComboBox()
        self.nm_height_combo.addItems(sorted(
            vtf.HEIGHT_CONVERSION_METHOD,
            key=lambda k: vtf.HEIGHT_CONVERSION_METHOD[k]))
        self.nm_height_combo.setCurrentText("AVERAGE_RGB")
        nform.addRow("Height source:", self.nm_height_combo)
        self.nm_scale_spin = QDoubleSpinBox()
        self.nm_scale_spin.setRange(0.01, 32.0)
        self.nm_scale_spin.setValue(2.0)
        nform.addRow("Scale:", self.nm_scale_spin)
        self.nm_wrap_check = QCheckBox("Wrap at edges")
        nform.addRow(self.nm_wrap_check)
        self.nm_invert_x_check = QCheckBox("Invert X")
        nform.addRow(self.nm_invert_x_check)
        self.nm_invert_y_check = QCheckBox("Invert Y")
        nform.addRow(self.nm_invert_y_check)
        self.nm_alpha_combo = QComboBox()
        self.nm_alpha_combo.addItems(sorted(
            vtf.NORMAL_ALPHA_RESULT, key=lambda k: vtf.NORMAL_ALPHA_RESULT[k]))
        nform.addRow("Alpha channel:", self.nm_alpha_combo)
        tabs.addTab(nm_tab, "Normal map")

        # ---------------- Flags tab --------------------------------------
        flags_tab = QWidget()
        fform = QVBoxLayout(flags_tab)
        self.flag_checks = {}
        common_flags = [
            "CLAMPS", "CLAMPT", "CLAMPU", "NOMIP", "NOLOD", "POINTSAMPLE",
            "TRILINEAR", "ANISOTROPIC", "NORMAL", "SSBUMP", "PROCEDURAL",
            "RENDERTARGET", "NODEBUGOVERRIDE", "BORDER",
        ]
        for name in common_flags:
            cb = QCheckBox(name)
            self.flag_checks[name] = cb
            fform.addWidget(cb)
        fform.addStretch(1)
        tabs.addTab(flags_tab, "Flags")

        # ---------------- VMT tab ------------------------------------------
        vmt_tab = QWidget()
        vform = QFormLayout(vmt_tab)
        self.vmt_check = QCheckBox("Also write a .vmt material file")
        vform.addRow(self.vmt_check)
        self.vmt_shader_edit = QLineEdit("LightmappedGeneric")
        vform.addRow("Shader:", self.vmt_shader_edit)
        self.vmt_basetexture_edit = QLineEdit(default_name)
        vform.addRow("$basetexture path:", self.vmt_basetexture_edit)
        self.vmt_extra_edit = QPlainTextEdit()
        self.vmt_extra_edit.setPlaceholderText(
            '$surfaceprop metal\n$translucent 1\n(one "$key value" per line -- '
            "this is a basic starting point, expected to be hand-tuned "
            "afterwards, same as VTFEdit Reloaded's VMT generation)"
        )
        vform.addRow("Extra parameters:", self.vmt_extra_edit)
        tabs.addTab(vmt_tab, "VMT")

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        # Add a small action row: Use Defaults and the OK/Cancel buttons.
        action_row = QHBoxLayout()
        self.use_defaults_btn = QLabel()
        from PyQt5.QtWidgets import QPushButton
        use_defaults = QPushButton("Use Defaults")
        use_defaults.clicked.connect(self._use_defaults)
        action_row.addWidget(use_defaults)
        action_row.addStretch(1)
        layout.addLayout(action_row)
        layout.addWidget(buttons)

        # Connect UI changes to automatic saving of options
        widgets_to_watch = [
            self.format_combo, self.version_combo, self.mipmaps_check,
            self.mip_filter_combo, self.thumbnail_check, self.full_options_check,
        ]
        for w in widgets_to_watch:
            if hasattr(w, 'currentTextChanged'):
                w.currentTextChanged.connect(lambda _t, w=w: self._save_settings())
            if hasattr(w, 'stateChanged'):
                w.stateChanged.connect(lambda _s, w=w: self._save_settings())
        # spinboxes
        for w in (self.resize_w_spin, self.resize_h_spin, self.nm_scale_spin):
            w.valueChanged.connect(lambda _v, w=w: self._save_settings())

        # Ensure initial save of any missing defaults
        self._save_settings()

    def get_options(self):
        """Returns (vtf_write_options: dict, vmt_options: dict or None)"""
        opts = {
            "format": self.format_combo.currentText(),
            "version": self.version_combo.currentText(),
            "generate_mipmaps": self.mipmaps_check.isChecked(),
            "mipmap_filter": self.mip_filter_combo.currentText(),
            "generate_thumbnail": self.thumbnail_check.isChecked(),
            "flags": [name for name, cb in self.flag_checks.items()
                      if cb.isChecked()],
        }

        method = self.resize_method_combo.currentText()
        if method == "NONE":
            opts["resize"] = None
        else:
            opts["resize"] = {"method": method}
            if method == "SET":
                opts["resize"]["width"] = self.resize_w_spin.value()
                opts["resize"]["height"] = self.resize_h_spin.value()

        if self.normalmap_check.isChecked():
            opts["normal_map"] = {
                "height_method": self.nm_height_combo.currentText(),
                "scale": self.nm_scale_spin.value(),
                "wrap": self.nm_wrap_check.isChecked(),
                "invert_x": self.nm_invert_x_check.isChecked(),
                "invert_y": self.nm_invert_y_check.isChecked(),
                "alpha_result": self.nm_alpha_combo.currentText(),
            }
        else:
            opts["normal_map"] = None

        vmt_opts = None
        if self.vmt_check.isChecked():
            extra = {}
            for line in self.vmt_extra_edit.toPlainText().splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(None, 1)
                if len(parts) == 2:
                    extra[parts[0]] = parts[1]
            vmt_opts = {
                "shader": self.vmt_shader_edit.text().strip() or "LightmappedGeneric",
                "basetexture": self.vmt_basetexture_edit.text().strip(),
                "extra_params": extra,
            }

        return opts, vmt_opts

    def _save_settings(self):
        try:
            self._settings.setValue("format", self.format_combo.currentText())
            self._settings.setValue("version", self.version_combo.currentText())
            self._settings.setValue("generate_mipmaps", self.mipmaps_check.isChecked())
            self._settings.setValue("mipmap_filter", self.mip_filter_combo.currentText())
            self._settings.setValue("generate_thumbnail", self.thumbnail_check.isChecked())
            self._settings.setValue("full_options", self.full_options_check.isChecked())
            self._settings.sync()
        except Exception:
            pass

    def _use_defaults(self):
        # Reset the dialog to the reasonable defaults used by the writer.
        self.format_combo.setCurrentText("DXT5")
        self.version_combo.setCurrentText("7.4")
        self.mipmaps_check.setChecked(True)
        self.mip_filter_combo.setCurrentText("TRIANGLE")
        self.thumbnail_check.setChecked(True)
        self.full_options_check.setChecked(False)
        self._save_settings()
