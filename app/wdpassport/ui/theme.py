"""Colour tokens and Qt stylesheets for the light and dark themes."""

LIGHT = {
    'window': '#eef1f5',
    'sidebar': '#0f1e33',
    'sidebar_text': '#c7d3e6',
    'sidebar_active': '#1c3050',
    'sidebar_active_text': '#ffffff',
    'card': '#ffffff',
    'border': '#d9dfe7',
    'text': '#172033',
    'muted': '#5b6778',
    'primary': '#1f5fbf',
    'primary_hover': '#1a51a3',
    'primary_text': '#ffffff',
    'secondary': '#e8edf4',
    'secondary_hover': '#dbe3ee',
    'secondary_text': '#1f2f47',
    'danger': '#b3261e',
    'danger_hover': '#9a1f18',
    'field': '#ffffff',
    'field_border': '#c3ccd8',
    'focus': '#1f5fbf',
    'console': '#0f1623',
    'console_text': '#d5deeb',
    'pill_ok_bg': '#e3f4e8', 'pill_ok_fg': '#1c5b30',
    'pill_warn_bg': '#fff2d9', 'pill_warn_fg': '#7a4b00',
    'pill_err_bg': '#fbe4e2', 'pill_err_fg': '#8a1f18',
    'pill_info_bg': '#e4ecf8', 'pill_info_fg': '#1b3e70',
    'pill_neutral_bg': '#e9edf2', 'pill_neutral_fg': '#3d4a5c',
    'icon': '#1f2f47',
    'icon_sidebar': '#c7d3e6',
    'icon_sidebar_active': '#ffffff',
}

DARK = {
    'window': '#0f141b',
    'sidebar': '#0b1526',
    'sidebar_text': '#aebbd0',
    'sidebar_active': '#1a2c48',
    'sidebar_active_text': '#ffffff',
    'card': '#171f2a',
    'border': '#2a3442',
    'text': '#e6ecf5',
    'muted': '#93a1b5',
    'primary': '#3b7ddd',
    'primary_hover': '#2f6cc4',
    'primary_text': '#ffffff',
    'secondary': '#243040',
    'secondary_hover': '#2c3a4d',
    'secondary_text': '#dbe5f3',
    'danger': '#c9463d',
    'danger_hover': '#b03a32',
    'field': '#0f1621',
    'field_border': '#3a4657',
    'focus': '#4f8fe6',
    'console': '#0a0f16',
    'console_text': '#cfd9e6',
    'pill_ok_bg': '#1d3a27', 'pill_ok_fg': '#bfe9cc',
    'pill_warn_bg': '#4a3a17', 'pill_warn_fg': '#ffe3a6',
    'pill_err_bg': '#4a2321', 'pill_err_fg': '#ffc9c5',
    'pill_info_bg': '#1c2f4d', 'pill_info_fg': '#cfe0ff',
    'pill_neutral_bg': '#26303d', 'pill_neutral_fg': '#c4cfdd',
    'icon': '#dbe5f3',
    'icon_sidebar': '#aebbd0',
    'icon_sidebar_active': '#ffffff',
}


def stylesheet(t):
    return '''
    QMainWindow, QWidget#root { background: %(window)s; }
    QWidget { color: %(text)s; font-size: 13px; }
    QToolTip { color: %(text)s; background: %(card)s; border: 1px solid %(border)s; padding: 4px; }

    QFrame#sidebar { background: %(sidebar)s; }
    QLabel#brandTitle { color: #ffffff; font-size: 15px; font-weight: 700; }
    QLabel#brandSub { color: %(sidebar_text)s; font-size: 11px; }
    QLabel#sidebarFoot { color: %(sidebar_text)s; font-size: 11px; }
    QPushButton#navBtn {
        text-align: left; padding: 9px 12px; border-radius: 8px; border: none;
        color: %(sidebar_text)s; background: transparent; font-weight: 600;
    }
    QPushButton#navBtn:hover { background: rgba(255,255,255,0.06); color: #ffffff; }
    QPushButton#navBtn:checked { background: %(sidebar_active)s; color: %(sidebar_active_text)s; }
    QPushButton#navBtn:disabled { color: rgba(199,211,230,0.45); }
    QPushButton#sideTool {
        text-align: left; padding: 7px 12px; border-radius: 8px; border: none;
        color: %(sidebar_text)s; background: transparent;
    }
    QPushButton#sideTool:hover { background: rgba(255,255,255,0.06); color: #ffffff; }

    QFrame#topbar { background: %(card)s; border-bottom: 1px solid %(border)s; }
    QLabel#pageTitle { font-size: 20px; font-weight: 700; }
    QLabel#pageSubtitle { color: %(muted)s; font-size: 12px; }

    QFrame#card { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; }
    QFrame#cardDanger { background: %(card)s; border: 1px solid %(danger)s; border-radius: 10px; }
    QLabel#cardTitle { font-size: 15px; font-weight: 700; }
    QLabel#cardSub { color: %(muted)s; }
    QLabel#kvKey { color: %(muted)s; font-size: 12px; }
    QLabel#kvVal { font-size: 13px; font-weight: 600; }
    QLabel#hint { color: %(muted)s; }
    QLabel#bodyText { color: %(text)s; }
    QLabel#dangerText { color: %(danger)s; font-weight: 600; }
    QLabel#mono { font-family: monospace; }

    QLineEdit, QComboBox, QPlainTextEdit {
        background: %(field)s; border: 1px solid %(field_border)s; border-radius: 8px;
        padding: 8px 10px; selection-background-color: %(primary)s;
    }
    QLineEdit:focus, QComboBox:focus { border: 1px solid %(focus)s; }
    QLineEdit:disabled, QComboBox:disabled { color: %(muted)s; }
    QComboBox::drop-down { border: none; width: 26px; }
    QComboBox QAbstractItemView { background: %(card)s; border: 1px solid %(border)s; selection-background-color: %(primary)s; selection-color: #ffffff; }
    QCheckBox { spacing: 8px; }

    QPushButton { border-radius: 8px; padding: 8px 14px; font-weight: 600; border: 1px solid transparent; }
    QPushButton#primary { background: %(primary)s; color: %(primary_text)s; }
    QPushButton#primary:hover { background: %(primary_hover)s; }
    QPushButton#primary:disabled { background: %(secondary)s; color: %(muted)s; }
    QPushButton#secondary { background: %(secondary)s; color: %(secondary_text)s; border: 1px solid %(border)s; }
    QPushButton#secondary:hover { background: %(secondary_hover)s; }
    QPushButton#secondary:disabled { color: %(muted)s; }
    QPushButton#danger { background: %(danger)s; color: #ffffff; }
    QPushButton#danger:hover { background: %(danger_hover)s; }
    QPushButton#danger:disabled { background: %(secondary)s; color: %(muted)s; }
    QPushButton#ghost { background: transparent; color: %(primary)s; border: none; padding: 4px 6px; }
    QPushButton#ghost:hover { text-decoration: underline; }

    QTableWidget {
        background: %(card)s; border: 1px solid %(border)s; border-radius: 8px;
        gridline-color: %(border)s; selection-background-color: %(primary)s; selection-color: #ffffff;
    }
    QHeaderView::section { background: %(secondary)s; color: %(muted)s; padding: 6px; border: none; border-bottom: 1px solid %(border)s; font-weight: 600; }
    QTableWidget::item { padding: 6px; }

    QPlainTextEdit#console { background: %(console)s; color: %(console_text)s; border: 1px solid %(border)s; font-family: monospace; font-size: 12px; }

    QProgressBar { background: %(secondary)s; border: none; border-radius: 3px; height: 6px; }
    QProgressBar::chunk { background: %(primary)s; border-radius: 3px; }
    QStatusBar { background: %(card)s; border-top: 1px solid %(border)s; color: %(muted)s; }
    QStatusBar::item { border: none; }
    QScrollArea { border: none; background: transparent; }
    QScrollArea > QWidget > QWidget { background: transparent; }
    QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
    QScrollBar::handle:vertical { background: %(border)s; border-radius: 5px; min-height: 30px; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QMessageBox { background: %(card)s; }
    QDialog { background: %(window)s; }
    ''' % t


PILL_KINDS = {
    'ok': ('pill_ok_bg', 'pill_ok_fg'),
    'warn': ('pill_warn_bg', 'pill_warn_fg'),
    'err': ('pill_err_bg', 'pill_err_fg'),
    'info': ('pill_info_bg', 'pill_info_fg'),
    'neutral': ('pill_neutral_bg', 'pill_neutral_fg'),
}


def pill_style(t, kind):
    bg_key, fg_key = PILL_KINDS.get(kind, PILL_KINDS['neutral'])
    return ('color: %s; background: %s; border-radius: 10px; padding: 4px 10px; '
            'font-size: 11px; font-weight: 700;' % (t[fg_key], t[bg_key]))
