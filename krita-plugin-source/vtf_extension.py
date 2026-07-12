import os
import traceback

from krita import Extension, Krita
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import QImage

from . import vtf_bindings as vtf
from .vtf_export_dialog import VTFExportDialog


class VTFExtension(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def createActions(self, window):
        export_action = window.createAction(
            "vtf_export", "Export as VTF...", "file")
        export_action.triggered.connect(self.export_vtf)

        import_action = window.createAction(
            "vtf_import", "Import VTF...", "file")
        import_action.triggered.connect(self.import_vtf)

    # ------------------------------------------------------------------
    def export_vtf(self):
        app = Krita.instance()
        doc = app.activeDocument()
        if doc is None:
            QMessageBox.warning(None, "Export as VTF",
                                 "No document is open.")
            return

        default_name = os.path.splitext(
            os.path.basename(doc.fileName() or "texture"))[0] or "texture"

        dialog = VTFExportDialog(default_name=default_name)
        if not dialog.exec_():
            return
        options, vmt_options = dialog.get_options()

        path, _ = QFileDialog.getSaveFileName(
            None, "Export as VTF",
            os.path.join(os.path.dirname(doc.fileName() or ""),
                         default_name + ".vtf"),
            "Valve Texture Format (*.vtf)")
        if not path:
            return
        if not path.lower().endswith(".vtf"):
            path += ".vtf"

        try:
            width = doc.width()
            height = doc.height()

            # Flatten and grab pixel data. Krita hands back pixel data as
            # tightly packed bytes in the document's colour model/depth;
            # projectionPixelData() on a flattened image in 8-bit RGBA is
            # the simplest reliable path to plain RGBA8888 bytes.
            doc.flatten()
            pixel_data = doc.pixelData(0, 0, width, height)

            qimg = QImage(pixel_data, width, height, QImage.Format_ARGB32)
            qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
            ptr = qimg.bits()
            ptr.setsize(width * height * 4)
            rgba_bytes = bytes(ptr)

            vtf.write_vtf(path, width, height, rgba_bytes, options)

            if vmt_options:
                vmt_path = os.path.splitext(path)[0] + ".vmt"
                vtf.write_vmt(
                    vmt_path,
                    vmt_options["basetexture"],
                    shader=vmt_options["shader"],
                    extra_params=vmt_options["extra_params"],
                )

            QMessageBox.information(None, "Export as VTF",
                                     "Exported to:\n{}".format(path))
        except Exception as e:
            QMessageBox.critical(
                None, "Export as VTF",
                "Export failed:\n{}\n\n{}".format(e, traceback.format_exc()))

    # ------------------------------------------------------------------
    def import_vtf(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Import VTF", "", "Valve Texture Format (*.vtf)")
        if not path:
            return

        try:
            info = vtf.read_vtf(path)
            app = Krita.instance()
            doc = app.createDocument(
                info["width"], info["height"],
                os.path.basename(path), "RGBA", "U8", "", 1.0)
            app.activeWindow().addView(doc)

            root = doc.rootNode()
            layer = root.childNodes()[0] if root.childNodes() else \
                doc.createNode("Imported VTF", "paintlayer")
            if not root.childNodes():
                root.addChildNode(layer, None)

            qimg = QImage(info["rgba"], info["width"], info["height"],
                          QImage.Format_RGBA8888)
            qimg = qimg.convertToFormat(QImage.Format_ARGB32)
            ptr = qimg.bits()
            ptr.setsize(info["width"] * info["height"] * 4)
            layer.setPixelData(bytes(ptr), 0, 0, info["width"],
                                info["height"])
            doc.refreshProjection()
        except Exception as e:
            QMessageBox.critical(
                None, "Import VTF",
                "Import failed:\n{}\n\n{}".format(e, traceback.format_exc()))
