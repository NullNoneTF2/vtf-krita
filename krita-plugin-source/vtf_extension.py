import os
import traceback

from krita import Extension, Krita
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtGui import QImage
from PyQt5.QtCore import QObject, pyqtSignal, QThread

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

        animated_action = window.createAction(
            "vtf_create_animated", "Create Animated VTF from Frames...", "file")
        animated_action.triggered.connect(self.create_animated_from_frames)

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

        # Run the export in a background thread and show progress.
        class ExportWorker(QObject):
            finished = pyqtSignal()
            error = pyqtSignal(str)

            def __init__(self, path, width, height, rgba_bytes, options, vmt_options):
                super().__init__()
                self.path = path
                self.width = width
                self.height = height
                self.rgba_bytes = rgba_bytes
                self.options = options
                self.vmt_options = vmt_options

            def run(self):
                try:
                    vtf.write_vtf(self.path, self.width, self.height, self.rgba_bytes, self.options)
                    if self.vmt_options:
                        vmt_path = os.path.splitext(self.path)[0] + ".vmt"
                        vtf.write_vmt(vmt_path, self.vmt_options["basetexture"], shader=self.vmt_options["shader"], extra_params=self.vmt_options["extra_params"])
                    self.finished.emit()
                except Exception as e:
                    self.error.emit(str(e) + "\n\n" + traceback.format_exc())

        try:
            width = doc.width()
            height = doc.height()

            root = doc.rootNode()
            alpha_mask_layer = None
            alpha_mask_was_visible = None
            for node in root.childNodes():
                try:
                    if node.name() == "Alpha Mask":
                        alpha_mask_layer = node
                        break
                except Exception:
                    continue

            if alpha_mask_layer and hasattr(alpha_mask_layer, "setVisible"):
                try:
                    if hasattr(alpha_mask_layer, "isVisible"):
                        alpha_mask_was_visible = alpha_mask_layer.isVisible()
                    alpha_mask_layer.setVisible(False)
                except Exception:
                    alpha_mask_layer = None

            doc.flatten()
            pixel_data = doc.pixelData(0, 0, width, height)

            qimg = QImage(pixel_data, width, height, QImage.Format_ARGB32)
            qimg = qimg.convertToFormat(QImage.Format_RGBA8888)
            ptr = qimg.bits()
            ptr.setsize(width * height * 4)
            rgba_bytes = bytearray(ptr)

            if alpha_mask_layer:
                try:
                    mask_data = alpha_mask_layer.pixelData(0, 0, width, height)
                    if mask_data:
                        mask_bytes = bytearray(mask_data)
                        if len(mask_bytes) >= width * height * 4:
                            for i in range(width * height):
                                rgba_bytes[i * 4 + 3] = mask_bytes[i * 4]
                except Exception:
                    pass
                finally:
                    try:
                        if alpha_mask_was_visible is not None:
                            alpha_mask_layer.setVisible(alpha_mask_was_visible)
                    except Exception:
                        pass
            rgba_bytes = bytes(rgba_bytes)

            worker = ExportWorker(path, width, height, rgba_bytes, options, vmt_options)
            thread = QThread()
            worker.moveToThread(thread)

            from PyQt5.QtWidgets import QProgressDialog
            progress = QProgressDialog("Exporting VTF...", "Cancel", 0, 0)
            progress.setWindowTitle("Export as VTF")
            progress.setModal(True)
            progress.setMinimumDuration(0)

            thread.started.connect(worker.run)
            worker.finished.connect(lambda: (progress.close(), QMessageBox.information(None, "Export as VTF", f"Exported to:\n{path}"), thread.quit()))
            worker.finished.connect(worker.deleteLater)
            worker.error.connect(lambda msg: (progress.close(), QMessageBox.critical(None, "Export as VTF", f"Export failed:\n{msg}"), thread.quit()))
            worker.error.connect(worker.deleteLater)
            progress.canceled.connect(lambda: QMessageBox.information(None, "Export as VTF", "Cancel requested — export will stop when possible."))

            thread.start()
            progress.exec_()
            thread.wait()
        except Exception as e:
            QMessageBox.critical(None, "Export as VTF", "Export failed:\n{}\n\n{}".format(e, traceback.format_exc()))

    # ------------------------------------------------------------------
    def import_vtf(self):
        path, _ = QFileDialog.getOpenFileName(
            None, "Import VTF", "", "Valve Texture Format (*.vtf)")
        if not path:
            return

        try:
            info = vtf.read_vtf(path)
            # If the VTF contains multiple frames, offer the user a choice
            # to import a single frame or export all frames individually.
            if info.get("frame_count", 1) > 1:
                msg = QMessageBox()
                msg.setWindowTitle("Animated VTF")
                msg.setText("This VTF contains multiple frames. What would you like to do?")
                edit_btn = msg.addButton("Edit single frame", QMessageBox.AcceptRole)
                export_btn = msg.addButton("Export all frames to folder", QMessageBox.ActionRole)
                cancel_btn = msg.addButton(QMessageBox.Cancel)
                msg.exec_()
                clicked = msg.clickedButton()
                if clicked == export_btn:
                    target = QFileDialog.getExistingDirectory(None, "Select output folder for frames")
                    if not target:
                        return
                    frames = info.get("frames") or []
                    for i, frame_bytes in enumerate(frames):
                        qimg = QImage(frame_bytes, info["width"], info["height"], QImage.Format_RGBA8888)
                        png_path = os.path.join(target, f"frame_{i:04d}.png")
                        qimg.save(png_path)
                    QMessageBox.information(None, "Import VTF", f"Exported {len(frames)} frames to {target}")
                    return
                # otherwise continue and import frame 0
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

            rgba = info["rgba"]
            # Detect if there is any non-opaque alpha channel data
            has_alpha = any(a != 255 for a in rgba[3::4])

            # Prepare color bytes (force alpha to opaque so Krita doesn't
            # use it as transparency) and a separate grayscale alpha image.
            color_buf = bytearray(rgba)
            alpha_buf = bytearray(len(rgba) // 4)
            for i in range(0, len(rgba), 4):
                a = rgba[i + 3]
                alpha_buf[i // 4] = a
                color_buf[i + 3] = 255

            qimg = QImage(bytes(color_buf), info["width"], info["height"], QImage.Format_RGBA8888)
            qimg = qimg.convertToFormat(QImage.Format_ARGB32)
            ptr = qimg.bits()
            ptr.setsize(info["width"] * info["height"] * 4)
            layer.setPixelData(bytes(ptr), 0, 0, info["width"], info["height"])

            # If alpha existed, create a bound mask if possible; otherwise
            # create a separate "Alpha Mask" paint layer above the color.
            if has_alpha:
                try:
                    # Try to create an actual transparency mask bound to the layer.
                    if hasattr(layer, "createTransparencyMask"):
                        mask = layer.createTransparencyMask()
                        # mask expects RGBA as well; make grayscale -> RGBA
                        mask_rgba = bytearray(len(rgba))
                        for i in range(info["width"] * info["height"]):
                            v = alpha_buf[i]
                            base = i * 4
                            mask_rgba[base:base+4] = bytes((v, v, v, 255))
                        mq = QImage(bytes(mask_rgba), info["width"], info["height"], QImage.Format_RGBA8888)
                        mq = mq.convertToFormat(QImage.Format_ARGB32)
                        mp = mq.bits()
                        mp.setsize(info["width"] * info["height"] * 4)
                        mask.setPixelData(bytes(mp), 0, 0, info["width"], info["height"])
                        layer.addMask(mask)
                    else:
                        raise AttributeError
                except Exception:
                    # Fallback: create a visible grayscale layer named "Alpha Mask"
                    mask_layer = doc.createNode("Alpha Mask", "paintlayer")
                    root.addChildNode(mask_layer, layer)
                    # build ARGB image for mask (RGB=alpha, A=255)
                    mask_rgba = bytearray(info["width"] * info["height"] * 4)
                    for i in range(info["width"] * info["height"]):
                        v = alpha_buf[i]
                        base = i * 4
                        mask_rgba[base] = v
                        mask_rgba[base+1] = v
                        mask_rgba[base+2] = v
                        mask_rgba[base+3] = 255
                    mq = QImage(bytes(mask_rgba), info["width"], info["height"], QImage.Format_RGBA8888)
                    mq = mq.convertToFormat(QImage.Format_ARGB32)
                    mp = mq.bits()
                    mp.setsize(info["width"] * info["height"] * 4)
                    mask_layer.setPixelData(bytes(mp), 0, 0, info["width"], info["height"])
            doc.refreshProjection()
        except Exception as e:
            QMessageBox.critical(
                None, "Import VTF",
                "Import failed:\n{}\n\n{}".format(e, traceback.format_exc()))

    # ------------------------------------------------------------------
    def create_animated_from_frames(self):
        folder = QFileDialog.getExistingDirectory(None, "Select frames folder")
        if not folder:
            return

        # Collect image files (sorted)
        exts = ('.png', '.jpg', '.jpeg', '.tga', '.bmp')
        files = sorted([os.path.join(folder, f) for f in os.listdir(folder)
                        if f.lower().endswith(exts)])
        if not files:
            QMessageBox.warning(None, "Create Animated VTF", "No image files found in folder")
            return

        frames = []
        width = height = None
        for p in files:
            img = QImage(p)
            if img.isNull():
                continue
            if width is None:
                width, height = img.width(), img.height()
            elif img.width() != width or img.height() != height:
                QMessageBox.critical(None, "Create Animated VTF",
                                     "All frames must have identical dimensions")
                return
            q = img.convertToFormat(QImage.Format_RGBA8888)
            bits = q.bits()
            bits.setsize(width * height * 4)
            frames.append(bytes(bits))

        # Ask for output VTF path and options
        dialog = VTFExportDialog(default_name=os.path.basename(folder))
        if not dialog.exec_():
            return
        options, vmt_options = dialog.get_options()

        path, _ = QFileDialog.getSaveFileName(None, "Export Animated VTF",
                                              os.path.join(folder, os.path.basename(folder) + ".vtf"),
                                              "Valve Texture Format (*.vtf)")
        if not path:
            return
        if not path.lower().endswith('.vtf'):
            path += '.vtf'

        # Run animated export in a background thread and show determinate progress.
        class AnimatedWorker(QObject):
            progress = pyqtSignal(int)
            finished = pyqtSignal()
            error = pyqtSignal(str)

            def __init__(self, path, width, height, frames, options):
                super().__init__()
                self.path = path
                self.width = width
                self.height = height
                self.frames = frames
                self.options = options
                self._abort = False

            def run(self):
                try:
                    def cb(done, total):
                        # cb returns True to continue, False to abort
                        pct = int(done / total * 100) if total else 0
                        self.progress.emit(pct)
                        return not self._abort

                    vtf.write_vtf_multiple(self.path, self.width, self.height, self.frames, self.options, progress_callback=cb)
                    self.finished.emit()
                except Exception as e:
                    self.error.emit(str(e) + "\n\n" + traceback.format_exc())

            def abort(self):
                self._abort = True

        try:
            worker = AnimatedWorker(path, width, height, frames, options)
            thread = QThread()
            worker.moveToThread(thread)

            from PyQt5.QtWidgets import QProgressDialog
            progress = QProgressDialog("Creating animated VTF...", "Cancel", 0, 100)
            progress.setWindowTitle("Create Animated VTF")
            progress.setModal(True)
            progress.setMinimumDuration(0)

            worker.progress.connect(progress.setValue)
            worker.finished.connect(lambda: (progress.close(), QMessageBox.information(None, "Create Animated VTF", f"Animated VTF written to:\n{path}"), thread.quit()))
            worker.finished.connect(worker.deleteLater)
            worker.error.connect(lambda msg: (progress.close(), QMessageBox.critical(None, "Create Animated VTF", f"Creation failed:\n{msg}"), thread.quit()))
            worker.error.connect(worker.deleteLater)

            progress.canceled.connect(worker.abort)

            thread.started.connect(worker.run)
            thread.start()
            progress.exec_()
            thread.wait()
        except Exception as e:
            QMessageBox.critical(None, "Create Animated VTF", "Creation failed:\n{}\n\n{}".format(e, traceback.format_exc()))
