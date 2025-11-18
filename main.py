import hashlib as hl
import os
import json
import time
import watchdog.events
import watchdog.observers
import dotenv

dotenv.load_dotenv()
# size of chunks to read when hashing files
block_size = int(os.getenv("block_size"))


HASH_PATH = os.getenv("hash_path")
_IGNORE_FILENAME = os.path.basename(HASH_PATH)
CONFIG_PATH = ".env"


def _file_hash(path):
    h = hl.sha256()
    try:
        with open(path, "rb") as f:
            for blk in iter(lambda: f.read(block_size), b""):
                h.update(blk)
        return h.hexdigest()
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        return None


def calc_of_hash(path):
    try:
        if os.path.isdir(path):
            sha = hl.sha256()
            base = os.path.abspath(path)
            for root, dirs, files in os.walk(base):
                dirs.sort()
                files.sort()
                for d in dirs:
                    rel = os.path.relpath(os.path.join(root, d), base).replace(os.sep, "/").encode("utf-8")
                    sha.update(b"DIR:" + rel + b"\0")
                for fname in files:
                    full = os.path.join(root, fname)
                    fh = _file_hash(full)
                    rel = os.path.relpath(full, base).replace(os.sep, "/").encode("utf-8")
                    if fh is None:
                        sha.update(b"FILE-ERR:" + rel + b"\0")
                    else:
                        sha.update(b"FILE:" + rel + b"\0" + bytes.fromhex(fh))
            return sha.hexdigest()
        else:
            return _file_hash(path)
    except (FileNotFoundError, PermissionError):
        return None


def read_index():
    index = {}
    try:
        with open(HASH_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    loc = obj.get("Location")
                    h = obj.get("Hash")
                    if loc is not None:
                        index[loc] = h
                except json.JSONDecodeError:
                    # skip bad lines
                    continue
    except FileNotFoundError:
        pass
    return index


def write_index(index):
    tmp = HASH_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for loc, h in sorted(index.items()):
            json.dump({"Location": loc, "Hash": h}, f, ensure_ascii=False)
            f.write("\n")
    os.replace(tmp, HASH_PATH)


def upsert_entry(location, hash_value):
    idx = read_index()
    idx[location] = hash_value
    write_index(idx)


def remove_entry(location):
    idx = read_index()
    if location in idx:
        idx.pop(location)
        write_index(idx)

class WatcherHandler(watchdog.events.FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            print(f"File modified: {event.src_path}")
            new_hash = calc_of_hash(event.src_path)
            print(f"New hash: {new_hash}")
            upsert_entry(event.src_path, new_hash)

    def on_created(self, event):
        if not event.is_directory:
            print(f"File created: {event.src_path}")
            h = calc_of_hash(event.src_path)
            print(f"sha256: {h}")
            upsert_entry(event.src_path, h)

    def on_deleted(self, event):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")
            print("Hash: N/A")
            remove_entry(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            print(f"File moved from {event.src_path} to {event.dest_path}")
            # remove old entry and add new one (dest might not be readable yet)
            remove_entry(event.src_path)
            new_hash = calc_of_hash(event.dest_path)
            print(f"New hash: {new_hash}")
            upsert_entry(event.dest_path, new_hash)




# ignore config.json and config.json.tmp (case-insensitive on Windows)
_IGNORE_FILENAME = os.path.basename(HASH_PATH)
_IGNORE_FILENAMES = { _IGNORE_FILENAME, _IGNORE_FILENAME + ".tmp" }
_IGNORE_FILENAMES_NORM = { os.path.normcase(x) for x in _IGNORE_FILENAMES }

_original_dispatch = watchdog.events.FileSystemEventHandler.dispatch

def _dispatch_filtered(self, event):
    try:
        path = getattr(event, "src_path", None) or getattr(event, "dest_path", None)
        if path:
            bname = os.path.basename(path)
            if os.path.normcase(bname) in _IGNORE_FILENAMES_NORM:
                return  # ignore config.json and config.json.tmp
    except Exception:
        pass
    return _original_dispatch(self, event)

watchdog.events.FileSystemEventHandler.dispatch = _dispatch_filtered


if __name__ == "__main__":
    path = "."  # Watch current directory
    event_handler = WatcherHandler()
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    print(f"Watching directory {os.path.abspath(path)} ...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
