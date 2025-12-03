import sys
import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                              QHBoxLayout, QListWidget, QPushButton, QLabel, 
                              QFileDialog, QTabWidget, QMenu, QSystemTrayIcon,
                              QListWidgetItem, QDialog, QLineEdit)
from PyQt6.QtCore import Qt, QTimer, QPoint, QRect, QMimeData, QUrl, pyqtSignal
from PyQt6.QtGui import QCursor, QDrag, QIcon, QAction, QPixmap
import subprocess


class WorkspaceDialog(QDialog):
    """워크스페이스 추가/편집 다이얼로그"""
    def __init__(self, parent=None, workspace_name="", workspace_path=""):
        super().__init__(parent)
        self.setWindowTitle("워크스페이스 설정")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # 이름 입력
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("이름:"))
        self.name_input = QLineEdit(workspace_name)
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)
        
        # 경로 선택
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("경로:"))
        self.path_input = QLineEdit(workspace_path)
        path_layout.addWidget(self.path_input)
        browse_btn = QPushButton("찾아보기")
        browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(browse_btn)
        layout.addLayout(path_layout)
        
        # 버튼
        button_layout = QHBoxLayout()
        ok_btn = QPushButton("확인")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "폴더 선택")
        if folder:
            self.path_input.setText(folder)
    
    def get_data(self):
        return self.name_input.text(), self.path_input.text()


class FileListWidget(QListWidget):
    """드래그 가능한 파일 리스트 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.pos()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        
        item = self.currentItem()
        if not item:
            return
        
        # 드래그 시작
        drag = QDrag(self)
        mime_data = QMimeData()
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        mime_data.setUrls([QUrl.fromLocalFile(file_path)])
        drag.setMimeData(mime_data)
        
        drag.exec(Qt.DropAction.CopyAction)


class FolderHubWindow(QMainWindow):
    """메인 QuickDrop 윈도우"""
    def __init__(self):
        super().__init__()
        self.config_file = Path.home() / ".folder_hub_config.json"
        self.workspaces = {}
        self.current_workspace = None
        self.is_pinned = False
        
        self.init_ui()
        self.load_config()
        self.setup_auto_hide()
        self.setup_tray_icon()
        
    def init_ui(self):
        self.setWindowTitle("QuickDrop")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 메인 위젯
        main_widget = QWidget()
        main_widget.setObjectName("mainWidget")
        main_widget.setStyleSheet("""
            QWidget#mainWidget {
                background-color: rgba(40, 40, 40, 240);
                border-radius: 10px;
                border: 1px solid rgba(80, 80, 80, 180);
            }
            QTabWidget::pane {
                border: none;
                background-color: transparent;
            }
            QTabBar::tab {
                background-color: rgba(60, 60, 60, 200);
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background-color: rgba(80, 80, 80, 255);
            }
            QListWidget {
                background-color: rgba(50, 50, 50, 200);
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: rgba(70, 70, 70, 255);
            }
            QListWidget::item:selected {
                background-color: rgba(0, 120, 212, 255);
            }
            QPushButton {
                background-color: rgba(0, 120, 212, 255);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(0, 140, 232, 255);
            }
            QPushButton:pressed {
                background-color: rgba(0, 100, 192, 255);
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 상단 버튼 영역
        top_layout = QHBoxLayout()
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setMaximumWidth(40)
        self.pin_btn.setToolTip("고정")
        self.pin_btn.clicked.connect(self.toggle_pin)
        
        add_workspace_btn = QPushButton("+ 워크스페이스")
        add_workspace_btn.clicked.connect(self.add_workspace)
        
        settings_btn = QPushButton("⚙️")
        settings_btn.setMaximumWidth(40)
        settings_btn.clicked.connect(self.show_settings)
        
        close_btn = QPushButton("✕")
        close_btn.setMaximumWidth(40)
        close_btn.clicked.connect(self.hide)
        
        top_layout.addWidget(self.pin_btn)
        top_layout.addWidget(add_workspace_btn)
        top_layout.addStretch()
        top_layout.addWidget(settings_btn)
        top_layout.addWidget(close_btn)
        
        layout.addLayout(top_layout)
        
        # 워크스페이스 탭
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self.remove_workspace)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tab_widget)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
        
        # 기본 크기 및 위치 설정
        self.resize(600, 400)
        self.position_at_top()
        self.hide()
        
    def position_at_top(self):
        """화면 상단 중앙에 위치"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = 0
        self.move(x, y)
    
    def setup_auto_hide(self):
        """자동 숨김 타이머 설정"""
        self.hide_timer = QTimer()
        self.hide_timer.timeout.connect(self.check_mouse_position)
        self.hide_timer.start(100)
        
        self.show_timer = QTimer()
        self.show_timer.timeout.connect(self.check_show_trigger)
        self.show_timer.start(100)
    
    def check_show_trigger(self):
        """마우스가 상단에 있을 때 창 표시"""
        if self.isVisible() or self.is_pinned:
            return
        
        pos = QCursor.pos()
        screen = QApplication.primaryScreen().geometry()
        
        # 화면 상단 50px 영역에 마우스가 있으면 표시
        if pos.y() < 50 and 0 <= pos.x() <= screen.width():
            self.show()
            self.position_at_top()
            self.raise_()
            self.activateWindow()
    
    def check_mouse_position(self):
        """마우스가 창 밖으로 나가면 자동 숨김"""
        if self.is_pinned or not self.isVisible():
            return
        
        pos = QCursor.pos()
        window_rect = self.geometry()
        
        # 창 영역을 약간 확장하여 여유 공간 제공
        expanded_rect = window_rect.adjusted(-20, -20, 20, 20)
        
        if not expanded_rect.contains(pos):
            self.hide()
    
    def toggle_pin(self):
        """고정 토글"""
        self.is_pinned = not self.is_pinned
        if self.is_pinned:
            self.pin_btn.setText("📍")
            self.pin_btn.setToolTip("고정 해제")
        else:
            self.pin_btn.setText("📌")
            self.pin_btn.setToolTip("고정")
    
    def add_workspace(self):
        """워크스페이스 추가"""
        dialog = WorkspaceDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, path = dialog.get_data()
            if name and path and os.path.exists(path):
                self.create_workspace(name, path)
                self.save_config()
    
    def create_workspace(self, name, path):
        """워크스페이스 생성"""
        # 파일 리스트 위젯 생성
        file_list = FileListWidget()
        file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        file_list.customContextMenuRequested.connect(
            lambda pos: self.show_context_menu(pos, file_list, path)
        )
        
        # 탭 추가
        tab_index = self.tab_widget.addTab(file_list, name)
        self.workspaces[name] = {
            'path': path,
            'widget': file_list,
            'index': tab_index
        }
        
        # 파일 목록 로드
        self.load_files(name)
        
        # 새 탭으로 전환
        self.tab_widget.setCurrentIndex(tab_index)
    
    def load_files(self, workspace_name):
        """워크스페이스의 파일 목록 로드"""
        workspace = self.workspaces.get(workspace_name)
        if not workspace:
            return
        
        path = workspace['path']
        file_list = workspace['widget']
        file_list.clear()
        
        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                list_item = QListWidgetItem(
                    f"📁 {item}" if os.path.isdir(item_path) else f"📄 {item}"
                )
                list_item.setData(Qt.ItemDataRole.UserRole, item_path)
                file_list.addItem(list_item)
        except Exception as e:
            print(f"파일 로드 오류: {e}")
    
    def show_context_menu(self, pos, file_list, base_path):
        """컨텍스트 메뉴 표시"""
        item = file_list.itemAt(pos)
        if not item:
            return
        
        file_path = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(50, 50, 50, 240);
                color: white;
                border: 1px solid rgba(80, 80, 80, 180);
            }
            QMenu::item:selected {
                background-color: rgba(0, 120, 212, 255);
            }
        """)
        
        open_action = QAction("열기", self)
        open_action.triggered.connect(lambda: self.open_file(file_path))
        menu.addAction(open_action)
        
        show_in_finder = QAction("Finder에서 보기", self)
        show_in_finder.triggered.connect(lambda: self.show_in_finder(file_path))
        menu.addAction(show_in_finder)
        
        refresh_action = QAction("새로고침", self)
        refresh_action.triggered.connect(
            lambda: self.load_files(self.get_current_workspace_name())
        )
        menu.addAction(refresh_action)
        
        menu.exec(file_list.mapToGlobal(pos))
    
    def open_file(self, file_path):
        """파일 열기"""
        subprocess.run(['open', file_path])
    
    def show_in_finder(self, file_path):
        """Finder에서 보기"""
        subprocess.run(['open', '-R', file_path])
    
    def get_current_workspace_name(self):
        """현재 워크스페이스 이름 반환"""
        current_index = self.tab_widget.currentIndex()
        for name, workspace in self.workspaces.items():
            if workspace['index'] == current_index:
                return name
        return None
    
    def remove_workspace(self, index):
        """워크스페이스 제거"""
        name_to_remove = None
        for name, workspace in self.workspaces.items():
            if workspace['index'] == index:
                name_to_remove = name
                break
        
        if name_to_remove:
            self.tab_widget.removeTab(index)
            del self.workspaces[name_to_remove]
            self.save_config()
            
            # 인덱스 재조정
            for name, workspace in self.workspaces.items():
                workspace['index'] = self.tab_widget.indexOf(workspace['widget'])
    
    def on_tab_changed(self, index):
        """탭 변경 시"""
        self.current_workspace = self.get_current_workspace_name()
    
    def show_settings(self):
        """설정 표시 (추후 확장 가능)"""
        print("설정 창 (추후 구현)")
    
    def setup_tray_icon(self):
        """시스템 트레이 아이콘 설정"""
        self.tray_icon = QSystemTrayIcon(self)
        
        # 아이콘 생성 (간단한 픽스맵)
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        self.tray_icon.setIcon(QIcon(pixmap))
        
        # 트레이 메뉴
        tray_menu = QMenu()
        show_action = QAction("QuickDrop 표시", self)
        show_action.triggered.connect(self.show_and_position)
        tray_menu.addAction(show_action)
        
        quit_action = QAction("종료", self)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()
        
        # 트레이 아이콘 클릭
        self.tray_icon.activated.connect(self.tray_icon_clicked)
    
    def tray_icon_clicked(self, reason):
        """트레이 아이콘 클릭 처리"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_and_position()
    
    def show_and_position(self):
        """창 표시 및 위치 조정"""
        self.show()
        self.position_at_top()
        self.raise_()
        self.activateWindow()
    
    def load_config(self):
        """설정 파일 로드"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    workspaces = config.get('workspaces', {})
                    
                    for name, path in workspaces.items():
                        if os.path.exists(path):
                            self.create_workspace(name, path)
            except Exception as e:
                print(f"설정 로드 오류: {e}")
        
        # 기본 워크스페이스 추가
        if not self.workspaces:
            self.create_workspace("데스크탑", str(Path.home() / "Desktop"))
            self.create_workspace("다운로드", str(Path.home() / "Downloads"))
    
    def save_config(self):
        """설정 파일 저장"""
        config = {
            'workspaces': {
                name: workspace['path'] 
                for name, workspace in self.workspaces.items()
            }
        }
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"설정 저장 오류: {e}")
    
    def closeEvent(self, event):
        """창 닫기 이벤트"""
        event.ignore()
        self.hide()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    window = FolderHubWindow()
    
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
