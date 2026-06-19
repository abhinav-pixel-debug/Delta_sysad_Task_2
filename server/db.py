import sqlite3

#Code to setup the database
conn=sqlite3.connect('music_streaming/music.db',isolation_level=None)
cursor=conn.cursor()


def init_db():
    with open('music_streaming/schema.sql') as f:
        conn.executescript(f.read())



if __name__ == "__main__":
    init_db()
    conn.close()