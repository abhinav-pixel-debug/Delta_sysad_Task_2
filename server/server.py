import socket 
import threading
import json
import sqlite3
import hashlib
import wave
import os
import time
from collections import defaultdict
import shutil   

def backup_database():
    os.makedirs("music_streaming/backups", exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    backup_path = os.path.join("music_streaming/backups", f"music-{timestamp}.db")
    shutil.copy2("music_streaming/music.db", backup_path)
    print(f"[BACKUP] Saved DB backup to {backup_path}")

def backup_loop():
    while True:
        time.sleep(30)  
        try:
            backup_database()
        except Exception as e:
            print(f"[BACKUP ERROR] {e}")


IP_CONNECTION_COUNT = defaultdict(int)
FAILED_LOGINS_BY_IP = defaultdict(int)
MAX_CONNECTIONS_PER_IP = 50    
MAX_FAILED_LOGINS_PER_IP = 5
BAN_SECONDS = 300   


SESSIONS={}
class UserState:
    def __init__(self,user_id):
        self.session_id=str(user_id)
        self.user_id=user_id
        self.current_track_id=None
        self.playback_position=0
        self.playing=False
        self.paused=False
        self.buffer_health=0
        self.conn=None


def ban_ip(ip): 
    now = int(time.time())
    expires = now + BAN_SECONDS
    conn = sqlite3.connect("music_streaming/music.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO active_Ban (ip_address, banned_at, expires_at) VALUES (?, ?, ?)",
        (ip, now, expires)
    )
    conn.commit()
    conn.close()
    print(f"[BAN] IP {ip} banned until {expires}")

def is_ip_banned(ip): 
    now = int(time.time())
    conn = sqlite3.connect("music_streaming/music.db")
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM active_Ban WHERE ip_address = ? AND expires_at > ?",
        (ip, now)
    )
    row = cur.fetchone()
    conn.close()
    return row is not None

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password, stored_hash):
    return hash_password(password) == stored_hash

def create_user(username,password):
    password_hash=hash_password(password)
    conn=sqlite3.connect('music_streaming/music.db')
    cursor=conn.cursor()

    try:
        cursor.execute("INSERT INTO users (username,password_HASH) VALUES (?,?) ",(username,password_hash))
        conn.commit()
        return{
            "status":True,
            "message":"Account created please login"
        }

    except sqlite3.IntegrityError as e:
        return {
            "status":False,
            "message":"Username already taken"            
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
        }
    finally:
        conn.close()


def login_user(username,password):
    conn=sqlite3.connect('music_streaming/music.db')
    cursor=conn.cursor()
    try:
        cursor.execute("SELECT user_id, password_HASH FROM users WHERE username = ?", (username,))
        row=cursor.fetchone()
        if row is None:
            return{
                "status":False,
                "message":"User not found"
            }
        user_id, store_password=row
        if check_password(password,store_password):
            return{
                "status":True,
                "message":user_id
            }    
        else:
            return{
                "status":False,
                "message":"Invalid password"
            }
    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}"
        }

    finally:
        conn.close()




def get_song_path(track_id):
    conn=sqlite3.connect('music_streaming/music.db')
    cursor=conn.cursor()
    try:
        cursor.execute("SELECT file_path FROM songs WHERE song_id=?",(track_id,))
        row=cursor.fetchone()
        if row is None:
            return{
                "status":False,
                "message":"Wrong track id"
            }
        filepath=row[0]
        return{
            "status":True,
            "message":filepath
        }
    except Exception:
        return{
            "status":False,
            "message":"Unexpected error occured"
        }
    finally:
        conn.close()


def stream_song(user_state):
    track_id=user_state.current_track_id
    if track_id is None:
        return
    conn=user_state.conn
    if conn is None:
        return

    path_result=get_song_path(track_id)
    if not path_result["status"]:
        print(path_result["message"])
        return
    file_path = path_result["message"]
    with wave.open(file_path,"rb") as wf:
        chunk_size=4096
        chunk_sent=user_state.playback_position
        wf.setpos(chunk_size*chunk_sent)
        data=wf.readframes(chunk_size)
        while data and user_state.playing:
            if user_state.paused:
                time.sleep(0.1)
                continue
            try:
                conn.sendall(data)
                user_state.buffer_health = 0
            except Exception:
                user_state.buffer_health += 1
                print(f"Send error, buffer_health={user_state.buffer_health}")
                if user_state.buffer_health > 5:
                    break
                time.sleep(0.1)
                continue
            user_state.playback_position+=1
            data=wf.readframes(chunk_size)

def create_playlist(user_id,name):
    conn=sqlite3.connect('music_streaming/music.db')
    cursor=conn.cursor()
    try:
        cursor.execute("INSERT INTO playlists (user_id,name) VALUES (?,?) ",(user_id,name))
        conn.commit()
        return{
            "status":True,
            "message":"Playlist created"
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
        }
    finally:
        conn.close()

def show_playlist(user_id):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT name, playlist_id FROM playlists WHERE user_id = ?",
            (user_id,)
        )
        rows = cursor.fetchall()

        if not rows:
            return {
                "status": False,
                "message": "No playlists found",
                "data": []
            }

        data = []
        for row in rows:
            data.append({
                "name": row[0],
                "playlist_id": row[1]
            })

        return {
            "status": True,
            "message": "Playlists:",
            "data": data
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
            "data": []
        }

    finally:
        conn.close()

def list_songs(playlist_id):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT s.song_id, s.title
            FROM songs s
            JOIN playlist_songs ps ON s.song_id = ps.song_id
            WHERE ps.playlist_id = ?
        """, (playlist_id,))

        rows = cursor.fetchall()

        if not rows:
            return {
                "status": True,
                "message": "No songs found in playlist",
                "data": []
            }

        songs = [
            {"song_id": row[0], "title": row[1]}
            for row in rows
        ]

        return {
            "status": True,
            "message": "Songs found",
            "data": songs
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
            "data": []
        }

    finally:
        conn.close()

def search_songs(name):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT songs.title, songs.song_id, artists.name
            FROM songs
            JOIN artists ON songs.artist_id = artists.artist_id
            WHERE LOWER(songs.title) LIKE LOWER(?)
        """, (f"{name}%",))

        rows = cursor.fetchall()
        if not rows:
            return {
                "status": True,
                "message": "No songs found",
                "data": []
            }

        data = []
        for row in rows:
            data.append({
                "title": row[0],
                "song_id": row[1],
                "artist_name": row[2]
            })
        return {
            "status": True,
            "message": "Songs found",
            "data": data
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
            "data": []
        }

    finally:
        conn.close()

def add_to_playlist(p_id,s_id):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO playlist_songs (playlist_id,song_id) VALUES (?,?) ",(p_id,s_id))
        conn.commit()
        return{
            "status":True,
            "message":"Song added to Playlist"
        }
    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
        }
    finally:
        conn.close()

def add_listening_history(user_id, song_id):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()
    try:
        listened_at = int(time.time())  
        cursor.execute(
            "INSERT INTO listening_history (user_id, song_id, listened_at) VALUES (?, ?, ?)",
            (user_id, song_id, listened_at)
        )
        conn.commit()
    finally:
        conn.close()

def view_history(user_id):
    conn = sqlite3.connect('music_streaming/music.db')
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT listening_history.listened_at,
                   songs.title,
                   songs.song_id,
                   artists.name
            FROM listening_history
            JOIN songs   ON listening_history.song_id = songs.song_id
            JOIN artists ON songs.artist_id = artists.artist_id
            WHERE listening_history.user_id = ?
        """, (user_id,))

        rows = cursor.fetchall()

        if not rows:
            return {
                "status": True,
                "message": "No songs found",
                "data": []
            }

        data = []
        for row in rows:
            data.append({
                "listened_at": row[0],
                "title":       row[1],
                "song_id":     row[2],
                "artist_name": row[3]
            })

        return {
            "status": True,
            "message": "Songs found",
            "data": data
        }

    except Exception as e:
        return {
            "status": False,
            "message": f"Some error occurred: {str(e)}",
            "data": []
        }

    finally:
        conn.close()

def process_command(msg, auth, user_state, conn, ip): 
    parts = msg.split()

    if not auth:
        if len(parts) == 3 and parts[0] == "LOGIN":
            username = parts[1]
            password = parts[2]

            if is_ip_banned(ip):
                return {"status": False, "message": "Your IP is banned"}, False, user_state

            result = login_user(username, password)

            if result["status"]:
                FAILED_LOGINS_BY_IP[ip] = 0

                user_id = result["message"]
                if str(user_id) in SESSIONS:
                    user_state = SESSIONS[str(user_id)]
                else:
                    user_state = UserState(user_id)
                    SESSIONS[user_state.session_id] = user_state
                return result, True, user_state
            else:
            
                FAILED_LOGINS_BY_IP[ip] += 1
                if FAILED_LOGINS_BY_IP[ip] >= MAX_FAILED_LOGINS_PER_IP:
                    ban_ip(ip)
                    return {"status": False, "message": "Too many failed attempts, IP banned"}, False, user_state
                return result, False, user_state

        elif len(parts) == 3 and parts[0] == "REGISTER":
            return create_user(parts[1], parts[2]), False, user_state

        else:
            return {"status": False, "message": "Invalid input"}, auth, user_state

    if parts[0] == "PLAY":
        if len(parts) < 2:
            return {"status": False, "message": "No track id provided"}, auth, user_state
        try:
            track_id = int(parts[1])
        except ValueError:
            return {"status": False, "message": "Track id must be integer"}, auth, user_state
        user_state.current_track_id = track_id
        user_state.playing = True
        user_state.paused = False
        user_state.buffer_health = 0
        add_listening_history(user_state.user_id,track_id)

        return {"status": True, "message": f"Started {track_id}"}, auth, user_state

    elif parts[0] == "PAUSE":
        if not user_state or not user_state.playing:
            return {"status": False, "message": "Nothing is playing"}, auth, user_state
        user_state.paused = True
        return {"status": True, "message": "Paused"}, auth, user_state

    elif parts[0] == "RESUME":
        if not user_state or not user_state.playing:
            return {"status": False, "message": "Nothing is playing"}, auth, user_state
        user_state.paused = False
        return {"status": True, "message": "Resumed"}, auth, user_state
    elif parts[0]=="CREATE":
        if len(parts) == 2:
            result=create_playlist(user_state.user_id,parts[1])
            return result, auth, user_state
        else:
            return {
                "status":False,
                "message":"Invalid Input"
            }, auth, user_state

    elif parts[0]=="LIST":
        if len(parts) == 2:
            result=list_songs(parts[1])
            return result, auth, user_state
        else:
            return {
                "status":False,
                "message":"Invalid Input"
            }, auth, user_state

    elif parts[0]=="SHOW":
        result=show_playlist(user_state.user_id)
        return result, auth, user_state

    elif parts[0]=="SEARCH":
        if len(parts) >= 2:
            name = " ".join(parts[1:])
            result=search_songs(name)
            return result, auth, user_state
        else:
            return {
                "status":False,
                "message":"Invalid Input"
            }, auth, user_state
    elif parts[0]=="ADD":
        if len(parts) == 3:
            result=add_to_playlist(parts[1],parts[2])
            return result, auth, user_state
    elif parts[0]=="HISTORY":
        result=view_history(user_state.user_id)
        return result, auth, user_state

    elif parts[0] == "EXIT":
        user_state.conn.close()
        return {"status": True, "message": "Goodbye"}, False, user_state

    return {"status": False, "message": "Invalid input"}, auth, user_state


def handle_client(conn, addr):
    ip = addr[0]
    print(f"Connected by {addr}")
    auth = False
    user_state = None
    try:
        while True:
            data = conn.recv(1024).decode()
            if not data:
                break
            resp, auth, user_state = process_command(data, auth, user_state, conn, ip)
            conn.sendall(json.dumps(resp).encode())
    finally:
        conn.close()
        if IP_CONNECTION_COUNT[ip] > 0:
            IP_CONNECTION_COUNT[ip] -= 1
        print(f"Connection closed by {addr}")

def handle_audio_client(conn, addr, first_line):
    print(f"[AUDIO] Connected by {addr}")

    parts = first_line.split()
    if len(parts) < 2:
        conn.close()
        return

    user_id = parts[1]
    user_state = SESSIONS.get(str(user_id))
    if user_state is None:
        print(f"[AUDIO] Unknown user_id {user_id}")
        conn.close()
        return

    user_state.conn = conn
    stream_song(user_state)
    conn.close()
    user_state.conn = None
    print(f"[AUDIO CLOSED] {addr}")


def dispatch_client(conn, addr):
    try:
        first = conn.recv(1024).decode().strip()

        if first.startswith("CONTROL"):
            conn.sendall(json.dumps({
                "status": True,
                "message": "CONTROL connection established"
            }).encode())
            handle_client(conn, addr)

        elif first.startswith("AUDIO"):
            handle_audio_client(conn, addr, first)

        else:
            conn.sendall(json.dumps({
                "status": False,
                "message": f"Unknown connection type: {first}"
            }).encode())
            conn.close()

    except Exception as e:
        print(f"Error in dispatch_client: {e}")
        try:
            conn.sendall(json.dumps({
                "status": False,
                "message": f"Server error: {str(e)}"
            }).encode())
        except:
            pass
        conn.close()

server=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(('localhost', 65432))
server.listen()
print("Server is listening on port 65432...")
threading.Thread(target=backup_loop, daemon=True).start()

while True:
    conn, addr = server.accept()
    ip = addr[0]

    if is_ip_banned(ip):
        print(f"Rejected banned IP {ip}")
        conn.close()
        continue

    if IP_CONNECTION_COUNT[ip] >= MAX_CONNECTIONS_PER_IP:
        print(f"Too many connections from {ip}, banning")
        ban_ip(ip)
        conn.close()
        continue

    IP_CONNECTION_COUNT[ip] += 1 

    t = threading.Thread(target=dispatch_client, args=(conn, addr))
    t.start()
