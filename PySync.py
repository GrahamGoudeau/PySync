import argparse
import sys
#import dir_manager
import sync_manager

default_thread_max = 1000

def parse_args():
    parser = argparse.ArgumentParser(description='Directory syncing')

    parser.add_argument('-s', dest='sync_dirs', help='List of directories to sync', nargs='+')

    parser.add_argument('-t', dest='thread_max', type=int, default=default_thread_max, help='Max number of threads; default is 1000; > 0')

    args = parser.parse_args()
    if args.sync_dirs is None or args.thread_max < 1:
        parser.print_help()
        sys.exit(1)

    return args

def main():
    args = parse_args()
    '''
    manager = dir_manager.Dir_Manager(args.sync_dirs, daemon_mode=True)
    manager.sync()
    '''
    manager = sync_manager.Sync_Manager(args.sync_dirs, daemon_mode=True)
    manager.sync()

if __name__ == '__main__':
    main()
