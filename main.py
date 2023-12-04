import sys
import os
import shutil
import re
import traceback
from PyQt5.QtCore import QPropertyAnimation, QRect, QTimer, QPoint

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QPushButton, QVBoxLayout,
    QWidget, QFileDialog, QMessageBox, QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QIcon

# Обновленный список шаблонов.
# re.DOTALL позволяет '.' совпадать с переносами строк
# Обновленный список шаблонов.
# re.DOTALL позволяет '.' совпадать с переносами строк
pattern_list = [
    re.compile(r'<script.*?(u_global_data|adbetnetshowed=1|utarget|yadro|s200\.ucoz\.net|www\.ucoz\.ru).*?</script>', re.DOTALL),
    re.compile(r'<div align="center">.*?s200\.ucoz\.net.*?</div>', re.DOTALL)
]



# Это условие, когда имя файла считается случайно сгенерированным
def is_random_name(name):
    return len(name) > 30 and re.search(r'\W', name)

def should_remove_directory(dir_path):
    # Проверка, если имя директории '.s' или все файлы внутри имеют случайные имена, то она должна быть удалена
    if os.path.basename(dir_path) == '.s' or all(is_random_name(name) for name in os.listdir(dir_path)):
        return True

    files = os.listdir(dir_path)
    for file in files:
        filepath = os.path.join(dir_path, file)
        # Если это директория, то проверяем её содержимое рекурсивно
        if os.path.isdir(filepath):
            if not should_remove_directory(filepath):
                return False
        # Если файл не имеет случайного имени, то директория не удаляется
        elif not is_random_name(file):
            return False
    return True

def remove_patterns_from_file(file_path, log_callback):
    # Список поддерживаемых текстовых расширений файлов
    supported_extensions = ['.html', '.htm', '.xml']

    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() not in supported_extensions:
        log_callback(f"Skipping unsupported file extension: {file_path}")
        return

    encodings = ['utf-8', 'ISO-8859-1', 'windows-1251']  # Список кодировок для попыток открытия файла
    content = None
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as file:
                content = file.read()
            # Если файл был успешно прочитан, выходим из цикла
            break
        except UnicodeDecodeError:
            log_callback(f"Could not decode file {file_path} with encoding {encoding}. Trying next encoding.")
        except Exception as e:
            log_callback(f"Error opening file {file_path}: {e}")
            traceback.print_exc()
            return  # Пропускаем файл, если он не может быть прочитан

    # Пропустите обработку файла, если содержимое не было прочитано
    if content is None:
        log_callback(f"Failed to read the file {file_path}. It might be a binary file.")
        return

    try:
        for pattern in pattern_list:
            content = pattern.sub('', content)

        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(content)
        log_callback(f"Cleaned file: {file_path}")
    except Exception as e:
        log_callback(f"Error writing to file {file_path}: {e}")
        traceback.print_exc()

def clean_directory(directory, log_callback, progress_callback=None, total_files=None, processed_files=None):
    # Если это первый вызов функции, определите общее количество файлов
    if total_files is None or processed_files is None:
        total_files = sum(len(files) for _, _, files in os.walk(directory))
        processed_files = [0]

    for entry in os.listdir(directory):
        path = os.path.join(directory, entry)
        if os.path.isdir(path):
            # Рекурсивно очищаем директорию и обновляем прогресс
            clean_directory(path, log_callback, progress_callback, total_files, processed_files)
            # Проверяем, нужно ли удалять директорию после обхода всех её файлов
            if should_remove_directory(path):
                shutil.rmtree(path)
                log_callback(f"Removed suspicious directory: {path}")
        else:
            # Здесь добавляем логику для обновления прогресса
            processed_files[0] += 1
            # Удалите этот файл или обработайте его
            remove_patterns_from_file(path, log_callback)   # <-- Здесь мы передаем log_callback
            log_callback(f"Cleaned file: {path}")
            if progress_callback:
                progress = int((processed_files[0] / total_files) * 100)
                progress_callback(progress)

    # Если мы обрабатываем файлы в корневом каталоге, удаляем случайно именованные файлы
    if os.path.abspath(directory) == os.path.abspath(directory):
        for entry in os.listdir(directory):
            path = os.path.join(directory, entry)
            if os.path.isfile(path) and is_random_name(entry):
                os.remove(path)
                log_callback(f"Removed suspicious file: {path}")
                processed_files[0] += 1
                if progress_callback:
                    progress = int((processed_files[0] / total_files) * 100)
                    progress_callback(progress)


class Worker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)

    def __init__(self, directory):
        super().__init__()
        self.directory = directory

    def run(self):
        clean_directory(self.directory, self.update_log, self.update_progress)

    def update_log(self, message):
        self.log_signal.emit(message)

    def update_progress(self, value):
        self.progress_signal.emit(value)


class CleaningUI(QMainWindow):
    def __init__(self):
        super().__init__()
                # Создание и установка центрального виджета
        self.central_widget = QWidget()  
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)
         # Окно с предупреждением о создании бекапа
        backup_warning = QMessageBox()
        backup_warning.setIcon(QMessageBox.Warning)
        backup_warning.setText('Before starting the cleaning process, make sure to back up your files to prevent unintended data loss.')
        backup_warning.setWindowTitle('Create Backup')
        backup_warning.setStyleSheet("QLabel { color: white; } QPushButton { color: white; }")
        backup_warning.exec_()
        self.setWindowTitle('Directory Cleaning Tool')
        self.setWindowIcon(QIcon('clean.png'))  # Установить путь к вашей иконке

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.setGeometry(300, 300, 600, 400)

        self.info_text = QTextEdit()
        self.layout.addWidget(self.info_text)
        self.info_text.setReadOnly(True)
        self.info_text.setPlaceholderText("Log output will appear here...")

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.select_button = QPushButton('Select Directory')
        self.layout.addWidget(self.select_button)
        self.select_button.clicked.connect(self.select_directory)

        self.start_button = QPushButton('Start Cleaning')
        self.layout.addWidget(self.start_button)
        self.start_button.clicked.connect(self.start_cleaning)
        self.start_button.setEnabled(False)  # Изначально отключено до выбора директории
# Задаем начальную позицию относительно главного окна для анимации
        start_pos = self.central_widget.pos() + QPoint(self.central_widget.width(), 0)  # начальная позиция сбоку от текущей позиции
        end_pos = self.central_widget.pos()  # конечная позиция - текущая позиция центрального виджета

        # Создаем анимацию для центрального виджета
        self.content_animation = QPropertyAnimation(self.central_widget, b"pos")
        self.content_animation.setDuration(200)  # Анимация продлится 1 секунду
        self.content_animation.setStartValue(start_pos)
        self.content_animation.setEndValue(end_pos)

        # Запланируем старт анимации после появления окна
        QTimer.singleShot(25, self.content_animation.start)  # Задержка старта анимации на 500 мс

        self.setGeometry(300, 300, 600, 400)
        self.setWindowTitle('Directory Cleaning Tool')
        self.setWindowIcon(QIcon('clean.png'))
        self.show()

    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, 'Select Directory')
        if directory:
            self.directory = directory
            self.info_text.append("Directory selected: {}".format(directory))
            self.start_button.setEnabled(True)
            self.progress_bar.setValue(0)  # Reset progress bar

    def start_cleaning(self):
        if hasattr(self, 'directory') and self.directory:
            confirm = QMessageBox.question(self, 'Start Cleaning',
                                           'Cleaning will permanently delete files. Are you sure you want to proceed?',
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm == QMessageBox.Yes:
                self.worker = Worker(self.directory)
                self.worker.log_signal.connect(self.info_text.append)
                self.worker.progress_signal.connect(self.progress_bar.setValue)
                self.worker.start()
        else:
            QMessageBox.warning(self, 'No Directory Selected', 'Please select a directory first.')


if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyleSheet("""
            QWidget {
                background-color: #1F1F1F;
            }
            QTextEdit {
                border: 1px solid #5A5A5A;
                border-radius: 2px;
                font-family: Arial;
                background-color: #101010;
                color: #7F7F7F;
            }
            QPushButton {
                background-color: #202020;
                color: #E1B700;
                border: 1px solid #5A5A5A;
                border-radius: 3px;
                padding: 5px;
                opacity: 200;
            }
            QPushButton:hover {
                background-color: #E1B700;
                color: #202020;
            }
            QPushButton:pressed {
                background-color: #CCA700;
            }
            QPushButton:disabled {
                background-color: #303030;
                color: #706F6F;
            }
            QProgressBar {
                border: 2px solid #5A5A5A;
                border-radius: 5px;
                text-align: center;
                background-color: #202020;
            }
            QProgressBar::chunk {
                background-color: #E1B700;
            }
    """)

    window = CleaningUI()
    window.show()
    sys.exit(app.exec_())
