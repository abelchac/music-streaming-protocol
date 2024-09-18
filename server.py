#!/usr/bin/env python

import os
import socket
import struct
import sys
from threading import Lock, Thread


QUEUE_LENGTH    = 10
SEND_BUFFER     = 4096


IDLE            = -1
SETUP           = 0
PLAY            = 1
STOP            = 2
LIST            = 3
TEARDOWN        = 4


# per-client struct
class Client:
    def __init__(self, conn, addr, songs, songlist, musicdir):
        self.lock = Lock()

        self.conn = conn
        self.addr = addr

        self.songs = songs
        self.songlist = songlist

        self.iden = -1

        self.state = -1
        self.prev_state = -1

        self.song_pos = 0

        self.musicdir = musicdir

        self.list_pos = -1



# TODO: Thread that sends music and lists to the client.  All send() calls
# should be contained in this function.  Control signals from client_read could
# be passed to this thread through the associated Client object.  Make sure you
# use locks or similar synchronization tools to ensure that the two threads play
# nice with one another!
def client_write(client):
    conn = client.conn
    addr = client.addr
    file = None 
    while True:
        while True:

            client.lock.acquire()
            state = client.state
            client.lock.release()

            response = ""

            if state is SETUP:
                client.lock.acquire()
                client.state = IDLE
                client.lock.release()

                response += "10\r\n"
                response += "\r\n"
                break
                        
            elif state is PLAY:
                client.lock.acquire()
                if client.song_pos != -1:
                    
                    path = os.path.join(client.musicdir, client.songs[client.iden])
                    if client.song_pos == 0:
                        file = open(path, 'r')

                    bytes_to_send = SEND_BUFFER - (sys.getsizeof(response) + sys.getsizeof("\r\n\r\n"))
                    data = file.read(bytes_to_send)

                    if len(data) == 0:
                        client.state = IDLE
                        response += "14"
                    else:
                        response += "12\r\n"
                    
                    response += data
                    client.song_pos += bytes_to_send

                    response += "\r\n"
                        
                else:
                    client.state = IDLE
                    client.song_pos = 0
                    response += "20\r\n"
                
                response += "\r\n"

                if client.list_pos != -1:
                    client.state = LIST

                client.lock.release()
                break

            elif state is STOP:
                client.lock.acquire()
                client.state = IDLE
                if file:
                    file.close()
                    file = None
                client.lock.release()

                response += "13\r\n"
                response += "\r\n"
                break

            elif state is LIST:
                client.lock.acquire()

                if client.list_pos == -1:
                    client.state = IDLE
                    client.lock.release()
                    continue
                
                if client.prev_state == PLAY:
                    client.state = client.prev_state
                
                response += "11\r\n"
                if client.list_pos == len(client.songlist):
                    client.list_pos = -1
                    response += "\r\n"
                    client.lock.release()
                    break

                response += client.songlist[client.list_pos] + "\r\n"
                client.list_pos += 1
                response += "\r\n"

                client.lock.release()
                break

            elif state is TEARDOWN:
                return

            else:
                continue

        conn.send(response)

# TODO: Thread that receives commands from the client.  All recv() calls should
# be contained in this function.
def client_read(client):
    conn = client.conn
    addr = client.addr
    while True:

        data = conn.recv(SEND_BUFFER)
        if not(data):
            continue

        tokens = data.split(b"\r\n")
        tokens = [tok.decode("utf-8") for tok in tokens if (len(tok))]
        req_line = tokens[0]

        client.lock.acquire()
        client.prev_state = client.state
        if req_line == "SETUP":
            client.state = SETUP

        elif req_line == "PLAY":
            client.state = PLAY
            try:
                client.iden = int(tokens[1])
            except:    
                client.iden = -1

            if not(client.iden in range(len(client.songs))):
                client.song_pos = -1
            else:
                client.song_pos = 0

        elif req_line == "STOP":
            client.state = STOP

        elif req_line == "LIST":
            client.state = LIST
            client.list_pos = 0

        elif req_line == "TEARDOWN":
            client.state = TEARDOWN
            conn.shutdown(socket.SHUT_RDWR)
            conn.close()
            client.lock.release()

            break

        client.lock.release()

    #conn.close()



def get_mp3s(musicdir):
    print("Reading music files...")
    songs = []
    songlist = []

    for filename in os.listdir(musicdir):
        if not filename.endswith(".mp3"):
            continue

        # TODO: Store song metadata for future use.  You may also want to build
        # the song list once and send to any clients that need it.

        songs.append(filename)

    i = 0
    while True:
        resp_data = ""
        new_line = songs[i] + ": " + str(i) + "\n"
        while (sys.getsizeof(new_line) < SEND_BUFFER - (sys.getsizeof("11\r\n") + sys.getsizeof("\r\n\r\n") + sys.getsizeof(resp_data))):
            resp_data += new_line
            i += 1
            if i == len(songs):
                break
            new_line = songs[i] + ": " + str(i) + "\n"
        songlist.append(resp_data)
        if i == len(songs):
            break
    
    print("Found {0} song(s)!".format(len(songs)))

    return (songs, songlist)

def main():
    if len(sys.argv) != 3:
        sys.exit("Usage: python server.py [port] [musicdir]")
    if not os.path.isdir(sys.argv[2]):
        sys.exit("Directory '{0}' does not exist".format(sys.argv[2]))

    port = int(sys.argv[1])
    songs, songlist = get_mp3s(sys.argv[2])
    threads = []

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', port))
    s.listen(QUEUE_LENGTH)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # TODO: create a socket and accept incoming connections
    while True:
        (conn, addr) = s.accept()
        client = Client(conn, addr, songs, songlist, sys.argv[2])
        t = Thread(target=client_read, args=(client,))
        threads.append(t)
        t.start()
        t = Thread(target=client_write, args=(client,))
        threads.append(t)
        t.start()
    s.close()


if __name__ == "__main__":
    main()