# Copyright (C) 2017  Niklas Rosenstein
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import os
import webbrowser
from . import __version__, library
from .config import config
from .envfile import SectionEnvfile


resdir = os.path.join(os.path.dirname(__file__), 'res')


def _fileselectFor(edit):
  def handler():
    path = QFileDialog.getExistingDirectory()
    if path:
      edit.setText(path)
  return handler


class LibraryModel(QAbstractListModel):

  def __init__(self, envfile):
    QAbstractTableModel.__init__(self)
    self.envfile = envfile
    self.update()

  def update(self):
    self.sections = list(s for s in self.envfile.iter_named_sections() if s.is_library())
    self.layoutChanged.emit()

  def getFromIndex(self, index):
    index = index.row()
    if index < 0 or index >= len(self.sections):
      return
    return self.sections[index]

  def removeIndex(self, index):
    section = self.getFromIndex(index)
    if section:
      self.envfile.remove_section(section.name)

  def rowCount(self, parent=QModelIndex()):
    return len(self.sections)

  def data(self, index, role=Qt.DisplayRole):
    if not index.isValid():
      return None
    section = self.sections[index.row()]
    col = index.column()
    if col == 0 and role == Qt.DisplayRole:
      return '{} v{} ({})'.format(
        section.get_library_name(),
        section.get_library_version() or '???',
        section.get_library_path() or '???'
      )


class Window(QWidget):

  def __init__(self, parent=None):
    QWidget.__init__(self, parent)
    self.setWindowTitle('Houdini Manage v' + __version__)
    self.setWindowIcon(QIcon(os.path.join(resdir, 'icon_manage.png')))
    self.resize(500, 300)

    # Create widgets.
    self.houdiniVersion = QComboBox()
    self.houdiniPath = QLineEdit()
    self.listView = QListView()
    self.menuBar = QMenuBar()
    self._model = None
    self._envfile = None
    self._envfilename = None
    self._lastHoudiniVersionIndex = None

    btnInstall = QPushButton('')
    btnInstall.setIcon(QIcon(os.path.join(resdir, 'install.png')))
    btnInstall.setFixedSize(32, 32)
    btnInstall.setToolTip('Install Library')
    btnInstall.clicked.connect(self._install)
    btnRemove = QPushButton('')
    btnRemove.setIcon(QIcon(os.path.join(resdir, 'remove.png')))
    btnRemove.setFixedSize(32, 32)
    btnRemove.setToolTip('Remove Library')
    btnRemove.clicked.connect(self._remove)
    btnBuild = QPushButton('')
    btnBuild.setIcon(QIcon(os.path.join(resdir, 'build.png')))
    btnBuild.setFixedSize(32, 32)
    btnBuild.setToolTip('(Re)build DSO')
    btnBuild.clicked.connect(self._buildDso)
    btnSave = QPushButton('')
    btnSave.setIcon(QIcon(os.path.join(resdir, 'save.png')))
    btnSave.setFixedSize(32, 32)
    btnSave.setToolTip('Save Environment')
    btnSave.clicked.connect(self._save)
    btnHelp = QPushButton('')
    btnHelp.setIcon(QIcon(os.path.join(resdir, 'question.png')))
    btnHelp.setFixedSize(32, 32)
    btnHelp.setToolTip('Help')
    btnHelp.clicked.connect(self._help)

    # Layout.
    layout = QVBoxLayout(self)
    if True:  # Houdini version selector
      line = QVBoxLayout()
      layout.addLayout(line)
      box = QHBoxLayout()
      line.addLayout(box)
      box.addWidget(QLabel('Houdini Version'))
      box.addWidget(self.houdiniVersion)
      box = QHBoxLayout()
      line.addLayout(box)
      btn = QPushButton('...')
      btn.clicked.connect(_fileselectFor(self.houdiniPath))
      box.addWidget(QLabel('Houdini Application Directory'))
      box.addWidget(self.houdiniPath)
      box.addWidget(btn)
    if True: # List view and right bar
      line = QHBoxLayout()
      layout.addLayout(line)
      line.addWidget(self.listView)

      vert = QVBoxLayout()
      vert.setAlignment(Qt.AlignTop)
      line.addLayout(vert)
      vert.addWidget(btnInstall)
      vert.addWidget(btnRemove)
      vert.addWidget(btnBuild)
      vert.addWidget(make_spacer(vertical=True))
      vert.addWidget(btnSave)
      vert.addWidget(btnHelp)

    # Init values.
    self.houdiniPrefPaths = library.get_houdini_user_prefs_directories()
    self.houdiniVersion.addItems([x[0] for x in self.houdiniPrefPaths])
    self.houdiniVersion.currentIndexChanged.connect(self._updateEnv)
    self.houdiniVersion.setCurrentIndex(0)
    self.houdiniPath.setText(library.get_houdini_application_dir())
    self._updateEnv()

  def closeEvent(self, event):
    if self._envfile and self._envfile.changed:
      reply = QMessageBox.question(self, 'Unsaved Changes',
        'You have unsaved changes in this environment. Do you want to '
        'quit?', QMessageBox.Yes | QMessageBox.No)
      if reply == QMessageBox.Yes:
        event.accept()
      else:
        event.ignore()
    else:
      event.accept()

  def _updateEnv(self):
    index = self.houdiniVersion.currentIndex()
    if self._envfile and self._envfile.changed and index != self._lastHoudiniVersionIndex:
      reply = QMessageBox.question(self, 'Unsaved Changes',
        'You have unsaved changes in this environment. Do you want to '
        'switch versions?', QMessageBox.Yes | QMessageBox.No)
      if reply != QMessageBox.Yes:
        self.houdiniVersion.setCurrentIndex(self._lastHoudiniVersionIndex)
        return
    if index == self._lastHoudiniVersionIndex:
      return
    path = self.houdiniPrefPaths[index][1]
    self._lastHoudiniVersionIndex = index
    if os.path.isfile(path):
      self._envfilename = path
      with open(path) as fp:
        self._envfile = SectionEnvfile.parse(fp)
      self._model = LibraryModel(self._envfile)
    else:
      self._envfilename = None
      self._envfile = None
      self._model = None
    self.listView.setModel(self._model)

  def _install(self):
    if not self._envfile:
      return
    directory = QFileDialog.getExistingDirectory(self)
    if not directory:
      return
    hou_app_dir = self.houdiniPath.text()
    if not hou_app_dir:
      print('No houdini application directory specified, skipping DSO builds.')
    try:
      library.install_library(self._envfile, directory)
      if hou_app_dir:
        if not library.build_dso(hou_app_dir, directory):
          error_dialog('DSO build failed', 'Check console for more information.')
    except library.NotALibraryError as exc:
      error_dialog('Not a Houdini Library', str(exc))
    except library.PreviousInstallationFoundError as exc:
      error_dialog('Previous installation found', 'Please uninstall "{}" first.'.format(exc.library_name))
    except OSError as exc:
      error_dialog('Fatal error', str(exc))
    else:
      self._model.update()

  def _remove(self):
    index = self.listView.selectionModel().selectedIndexes()
    if len(index) != 1:
      return
    self._model.removeIndex(index[0])
    self._model.update()

  def _buildDso(self):
    hou_app_dir = self.houdiniPath.text()
    if not hou_app_dir:
      error_dialog('Error', 'Specify the Houdini Application Path to build DSOs.')
      return
    count = 0
    num_built = 0
    for index in self.listView.selectionModel().selectedIndexes():
      section = self._model.getFromIndex(index)
      try:
        num, ok = library.build_dso(hou_app_dir, section.get_library_path())
        num_built += num
        count += 1
      except OSError as exc:
        error_dialog('Fatal error', str(exc))
        break
    if not count:
      error_dialog('Error', 'Please select a library to rebuild the DSOs for.')
    elif not num_built:
      message_dialog('Note', 'No DSOs in the selected libraries.')

  def _save(self):
    if not self._envfile or not self._envfilename:
      return
    with open(self._envfilename, 'w') as fp:
      self._envfile.render(fp)

  def _help(self):
    webbrowser.open('https://niklasrosenstein.github.io/houdini-manage/')


class FilenameWidget(QWidget):  # Currently not used

  textChanged = pyqtSignal()

  def __init__(self, parent=None, type='file'):
    assert type in ('file', 'directory')
    QWidget.__init__(self, parent)
    QHBoxLayout(self)
    self.type = 'file'
    self.edit = QLineEdit()
    self.edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    self.edit.textChanged.connect(self.textChanged.emit)
    self.button = QPushButton('...')
    self.button.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
    self.button.clicked.connect(self._clicked)
    self.layout().addWidget(self.edit)
    self.layout().addWidget(self.button)
    self.layout().setContentsMargins(0, 0, 0, 0)

  def _clicked(self):
    if self.type == 'directory':
      path = QFileDialog.getExistingDirectory(self)
    else:
      path = QFileDialog.getOpenFileName(self)[0]
    if path:
      self.edit.setText(path)


def make_separator():
  frame = QFrame()
  frame.setFrameShape(QFrame.HLine)
  frame.setFrameShadow(QFrame.Sunken)
  return frame


def make_spacer(vertical=False):
  label = QLabel('')
  policy = QSizePolicy.Expanding, QSizePolicy.Preferred
  if vertical:
    policy = reversed(policy)
  label.setSizePolicy(*policy)
  return label


def message_dialog(title, message):
  QMessageBox.information(None, title, message)


def error_dialog(title, message):
  QMessageBox.critical(None, title, message)


def main():
  app = QApplication([])
  wnd = Window()
  wnd.show()
  app.exec_()
  return 0
