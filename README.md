
# Delta Sysad Task 2

Terminal-based music streaming system using a TCP client–server in Python. The threaded server streams audio files from a music directory to multiple clients while a TUI client offers Play, Pause, Resume,Exit etc. controls. Users must authenticate; passwords are hashed and stored in a raw-SQL SQLite database with tables for users, songs, artists, albums, playlists, and listening history.Background task periodically backs up the database to a persistent folder. Each listener has a UserState tracking session ID, current track, playback position, queue, and a simple buffer-health metric, supporting reconnection by session ID. The server also enforces IP-based connection rate limiting and brute-force protection via an Active_Bans table that records blocked IPs and ban expiry times.



## Features

- **TCP client–server streaming**  
  - TUI client connects to the music server over a persistent TCP socket.  
  - Separate control and audio connections: control commands (LOGIN, PLAY, PAUSE, etc.) over one socket, raw audio stream over a dedicated audio socket.

- **Terminal User Interface (TUI)**  
  - Login / register prompts in the terminal.  
  - Menu options for Play, Pause, Resume, Exit, and playlist-related actions.  
  - Prevents double-play by checking if an audio thread is already running.

- **Audio playback with PyAudio**  
  - Client receives raw PCM audio over TCP and plays it using PyAudio.  
  - Uses fixed audio parameters (16‑bit, stereo, 44.1 kHz, 4096‑frame chunks) for simple, consistent playback.

- **Playlists and song browsing**  
  - Create new playlists from the TUI.  
  - List all playlists with their IDs.  
  - View songs in a selected playlist.  
  - Search songs by name and display song ID, title, and artist.  
  - Add songs to a playlist by playlist ID and song ID.

- **Listening history**  
  - Display a user’s listening history with listened time, title, song ID, and artist.  

- **Threaded playback**  
  - Playback runs in a daemon thread so the TUI remains responsive while audio is streaming.

## Deployment

## Deployment / Running the Project

1. **Project setup**

   - Download all files into a folder named `music_streaming`.

2. **Initialize the database**

   From the project root, run:

   ```bash
   python3 db.py
   ```

   After running this command, you must manually insert data into the database tables  
   (users, songs, artists, albums, file paths, etc.) for the program to work correctly.

3. **Start the server**

   From the project root, run:

   ```bash
   python3 music_streaming/server/server.py
   ```

4. **Start the client**

   In another terminal, run:

   ```bash
   python3 music_streaming/client/client.py
   ```