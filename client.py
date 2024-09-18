#!/usr/bin/env python

import ao
import mad
import readline
import socket
import struct
import sys
import threading

import os

from time import sleep

SEND_BUFFER     = 4096

# The Mad audio library we're using expects to be given a file object, but
# we're not dealing with files, we're reading audio data over the network.  We
# use this object to trick it.  All it really wants from the file object is the
# read() method, so we create this wrapper with a read() method for it to
# call, and it won't know the difference.
# NOTE: You probably don't need to modify this class.
class mywrapper(object):
    def __init__(self):
        self.mf = None
        self.data = ""
        self.finished_receiving = False

    # When it asks to read a specific size, give it that many bytes, and
    # update our remaining data.
    def read(self, size):
        result = self.data[:size]
        self.data = self.data[size:]
        return result


# Receive messages.  If they're responses to info/list, print
# the results for the user to see.  If they contain song data, the
# data needs to be added to the wrapper object.  Be sure to protect
# the wrapper with synchronization, since the other thread is using
# it too!
def recv_thread_func(wrap, cond_filled, sock):
    lock_aquired = False
    collected = 0
    leftover = ""
    cond_filled.acquire()
    while True:
        data = ""
        data += leftover
        leftover = ""
        music_data = ""

        while True:
            try:
                cur_recv = sock.recv(500)
                data += cur_recv
                if len(cur_recv) < 500:
                    break
            except:
                if not(len(data)):
                    data = None
                break

        if not(data):
            continue

        messages = data.split("\r\n\r\n")

        if len(messages[-1]):
            leftover = messages[-1]
            messages = messages[:-1]

        messages = [msg for msg in messages if len(msg)]
        for message in messages:
            tokens = message.split("\r\n", 1)
            if not(tokens):
                continue

            tokens = [tok for tok in tokens if len(tok)]
            if len(tokens) == 0:
                break

            resp_line = tokens[0]

            if resp_line == "10":
                cond_filled.release()
            elif resp_line == "11":
                if len(tokens) > 1:
                    sys.stdout.write(tokens[1])
                    sys.stdout.flush()
                continue
            elif resp_line == "12":
                if len(tokens) > 1:

                    cond_filled.acquire()
                    wrap.finished_receiving = False
                    cond_filled.release()
                    music_data += tokens[1]

                    collected += 1

            elif resp_line == "14":
                cond_filled.acquire()
                wrap.finished_receiving = True
                cond_filled.release()

            elif resp_line == "13":
                pass

            elif resp_line == "20":
                sys.stdout.write("ERROR 20: Song ID not found!\n")
                sys.stdout.flush()

            else:
                continue

        cond_filled.acquire()
        wrap.data += music_data
        cond_filled.release()


# If there is song data stored in the wrapper object, play it!
# Otherwise, wait until there is.  Be sure to protect your accesses
# to the wrapper with synchronization, since the other thread is
# using it too!
def play_thread_func(wrap, cond_filled, dev):
    while True: 
        if wrap.mf is None:
            continue
        
        if len(wrap.data) < 500 and not(wrap.finished_receiving):
            continue

        cond_filled.acquire()
        buf = wrap.mf.read()
        cond_filled.release()

        while buf is None:
            cond_filled.acquire()
            buf = wrap.mf.read()
            cond_filled.release()

        if buf is None:
            continue

        dev.play(buffer(buf), len(buf))
           


def main():
    if len(sys.argv) < 3:
        print 'Usage: %s <server name/ip> <server port>' % sys.argv[0]
        sys.exit(1)

    # Create a pseudo-file wrapper, condition variable, and socket.  These will
    # be passed to the thread we're about to create.
    wrap = mywrapper()
    
    # Create a condition variable to synchronize the receiver and player threads.
    # In python, this implicitly creates a mutex lock too.
    # See: https://docs.python.org/2/library/threading.html#condition-objects
    cond_filled = threading.Condition()
    # Create a TCP socket and try connecting to the server.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((sys.argv[1], int(sys.argv[2])))

    # Create a thread whose job is to receive messages from the server.
    recv_thread = threading.Thread(
        target=recv_thread_func,
        args=(wrap, cond_filled, sock)
    )
    recv_thread.daemon = True
    recv_thread.start()

    # Create a thread whose job is to play audio file data.
    dev = ao.AudioDevice('pulse')

    play_thread = threading.Thread(
        target=play_thread_func,
        args=(wrap, cond_filled, dev)
    )
    play_thread.daemon = True
    play_thread.start()

    req = ""
    req += "SETUP\r\n"
    req += "\r\n"
    sock.send(req)
    cond_filled.acquire()
    cond_filled.release()

    # Enter our never-ending user I/O loop.  Because we imported the readline
    # module above, raw_input gives us nice shell-like behavior (up-arrow to
    # go backwards, etc.).
    while True:
        line = raw_input('>> ')
        args = None
        if ' ' in line:
            cmd, args = line.split(' ', 1)
        else:
            cmd = line

        req = ""

        # TODO: Send messages to the server when the user types things.
        if cmd in ['l', 'list']:
            print 'The user asked for list.'
            req += "LIST\r\n"
            req += "\r\n"
            sock.send(req)

        if cmd in ['p', 'play']:
            print 'The user asked to play:', args
            req += "PLAY\r\n"
            req += str(args) + "\r\n"
            req += "\r\n"
            cond_filled.acquire()
            wrap.mf = mad.MadFile(wrap)
            wrap.data = ""
            cond_filled.release()
            sock.send(req)

        if cmd in ['s', 'stop']:
            print 'The user asked for stop.'
            req += "STOP\r\n"
            req += "\r\n"
            cond_filled.acquire()
            wrap.data = ""
            cond_filled.release()
            sock.send(req)

        if cmd in ['quit', 'q', 'exit']:
            req = ""
            req += "TEARDOWN\r\n"
            req += "\r\n"
            sock.send(req)
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
            sys.exit(0)
            

if __name__ == '__main__':
    main()
