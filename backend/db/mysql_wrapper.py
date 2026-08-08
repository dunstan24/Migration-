import pymysql
import pymysql.cursors
from sqlalchemy import create_engine
import re

class MySQLCursorWrapper:
    def __init__(self, cursor, convert_func):
        self.cursor = cursor
        self.convert_func = convert_func

    def execute(self, sql, params=None):
        converted_sql = self.convert_func(sql)
        try:
            if params:
                self.cursor.execute(converted_sql, params)
            else:
                self.cursor.execute(converted_sql)
            return self
        except (pymysql.err.OperationalError, pymysql.err.ProgrammingError) as e:
            # Error 1061: Duplicate key name (Index already exists)
            if "CREATE INDEX" in converted_sql.upper() and e.args[0] == 1061:
                return self
            else:
                raise

    def executemany(self, sql, params_list):
        converted_sql = self.convert_func(sql)
        self.cursor.executemany(converted_sql, params_list)
        return self

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
        
    def __iter__(self):
        return iter(self.cursor.fetchall())

    def __getattr__(self, name):
        # Forward other attributes to the raw cursor
        return getattr(self.cursor, name)

class SqliteToMysqlWrapper:
    def __init__(self, pymysql_args):
        self.pymysql_args = pymysql_args.copy()
        # Default to tuple cursor (pymysql default) to match sqlite3 default
        self.conn = pymysql.connect(**self.pymysql_args)
        self._row_factory = None

    @property
    def row_factory(self):
        return self._row_factory

    @row_factory.setter
    def row_factory(self, value):
        self._row_factory = value
        # If set to a dict-like factory, we switch to DictCursor
        # Note: In SQLite, row_factory=sqlite3.Row is common.
        self.conn.close()
        args = self.pymysql_args.copy()
        if value is not None:
            args['cursorclass'] = pymysql.cursors.DictCursor
        self.conn = pymysql.connect(**args)

    def cursor(self):
        """Return a wrapper that performs SQL translation"""
        return MySQLCursorWrapper(self.conn.cursor(), self._convert_sql)

    def _convert_sql(self, sql):
        # Convert SQLite ? to MySQL %s
        sql = sql.replace('?', '%s')
        
        # Convert AUTOINCREMENT to AUTO_INCREMENT
        sql = re.sub(r'\bAUTOINCREMENT\b', 'AUTO_INCREMENT', sql, flags=re.IGNORECASE)
        
        # Convert TEXT DEFAULT (datetime('now')) to TIMESTAMP
        sql = sql.replace("TEXT DEFAULT (datetime('now'))", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        sql = sql.replace("DEFAULT (datetime('now'))", "DEFAULT CURRENT_TIMESTAMP")
        
        # MySQL doesn't support CREATE INDEX IF NOT EXISTS in many versions
        sql = re.sub(r'CREATE\s+INDEX\s+IF\s+NOT\s+EXISTS', 'CREATE INDEX', sql, flags=re.IGNORECASE)
        
        return sql

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)
        
    def executemany(self, sql, params_list):
        return self.cursor().executemany(sql, params_list)

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()

def get_mysql_wrapper(settings):
    return SqliteToMysqlWrapper(settings.get_pymysql_args)
