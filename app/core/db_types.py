"""
Cross-database column type shims.

The original models import MySQL-only types (BINARY, POINT, LINESTRING)
from sqlalchemy.dialects.mysql. For the local demo we run on SQLite,
so models import from here instead. On SQLite these become plain
LargeBinary / Text columns; on MySQL they still work (BLOB / TEXT),
so the demo stays compatible with the original schema intent.
Spatial SQL (ST_Distance etc.) is MySQL-only; demo queries avoid it.
"""

from sqlalchemy import LargeBinary, Text
from sqlalchemy.types import TypeDecorator


def BINARY(n=16):
    """UUID storage: 16 raw bytes. Works on both MySQL (BLOB) and SQLite."""
    return LargeBinary(n)


class GeometryText(TypeDecorator):
    """
    Geometry stored as WKT text.

    The backend writes WKT strings (e.g. 'POINT(77.7 28.9)') via
    ST_GeomFromText on MySQL. In the demo we store the same WKT text
    directly and skip spatial SQL (nearest-checkpoint falls back to
    Python distance).
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


def POINT(**kwargs):
    return GeometryText()


def LINESTRING(**kwargs):
    return GeometryText()
