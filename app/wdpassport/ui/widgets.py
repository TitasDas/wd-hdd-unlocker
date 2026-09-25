"""Small reusable widgets: cards, pills, key/value grids, password fields."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QVBoxLayout, QWidget,
)

from . import theme


class Card(QFrame):
    def __init__(self, title='', subtitle='', danger=False, parent=None):
        super().__init__(parent)
        self.setObjectName('cardDanger' if danger else 'card')
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(18, 16, 18, 16)
        self.body.setSpacing(10)
        self.title_label = None
        self.sub_label = None
        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName('cardTitle')
            self.body.addWidget(self.title_label)
        if subtitle:
            self.sub_label = QLabel(subtitle)
            self.sub_label.setObjectName('cardSub')
            self.sub_label.setWordWrap(True)
            self.body.addWidget(self.sub_label)

    def add(self, widget_or_layout, stretch=0):
        if isinstance(widget_or_layout, QWidget):
            self.body.addWidget(widget_or_layout, stretch)
        else:
            self.body.addLayout(widget_or_layout, stretch)


class Pill(QLabel):
    def __init__(self, text='', kind='neutral', parent=None):
        super().__init__(text, parent)
        self.kind = kind
        self.tokens = theme.LIGHT
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.refresh()

    def set(self, text, kind=None):
        self.setText(text)
        if kind:
            self.kind = kind
        self.refresh()

    def apply_theme(self, tokens):
        self.tokens = tokens
        self.refresh()

    def refresh(self):
        self.setStyleSheet(theme.pill_style(self.tokens, self.kind))


class KeyValueGrid(QWidget):
    def __init__(self, columns=2, parent=None):
        super().__init__(parent)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(10)
        self.columns = columns
        self.values = {}
        self.count = 0

    def add(self, key, value='', mono=False):
        row, col = divmod(self.count, self.columns)
        box = QVBoxLayout()
        box.setSpacing(2)
        k = QLabel(key)
        k.setObjectName('kvKey')
        v = QLabel(value or '—')
        v.setObjectName('mono' if mono else 'kvVal')
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.setWordWrap(True)
        box.addWidget(k)
        box.addWidget(v)
        self.grid.addLayout(box, row, col)
        self.values[key] = v
        self.count += 1
        return v

    def set(self, key, value):
        if key in self.values:
            self.values[key].setText(value or '—')


class PasswordField(QWidget):
    """Password entry with a show/hide checkbox underneath."""

    def __init__(self, placeholder='Password', parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setMaxLength(64)
        self.show = QCheckBox('Show')
        self.show.toggled.connect(self._toggle)
        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(self.show, 0)
        layout.addLayout(row)

    def _toggle(self, checked):
        self.edit.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)

    def text(self):
        return self.edit.text()

    def clear(self):
        self.edit.clear()

    def setFocus(self):
        self.edit.setFocus()


def label(text, name='bodyText', wrap=True):
    lbl = QLabel(text)
    lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def hrow(*widgets, stretch_last=False):
    row = QHBoxLayout()
    row.setSpacing(8)
    for w in widgets:
        if w == 'stretch':
            row.addStretch(1)
        else:
            row.addWidget(w)
    if stretch_last:
        row.addStretch(1)
    return row
