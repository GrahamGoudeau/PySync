import os
import sys
import time
import threading
import datetime
import collections
import hashlib

class Sync_Manager:
    def __init__(self, directories, time_delay=1, daemon_mode=False, thread_limit=1000):
        self.sync_dirs = [os.path.abspath(dir) for dir in directories]

        # check if we are trying to sync a parent directory with its child
        for dir in self.sync_dirs:
            other_dirs = [other_dir for other_dir in self.sync_dirs if other_dir is not dir]

            # combine the other dirs into one string that we can check for substring containment
            combined = '\n'.join(other_dirs)
            if dir in combined:
                raise ValueError('Cannot sync a parent directory with a child directory')

        self.time_delay = time_delay
        self.daemon_mode = daemon_mode
        #self.work_queue = collections.deque([])
        self.work_queues = {}
        self.sync_log = {}
        self.report_lock = threading.Semaphore(1)

    def report(self, message):
        with self.report_lock:
            print '-REPORT- ' + message

    def get_dirs_files(self, directory):
        contents = os.listdir(directory)
        dirs = [item for item in contents if os.path.isdir(os.path.join(directory, item))]
        files = [item for item in contents if item not in dirs]

        return (dirs, files)

    def sync(self):
        # used to prevent fetching content from yourself
        for id in range(1, len(self.sync_dirs) + 1):
            self.work_queues[id] = collections.deque([])

        dir_id = 1
        for dir in self.sync_dirs:
            serve_thread = threading.Thread(target=self._dir_serve_loop, args=[dir, dir_id])
            serve_thread.daemon = self.daemon_mode

            fetch_thread = threading.Thread(target=self._dir_fetch_loop, args=[dir, dir_id])
            fetch_thread.daemon = self.daemon_mode

            serve_thread.start()
            fetch_thread.start()
            dir_id += 1

        while True:
            time.sleep(60)

    def _broadcast(self, self_id, message):
        for key in self.work_queues.keys():
            if key != self_id:
                self.work_queues[key].append(message)

    def _dir_serve_loop(self, directory, dir_id):
        # http://stackoverflow.com/questions/237079/how-to-get-file-creation-modification-date-times-in-python
        def _is_updated(dir_filename, filename, file_digests):
            with open(dir_filename, 'r') as f:
                md5 = hashlib.new('md5')
                md5.update(f.read())
                new_hash = md5.hexdigest()

            old_hash = file_digests.get(filename, None)

            updated = old_hash is None or old_hash != new_hash
            file_digests[filename] = new_hash
            #print filename, 'updated:', updated, old_hash, new_hash
            return updated

        def _serve_file(dir_filename, filename, dir_id):
            self.report('Serving UPDATE ' + filename + ' from ' + dir_filename)

            with open(dir_filename, 'r') as f:
                contents = f.read()
                self._broadcast(dir_id, ('update', filename, dir_id, contents))
                self.sync_log[filename] = datetime.datetime.now()

        def _serve_delete(filename, dir_id):
            self.report('Serving DELETE ' + filename + ' from ' + dir_filename)
            self._broadcast(dir_id, ('delete', filename, dir_id))

        def _update(files, update_time, file_digests, first_update=True):
            new_update_time = None
            file_updated = False
            for file in files:
                dir_filename = directory + '/' + file
                updated = _is_updated(dir_filename, file, file_digests)
                if first_update or updated == True:
                    if not file_updated:
                        new_update_time = datetime.datetime.now()
                        file_updated = True

                    _serve_file(dir_filename, file, dir_id)

            return new_update_time

        def _delete(last_dir_contents, files):
            to_delete = [file for file in last_dir_contents if file not in files]
            for file in to_delete:
                _serve_delete(file, dir_id)

        file_digests = {}
        last_dir_contents = []
        last_update = None
        while True:
            _, files = self.get_dirs_files(directory)
            update_time = datetime.datetime.now() if last_update is None else last_update

            new_update_time = _update(files, update_time, file_digests, first_update=(last_update is None))
            if new_update_time is not None:
                update_time = new_update_time

            _delete(last_dir_contents, files)

            last_update = update_time
            last_dir_contents = files

            time.sleep(self.time_delay)

    def _dir_fetch_loop(self, directory, dir_id):
        def _write_file(directory, filename, contents):
            self.report('Updating ' + filename + ' in ' + directory)

            with open(directory + '/' + filename, 'w') as f:
                f.write(contents)
                self.sync_log[filename] = datetime.datetime.now()

        def _delete_file(directory, filename):
            self.report('Deleting ' + filename + ' in ' + directory)
            if os.path.isfile(directory + '/' + filename):
                try:
                    os.remove(directory + '/' + filename)
                except OSError:
                    return
        def _receive_tuple(work_queue):
            file_tuple = ()
            try:
                if len(work_queue) > 0:
                    file_tuple = work_queue.pop()
            except IndexError:
                return None

            if len(file_tuple) > 0:
                return file_tuple

            return None

        def _handle_update(file_tuple):
            message, filename, new_id, contents = file_tuple
            _write_file(directory, filename, contents)

        def _handle_delete(file_tuple):
            message, filename, new_id = file_tuple
            _delete_file(directory, filename)

        def _dispatch_message(file_tuple):
            message = file_tuple[0]
            if message == 'update':
                _handle_update(file_tuple)
            elif message == 'delete':
                _handle_delete(file_tuple)

        work_queue = self.work_queues[dir_id]
        while True:
            file_tuple = _receive_tuple(work_queue)
            if file_tuple is None:
                continue

            _dispatch_message(file_tuple)
            time.sleep(self.time_delay)
