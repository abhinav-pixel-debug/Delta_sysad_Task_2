import socket 
import threading
import json
import sqlite3
import hashlib
import wave
import os
import time


SESSIONS={}
class UserState:
    def __init__(self,user_id):
        self.session_id=str(user_id)
        self.user_id=user_id
        self.current_track_id=None
        self.playback_position=0
        self.queue=[]#MOSTLY WE WILL NOT NEED IT 
        self.playing=False
        self.paused=False
        self.buffer_health=0
        self.conn=None#For audio connection only



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
        print(row)
        if row is None:
            return{
                "status":False,
                "message":"User not found"
            }
        user_id, store_password=row
        if check_password(password,store_password):
            print("Okay password")
            return{
                "status":True,
                "message":user_id
            }    
        else:
            print("Wrong password")
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


music_dir="music_streaming/music"

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
        # fullpath=os.path.join(music_dir,filepath)
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
            except Exception:
                break
            user_state.playback_position+=1
            data=wf.readframes(chunk_size)

# def get_playlists(user_state):



def process_command(message,auth,user_state,conn):
    mess_list=message.split()
    if not auth:
        if len(mess_list)==3:
            if mess_list[0]=="LOGIN":
                result = login_user(mess_list[1], mess_list[2])
                if result["status"]:
                    user_id=result["message"]
                    if str(user_id) in SESSIONS.keys() :
                        user_state=SESSIONS[str(user_id)]

                    else:
                        user_state=UserState(user_id)
                        SESSIONS[user_state.session_id]=user_state

                    return result, result["status"],user_state
                return result, result["status"], user_state

            elif mess_list[0]=="REGISTER":
                return create_user(mess_list[1],mess_list[2]), False,user_state

        return{
            "status":False,
            "message":"Invalid input"
        },auth,user_state
    else: 
        # if mess_list[0]=="GET_PLAYLIST":
        #     #FUNCTION HERE WHICH COMMUNICATES WITH THE DB AND VERIFIES IT 
        if mess_list[0]=="PLAY":
            if len(mess_list) < 2:
                return {
                    "status": False,
                    "message": "No track id provided"
                }, auth, user_state

            try:
                track_id = int(mess_list[1])
            except ValueError:
                return {
                    "status": False,
                    "message": "Track id must be an integer"
                }, auth, user_state

            user_state.current_track_id = track_id
            user_state.playback_position = 0
            user_state.playing = True
            user_state.paused = False

            return {
                "status": True,
                "message": f"Started streaming track {track_id}"
            }, auth, user_state
         
        elif mess_list[0]=="PAUSE":
            if not user_state.playing:
                return{
                    "status":False,
                    "message":"Nothing is playing"
                },auth, user_state
            user_state.paused=True
            return{
                "status":True,
                "message":"Paused"
            },auth, user_state

        elif mess_list[0]=="RESUME":
            if not user_state.playing:
                return{
                    "status":False,
                    "message":"Nothing is playing"
                },auth, user_state
            if not user_state.paused:
                return {
                    "status": False,
                    "message": "Already playing"
                }, auth, user_state

            user_state.paused = False
            return {
                "status": True,
                "message": "Resumed"
            }, auth, user_state
       
        elif mess_list[0]=="EXIT":
            return {
                "status":True,
                "message":"Goodbye"
            },False,user_state

        return{
            "status":False,
            "message":"Invalid input"
        },auth,user_state

    


def handle_client(conn, addr):
    print(f"Connected by {addr}")
    auth=False
    user_state=None
    while True:
        data = conn.recv(1024).decode()
        if not data:
            break
        message,auth,user_state=process_command(data,auth,user_state,conn)
        conn.sendall(json.dumps(message).encode()) 
    conn.close()
    print(f"Connection closed by {addr}")

def handle_audio_client(conn, addr, first_line):
    print(f"[AUDIO] Connected by {addr}")

    parts = first_line.split()
    if len(parts) < 2:
        conn.close()
        return

    user_id = parts[1]  # AUDIO <user_id>
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

# def dispatch_client(conn, addr):
#     try:
#         first = conn.recv(1024).decode().strip()
#         if first.startswith("CONTROL"):
#             handle_client(conn, addr)
#         elif first.startswith("AUDIO"):
#             handle_audio_client(conn, addr, first)
#         else:
#             print(f"Unknown connection type from {addr}: {first}")
#             conn.close()
#     except Exception as e:
#         print(f"Error in dispatch_client: {e}")
#         conn.close()


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

while True:
    conn, addr = server.accept()
    thread = threading.Thread(target=dispatch_client, args=(conn, addr))
    thread.start()


