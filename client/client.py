import socket
import json
import pyaudio
import threading
client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect(('localhost', 65432))

client.sendall("CONTROL".encode())


handshake = json.loads(client.recv(1024).decode())
print(handshake["message"])
print("Connected to the server.Please verify your credentials.\n")


def send_command(command):
    client.sendall(command.encode())
    response=json.loads(client.recv(1024).decode())
    return response


#The TUI starts here

def auth():
    while True:
        print("1.Type [1] for Login \n")
        print("2.Type [2] for cretae account \n")
        print("3.Type [3] for exit \n")
        option=input('Your choice:\n').strip()

        if option=='1':
            username=input('Enter your username:\n')
            password=input('Enter your password:\n')
            response=send_command(f"LOGIN {username} {password}")
            if response["status"]:
                print("Login successful")
                return response["message"]
            else:
                print(response["message"])

        elif option.strip()=='2':
            username=input('Enter your username:\n')
            password=input('Enter your password:\n')
            response=send_command(f"REGISTER {username} {password}")
            if response["status"]:
                print(response["message"])
            else:
                print(response["message"])

        elif option.strip()=='3':
            print("Bye")
            return None
        
        else :
            print("Invalid option")


def play_with_pyaudio(user_id, track_id):

    resp = send_command(f"PLAY {track_id}")
    print(resp['message'])

    audio_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    audio_sock.connect(('localhost', 65432))
    audio_sock.sendall(f"AUDIO {user_id}\n".encode())

    CHUNK = 4096
    FORMAT = pyaudio.paInt16
    CHANNELS = 2
    RATE = 44100

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    output=True,
                    frames_per_buffer=CHUNK)

    try:
        while True:
            data = audio_sock.recv(CHUNK * CHANNELS * 2)
            if not data:
                break
            stream.write(data)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
        audio_sock.close()

audio_thread = None


def menu(user_id):
    audio_thread = None

    while True:
        print("1. Play")
        print("2. Pause")
        print("3. Resume")
        print("4. Create Playlist")
        print("5. Show Playlists")
        print("6. Show songs in playlist")
        print("7. Search song")
        print("8. Add song to playlist")
        print("9. Listening History")
        print("10. Exit")
        choice = input("Choice: ").strip()
        if choice == '1':
            if audio_thread and audio_thread.is_alive():
                print("Audio is already playing")
                continue

            track_id = input("Track id: ").strip()
            audio_thread = threading.Thread(
                target=play_with_pyaudio,
                args=(user_id, track_id),
                daemon=True
            )
            audio_thread.start()
        elif choice=='2':
            resp=send_command("PAUSE")
            print(resp['message'])
        elif choice=='3':
            resp=send_command("RESUME")
            print(resp['message'])
        elif choice=='4':
            name=input("Enter the name of playlist:")
            resp=send_command(f"CREATE {name}")
            print(resp[message])

        elif choice == '5':
            resp = send_command("SHOW")

            if resp["status"]:
                print(resp["message"])
                for row in resp["data"]:
                    print(f"Playlist Name: {row['name']} | Playlist ID: {row['playlist_id']}")
            else:
                print(resp["message"])
  
        elif choice=='6':
            id=input("Enter playlist id:")
            resp=send_command(f"LIST {id}")
            if resp["status"]:
                print(resp["message"])
                print(resp['data'])
                for row in resp["data"]:
                    print(f"Song name: {row['title']} | Song ID: {row['song_id']}" )
            else:
                print(resp["message"])
        elif choice=='7':
            song=input("Enter the name of the song:").lower()
            resp=send_command(f"SEARCH {song}")
            if resp["status"]:
                print(resp["message"])
                for row in resp["data"]:
                    print(f"Song ID: {row['song_id']} | Title: {row['title']} | Artist: {row['artist_name']}")
            else:
                print(resp["message"])
        elif choice=='8':
            p_id=input("Enter playlist id:")
            s_id=input("Enter song id:")
            resp=send_command(f"ADD {p_id} {s_id}")
            print(resp["message"])
        elif choice=='9':
            resp=send_command("HISTORY")
            if resp["status"]:
                print(resp["message"])
                for row in resp["data"]:
                    print(f"Listened At: {row['listened_at']}| Title: {row['title']} | Song ID: {row['song_id']} | Artist: {row['artist_name']}")
            else:
                print(resp["message"])       
        elif choice=='10':
            resp=send_command("EXIT")
            print(resp['message'])
            break
        else:
            print("Invalid option")


def main():
    while True:
        user_id=auth()
        if user_id is None:
            break
        menu(user_id)



if __name__=="__main__":
    main()


