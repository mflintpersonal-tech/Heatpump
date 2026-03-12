# apsw extension to return dictionary objects for each row
def row_factory(cursor, row):
    columns = [t[0] for t in cursor.getdescription()]
    return dict(zip(columns, row))

class DBConnection:
    def __init__(self, db_type="sqlite", **kwargs):
        self.db_type = db_type

        if db_type == "sqlite":
            import apsw
            import apsw.ext
            self.conn = apsw.Connection(kwargs.get("database"))
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA busy_timeout = 1000")
            self.conn.setrowtrace(row_factory)
            self.paramstyle = "qmark"  # APSW uses ?
        elif db_type == "mysql":
            import mysql.connector
            self.conn = mysql.connector.connect(
                host=kwargs.get("host"),
                user=kwargs.get("user"),
                password=kwargs.get("password"),
                database=kwargs.get("database")
            )
            self.paramstyle = "format"  # MySQL uses %s
        else:
            raise ValueError("Unsupported database type")

    def cursor(self, as_dict=False):
        if self.db_type == "mysql" and as_dict:
            return self.conn.cursor(dictionary=True)
        else:
            return self.conn.cursor()

    def commit(self):
        if self.db_type == "mysql":
            self.conn.commit()  # APSW commits automatically

    def close(self):
        self.conn.close()

    # --- General execute ---
    def execute(self, query, params=None, fetch=False, as_dict=True):
        cur = self.cursor(as_dict=as_dict)
        q = query
        selecting = (query.strip()[0:7].lower() == 'select ')
        #print(q)
        if self.paramstyle == "format" and params:
            q = query.replace("?", "%s")
        if self.paramstyle == "format" and selecting:
            fetch = True
        if params:
            cur.execute(q, params)
        else:
            cur.execute(q)
        #result = cur.fetchall() if fetch else None
        result = cur.fetchall() if fetch else cur.rowcount
        if not selecting: self.commit()
        cur.close()

        return result

    # --- Batch execute for inserts/updates/deletes ---
    def executemany(self, query, param_list):
        cur = self.cursor()
        q = query
        if self.paramstyle == "format":
            q = query.replace("?", "%s")
        cur.executemany(q, param_list)
        self.commit()
        cur.close()
