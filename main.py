#!/usr/bin/env python3
import datetime
import signal
import sys
import threading
from os import mkdir
from time import process_time, sleep

from bottle import route, run, template, HTTPError
from daqhats import HatIDs, OptionFlags, SourceType, hat_list, mcc172

board0 = mcc172(0)
board1 = mcc172(1)

class Axis:
    def __init__(self, board, channel):
        self.board = board
        self.channel = channel

x = Axis(board0, 0)
y = Axis(board0, 1)
z = Axis(board1, 0)

sample_rate = 10000
fetch_time = 5
buffer_size = sample_rate * fetch_time

print('Writing sensitivities')
x.board.a_in_sensitivity_write(x.channel, 9.764)
y.board.a_in_sensitivity_write(y.channel, 10.16)
z.board.a_in_sensitivity_write(z.channel, 9.899)

print('Turning on IEPE power')
x.board.iepe_config_write(x.channel, 1)
y.board.iepe_config_write(y.channel, 1)
z.board.iepe_config_write(z.channel, 1)

print('Syncing clocks')
# slaves go first
board1.a_in_clock_config_write(SourceType.SLAVE, sample_rate)
board0.a_in_clock_config_write(SourceType.MASTER, sample_rate)

# wait for clock sync
while board0.a_in_clock_config_read().synchronized != True:
    sleep(0.005)
while board1.a_in_clock_config_read().synchronized != True:
    sleep(0.005)
print('Clocks synced')

stopped = False
thread = None

def start_scan(run_id):
    while not stopped:
        data0 = board0.a_in_scan_read(-1, 0) # read all samples available
        print('Board 0: running {}, hw overrun {}, buffer overrun {}, triggered {}, timeout {}'.format(
            data0.running, data0.hardware_overrun, data0.buffer_overrun, data0.triggered, data0.timeout
        ))
        x = data0.data[0::2]
        y = data0.data[1::2]
        print(len(data0.data), len(x), len(y))

        data1 = board1.a_in_scan_read(-1, 0) # read all samples available
        print('Board 1: running {}, hw overrun {}, buffer overrun {}, triggered {}, timeout {}'.format(
            data1.running, data1.hardware_overrun, data1.buffer_overrun, data1.triggered, data1.timeout
        ))
        print(len(data1.data))
        z = data1.data

        start = process_time()
        with open('data/{}/{}'.format(run_id, datetime.datetime.now().isoformat()), 'w') as output:
            output.write(str(x)[1:-1])
            output.write('\n')
            output.write(str(y)[1:-1])
            output.write('\n')
            output.write(str(z)[1:-1])
            output.write('\n')

        print('Writing took {} sec'.format(process_time() - start))
        # if len(data1.data) > 0:
        #     print('{} {} {}... len={}'.format(data1.data[0], data1.data[1], data1.data[2], len(data1.data)))
        # else:
        #     print('empty')
        print()

        sleep(fetch_time/2)

def stop_scan(sig, frame):
    board0.a_in_scan_stop()
    board1.a_in_scan_stop()
    sys.exit(0)

signal.signal(signal.SIGINT, stop_scan)

@route('/start/<test>')
def start(test):
    global thread
    global stopped
    if thread != None:
        raise HTTPError(400, {'error': 'thread already running'})

    run_id = test + '-' + datetime.datetime.now().isoformat()
    mkdir('data/{}'.format(run_id))

    board0.a_in_scan_start(0b11, buffer_size, OptionFlags.CONTINUOUS)
    board1.a_in_scan_start(0b01, buffer_size, OptionFlags.CONTINUOUS)

    stopped = False
    thread = threading.Thread(target = start_scan, args = (run_id,))
    thread.start()
    return 'ok'

@route('/stop')
def stop():
    global thread
    global stopped
    stopped = True
    thread.join()
    thread = None

    board0.a_in_scan_stop()
    board1.a_in_scan_stop()

    board0.a_in_scan_cleanup()
    board1.a_in_scan_cleanup()
    return 'stopped'


run(host='0.0.0.0', port=8080)
