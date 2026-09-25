"""Inline SVG icons rendered to QIcon in the current theme colour."""

from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import QIcon, QPainter, QPixmap
from PyQt5.QtSvg import QSvgRenderer

_PATHS = {
    'drive': '<rect x="3" y="7" width="18" height="10" rx="2"/><circle cx="7" cy="12" r="1.2" fill="{c}" stroke="none"/><path d="M11 12h6"/>',
    'lock': '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    'unlock': '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.5-2"/>',
    'key': '<circle cx="8" cy="12" r="3.5"/><path d="M11.5 12H21M18 12v3M15 12v2"/>',
    'shield': '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>',
    'warning': '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    'list': '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1" fill="{c}" stroke="none"/><circle cx="4" cy="12" r="1" fill="{c}" stroke="none"/><circle cx="4" cy="18" r="1" fill="{c}" stroke="none"/>',
    'refresh': '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    'folder': '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    'eject': '<path d="M5 15h14L12 6z"/><path d="M5 19h14"/>',
    'sun': '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    'moon': '<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    'settings': '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    'copy': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/>',
    'check': '<path d="M5 12l4 4L19 6"/>',
    'edit': '<path d="M4 20h4l10-10-4-4L4 16z"/><path d="M13 7l4 4"/>',
    'trash': '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
}

_cache = {}


def svg_markup(name, color, size=24):
    body = _PATHS[name].replace('{c}', color)
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 24 24" fill="none" '
            'stroke="%s" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">%s</svg>'
            % (size, size, color, body))


def pixmap(name, color, size=20, dpr=1.0):
    key = (name, color, size, dpr)
    if key in _cache:
        return _cache[key]
    renderer = QSvgRenderer(QByteArray(svg_markup(name, color, size).encode('utf-8')))
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    _cache[key] = pm
    return pm


def icon(name, color, size=20, dpr=1.0):
    return QIcon(pixmap(name, color, size, dpr))


def app_icon_svg():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#1f5fbf"/><stop offset="1" stop-color="#0f1e33"/></linearGradient></defs>'
        '<rect x="8" y="8" width="112" height="112" rx="26" fill="url(#g)"/>'
        '<rect x="30" y="44" width="68" height="44" rx="10" fill="none" stroke="#ffffff" stroke-width="7"/>'
        '<path d="M46 44V34a18 18 0 0 1 36 0v10" fill="none" stroke="#ffffff" stroke-width="7" stroke-linecap="round"/>'
        '<circle cx="64" cy="66" r="7" fill="#ffffff"/>'
        '</svg>'
    )
