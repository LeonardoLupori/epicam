import sys
import os
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QSlider, QWidget, 
    QHBoxLayout, QComboBox, QProxyStyle
)
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPixmap, QImage, QClipboard, QPainter
import PySpin

class ProxyStyle(QProxyStyle):
    def styleHint(self, hint, opt=None, widget=None, returnData=None):
        res = super().styleHint(hint, opt, widget, returnData)
        if hint == self.SH_Slider_AbsoluteSetButtons:
            res |= Qt.LeftButton
        return res

class CameraApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Surgery camera acquisition")
        self.setGeometry(100, 100, 1200, 950)
        self.setFixedSize(1200, 900)
        self.px_per_mm = 107
        self.has_camera = False

        # Default values for when no camera is available
        self.min_exposure = 1000    # 1ms
        self.max_exposure = 100000  # 100ms
        self.min_gain = 0
        self.max_gain = 47

        # Initialize PySpin system
        self.system = PySpin.System.GetInstance()
        self.cam_list = self.system.GetCameras()
        self.camera = None
        
        # Try to initialize camera
        if self.cam_list.GetSize() > 0:
            try:
                self.camera = self.cam_list[0]
                self.camera.Init()
                self.set_camera_framerate(10)
                self.has_camera = True
                self.cache_exposure_range()
                self.cache_gain_range()
            except Exception as e:
                print(f"Error initializing camera: {e}")
                self.has_camera = False
        
        # Set dark gray background but exclude buttons from the white text color
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2d2d2d;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #e0e0e0;
                color: black;
                border: 1px solid #888888;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #d0d0d0;
            }
            QPushButton:pressed {
                background-color: #c0c0c0;
            }
            QComboBox {
                background-color: #e0e0e0;
                color: black;
                border: 1px solid #888888;
                border-radius: 4px;
                padding: 4px 8px;
            }
        """)
        
        # Setup UI
        self.init_ui()

        # Only start preview if camera is available
        if self.has_camera:
            self.preview_active = True
            self.preview_thread = threading.Thread(target=self.start_preview, daemon=True)
            self.preview_thread.start()
            self.update_exposure()
            self.update_gain()
        else:
            self.display_no_camera_warning()
            # Disable controls
            self.disable_controls()

    def disable_controls(self):
        """Disable all camera-related controls when no camera is available"""
        self.exposure_slider.setEnabled(False)
        self.gain_slider.setEnabled(False)
        self.framerate_combo.setEnabled(False)
        for button in self.findChildren(QPushButton):
            button.setEnabled(False)

    def display_no_camera_warning(self):
        """Display warning message in the image display area"""
        warning_label = QLabel("⚠️ No valid camera handle found\nPlease check camera connection and restart the application")
        warning_label.setStyleSheet("""
            color: #ff4444;
            font-size: 24px;
            font-weight: bold;
            background-color: black;
            padding: 20px;
        """)
        warning_label.setAlignment(Qt.AlignCenter)
        self.image_label.setLayout(QVBoxLayout())
        self.image_label.layout().addWidget(warning_label)


    def init_ui(self):
        # Main layout
        central_widget = QWidget()
        layout = QVBoxLayout()

        # Fixed-size Image display
        self.image_label = QLabel()
        self.image_label.setFixedSize(int(2048/2), int(1536/2))  # Static size: slightly less than the window size
        self.image_label.setStyleSheet("background-color: black; border: 3px solid white;")
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Sliders and labels layout
        controls_layout = QVBoxLayout()

        # Exposure controls
        exposure_layout = QHBoxLayout()
        self.exposure_label = QLabel("Exposure: 1 ms")
        self.exposure_label.setStyleSheet("font-size: 16px;")
        self.exposure_slider = QSlider(Qt.Horizontal)
        self.exposure_slider.setRange(int(self.min_exposure), int(self.max_exposure))
        self.exposure_slider.setValue(85000)
        self.exposure_slider.valueChanged.connect(self.update_exposure)
        exposure_layout.addWidget(QLabel("Exposure"))
        exposure_layout.addWidget(self.exposure_slider)
        exposure_layout.addWidget(self.exposure_label)
        controls_layout.addLayout(exposure_layout)

        # Gain controls
        gain_layout = QHBoxLayout()
        self.gain_label = QLabel("Gain: 10 dB")
        self.gain_label.setStyleSheet("font-size: 16px;")
        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(int(self.min_gain), int(self.max_gain))
        self.gain_slider.setValue(32)
        self.gain_slider.valueChanged.connect(self.update_gain)
        gain_layout.addWidget(QLabel("Gain"))
        gain_layout.addWidget(self.gain_slider)
        gain_layout.addWidget(self.gain_label)
        controls_layout.addLayout(gain_layout)
        
        # Framerate and screenshot button layout
        framerate_layout = QHBoxLayout()
        
        # Framerate label and combo box
        framerate_section = QVBoxLayout()
        self.framerate_label = QLabel("Framerate: 10 Hz")
        self.framerate_label.setStyleSheet("font-size: 16px;")
        self.framerate_combo = QComboBox()
        self.framerate_combo.addItems(["10", "5", "1"])
        self.framerate_combo.currentIndexChanged.connect(self.update_framerate)
        self.framerate_combo.setFixedWidth(100)  # Small dedicated space for the combo box
        framerate_section.addWidget(self.framerate_label)
        framerate_section.addWidget(self.framerate_combo)
        framerate_layout.addLayout(framerate_section)

        # Spacer for spacing
        framerate_layout.addStretch()

        # Screenshot button
        to_clipboard = QPushButton("To Clipboard")
        to_clipboard.setStyleSheet("font-size: 16px; padding: 8px;")
        to_clipboard.clicked.connect(self.copy_to_clipboard)
        framerate_layout.addWidget(to_clipboard)

        rotate_to_clipboard = QPushButton("Rotate -> To Clipboard")
        rotate_to_clipboard.setStyleSheet("font-size: 16px; padding: 8px;")
        rotate_to_clipboard.clicked.connect(self.rotate_and_copy_to_clipboard)
        framerate_layout.addWidget(rotate_to_clipboard)
        
        # Add the framerate layout to controls
        controls_layout.addLayout(framerate_layout)

        # Add all controls to the main layout
        layout.addLayout(controls_layout)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def start_preview(self):
        try:
            nodemap = self.camera.GetNodeMap()
            self.camera.BeginAcquisition()
            while self.preview_active:
                image_result = self.camera.GetNextImage()
                if image_result.IsIncomplete():
                    continue
                frame = image_result.GetNDArray()
                height, width = frame.shape
                image_result.Release()

                # Convert frame to QImage
                image = QImage(frame.data, width, height, QImage.Format_Grayscale8)
                pixmap = QPixmap.fromImage(image)
                
                # Update the QLabel on the GUI thread
                self.image_label.setPixmap(pixmap.scaled(
                    self.image_label.width(),
                    self.image_label.height(),
                    Qt.KeepAspectRatio,
                ))
        except Exception as e:
            self.show_error(f"Error during preview: {e}")

    def cache_exposure_range(self):
        """Cache exposure range during initialization"""
        if not self.has_camera:
            return
        node_map = self.camera.GetNodeMap()
        exposure_node = PySpin.CFloatPtr(node_map.GetNode("ExposureTime"))
        if PySpin.IsAvailable(exposure_node) and PySpin.IsReadable(exposure_node):
            self.min_exposure = exposure_node.GetMin()
            self.max_exposure = exposure_node.GetMax()

    def cache_gain_range(self):
        """Cache gain range during initialization"""
        if not self.has_camera:
            return
        node_map = self.camera.GetNodeMap()
        gain_node = PySpin.CFloatPtr(node_map.GetNode("Gain"))
        if PySpin.IsAvailable(gain_node) and PySpin.IsReadable(gain_node):
            self.min_gain = gain_node.GetMin()
            self.max_gain = gain_node.GetMax()

    def update_exposure(self):
        if self.camera:
            try:
                # Disable auto exposure
                node_map = self.camera.GetNodeMap()
                exposure_auto = PySpin.CEnumerationPtr(node_map.GetNode("ExposureAuto"))
                if PySpin.IsAvailable(exposure_auto) and PySpin.IsWritable(exposure_auto):
                    exposure_auto_off = exposure_auto.GetEntryByName("Off")
                    if PySpin.IsAvailable(exposure_auto_off) and PySpin.IsReadable(exposure_auto_off):
                        exposure_auto.SetIntValue(exposure_auto_off.GetValue())

                # Set manual exposure time
                exposure_node = PySpin.CFloatPtr(node_map.GetNode("ExposureTime"))
                if PySpin.IsAvailable(exposure_node) and PySpin.IsWritable(exposure_node):
                    slider_value = self.exposure_slider.value()                    
                    # Update the exposure time
                    exposure_node.SetValue(slider_value)
                    actual_exposure = exposure_node.GetValue()
                    self.exposure_label.setText(f"Exposure: {actual_exposure/1000:.2f} ms")
                else:
                    self.show_error("Exposure setting is not writable.")
            except Exception as e:
                self.show_error(f"Error updating exposure: {e}")

    def update_framerate(self):
        # Get the selected framerate from the dropdown and update the camera settings
        framerate = int(self.framerate_combo.currentText())
        self.set_camera_framerate(framerate)
        
        self.cache_exposure_range()
        self.exposure_slider.setRange(int(self.min_exposure), int(self.max_exposure))

        self.framerate_label.setText(f"Framerate: {framerate} Hz")

    def set_camera_framerate(self, framerate):
        try:
            node_map = self.camera.GetNodeMap()

            # Disable auto Framerate
            node_map = self.camera.GetNodeMap()
            framerate_auto = PySpin.CEnumerationPtr(node_map.GetNode("AcquisitionFrameRateAuto"))
            if PySpin.IsAvailable(framerate_auto) and PySpin.IsWritable(framerate_auto):
                exposure_auto_off = framerate_auto.GetEntryByName("Off")
                if PySpin.IsAvailable(exposure_auto_off) and PySpin.IsReadable(exposure_auto_off):
                    framerate_auto.SetIntValue(exposure_auto_off.GetValue())

            # Access the AcquisitionFrameRate node
            frame_rate_node = PySpin.CFloatPtr(node_map.GetNode("AcquisitionFrameRate"))
            if PySpin.IsAvailable(frame_rate_node) and PySpin.IsWritable(frame_rate_node):
                # Set the frame rate to 10 FPS
                frame_rate_node.SetValue(framerate)
            else:
                self.show_error("Frame rate setting is not writable or not available.")
        except Exception as e:
            self.show_error(f"Error setting frame rate: {e}")


    def update_gain(self):
        if self.camera:
            try:
                # Access the node map
                node_map = self.camera.GetNodeMap()

                # Disable Auto Gain
                gain_auto = PySpin.CEnumerationPtr(node_map.GetNode("GainAuto"))
                if PySpin.IsAvailable(gain_auto) and PySpin.IsWritable(gain_auto):
                    gain_auto_off = gain_auto.GetEntryByName("Off")
                    if PySpin.IsAvailable(gain_auto_off) and PySpin.IsReadable(gain_auto_off):
                        gain_auto.SetIntValue(gain_auto_off.GetValue())

                # Access the Gain node
                gain_node = PySpin.CFloatPtr(node_map.GetNode("Gain"))
                if PySpin.IsAvailable(gain_node) and PySpin.IsWritable(gain_node):
                    slider_value = self.gain_slider.value()  # Slider value (0 to 100)
                    # Update the gain value
                    gain_node.SetValue(slider_value)
                    actual_gain = gain_node.GetValue()
                    self.gain_label.setText(f"Gain: {actual_gain:.2f} dB")
                else:
                    self.show_error("Gain setting is not writable.")
            except Exception as e:
                self.show_error(f"Error updating gain: {e}")

    def copy_to_clipboard(self):
        """Copy the current image displayed in the QLabel to the clipboard with framerate, gain, exposure, and a 1mm scale bar."""
        if not self.image_label.pixmap():
            self.show_error("No image to copy.")
            return

        # Get the current pixmap
        pixmap = self.image_label.pixmap()

        # Ensure the pixmap is resized to 1024 x 768
        fixed_size_pixmap = pixmap.scaled(1024, 768, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Convert to QImage
        image = fixed_size_pixmap.toImage()

        # Start a QPainter to draw text and graphics on the image
        painter = QPainter(image)

        # Set font to bold and larger size for metadata text
        font = painter.font()
        font.setBold(True)
        font.setPointSize(14)  # Larger font size
        painter.setFont(font)

        # Set text color to cyan
        painter.setPen(Qt.cyan)

        # Retrieve the current framerate, gain, and exposure
        framerate = self.framerate_combo.currentText()
        gain = self.gain_label.text()
        exp_time = self.exposure_label.text()

        # Construct the metadata text
        text = f"{gain}, {exp_time}"

        # Measure text size for the background rectangle
        text_rect = painter.boundingRect(10, 10, image.width(), image.height(), Qt.TextSingleLine, text)

        # Draw the background rectangle for metadata text
        painter.setBrush(Qt.darkGray)  # Dark gray background
        painter.setPen(Qt.NoPen)       # No border for the rectangle
        painter.drawRect(text_rect.adjusted(-10, -5, 10, 5))  # Add padding around the text

        # Draw the metadata text on top of the rectangle
        painter.setPen(Qt.cyan)  # Cyan text color
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop, text)

        # End painting
        painter.end()

        # Convert the QImage back to a QPixmap
        updated_pixmap = QPixmap.fromImage(image)

        # Copy the updated pixmap to the clipboard
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(updated_pixmap)


    def rotate_and_copy_to_clipboard(self):
        """Copy the current image to the clipboard after rotating it 180 degrees."""
        if not self.image_label.pixmap():
            self.show_error("No image to copy.")
            return

        # Get the current pixmap and rotate it
        pixmap = self.image_label.pixmap()
        rotated_pixmap = pixmap.transformed(QPixmap.fromImage(QImage()).transform().rotate(180))

        # Ensure the pixmap is resized to 1024 x 768
        fixed_size_pixmap = rotated_pixmap.scaled(1024, 768, Qt.KeepAspectRatio, Qt.SmoothTransformation)

        # Convert to QImage
        image = fixed_size_pixmap.toImage()

        # Start a QPainter to draw text and graphics on the image
        painter = QPainter(image)

        # Set font to bold and larger size for metadata text
        font = painter.font()
        font.setBold(True)
        font.setPointSize(14)  # Larger font size
        painter.setFont(font)

        # Set text color to cyan
        painter.setPen(Qt.cyan)

        # Retrieve the current framerate, gain, and exposure
        framerate = self.framerate_combo.currentText()
        gain = self.gain_label.text()
        exp_time = self.exposure_label.text()

        # Construct the metadata text
        text = f"{gain}, {exp_time}"

        # Measure text size for the background rectangle
        text_rect = painter.boundingRect(10, 10, image.width(), image.height(), Qt.TextSingleLine, text)

        # Draw the background rectangle for metadata text
        painter.setBrush(Qt.darkGray)  # Dark gray background
        painter.setPen(Qt.NoPen)       # No border for the rectangle
        painter.drawRect(text_rect.adjusted(-10, -5, 10, 5))  # Add padding around the text

        # Draw the metadata text on top of the rectangle
        painter.setPen(Qt.cyan)  # Cyan text color
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignTop, text)

        # End painting
        painter.end()

        # Convert the QImage back to a QPixmap
        updated_pixmap = QPixmap.fromImage(image)

        # Copy the updated pixmap to the clipboard
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(updated_pixmap)


    def show_error(self, message):
        error_dialog = QLabel(message, self)
        error_dialog.setStyleSheet("color: red;")
        error_dialog.show()

    def closeEvent(self, event):
        """Handle application closure"""
        if self.has_camera:
            self.preview_active = False
            if hasattr(self, 'preview_thread') and self.preview_thread.is_alive():
                self.preview_thread.join()
            self.camera.EndAcquisition()
            self.camera.DeInit()
        self.cam_list.Clear()
        self.system.ReleaseInstance()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # set the style globally for the application
    app.setStyle(ProxyStyle())
    
    window = CameraApp()
    window.show()
    sys.exit(app.exec_())
