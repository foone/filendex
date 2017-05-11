#!/usr/bin/python
import os, sys, stat, hashlib, subprocess, sqlite3

DATABASE_PATH = 'filendex.sqlite3'
BUFFER_SIZE = 1024*1024 # TODO: configure on command line?
HASHERS='md5 sha1 sha256'.split()

def get_file_type(path):
	try:
		return subprocess.check_output(['/usr/bin/file', '-b', path]).strip()
	except subprocess.CalledProcessError:
		return None # Yes, file can fail. Computers are hard

def get_file_hashes(path, size):
	if size == 0:
		return EMPTYFILE
	with open(path, 'rb') as f:
		hashers = {}
		for algo in HASHERS:
			hashers[algo] = hashlib.new(algo)
		while True:
			data = f.read(BUFFER_SIZE)
			if data == '':
				break
			for hasher in hashers.values():
				hasher.update(data)
		# Replace hashing object with its hash
		for algo, hasher in hashers.items():
			hashers[algo] = hasher.hexdigest()
		return hashers

def record_file(row):
	sql='insert into files({}) values({})'.format(
		','.join(row.keys()),
		','.join('?'*len(row))
	)
	try:
		with conn as cur:
			cur.execute(sql, row.values())
	except sqlite3.IntegrityError:
		pass # Silently skip missing files
		# TODO: add an option to print these files or error?

EMPTYFILE={}
for algo in HASHERS:
	EMPTYFILE[algo] = hashlib.new(algo).hexdigest()

basepath = os.path.abspath(sys.argv[1])

conn = sqlite3.connect(DATABASE_PATH)
conn.text_factory = str # linux filesystem encoding is a mess. we'll handle it later, in the GUI
with conn as cur:
	try:
		cur.execute('select path from files limit 1')
	except sqlite3.OperationalError:
		with open('create.sql','rb') as f:
			cur.executescript(f.read())



for dirpath, dirnames, filenames in os.walk(basepath):
	for filename in filenames:
		row = {
			'inside': None # We're at filesystem level, not inside any archives
		}
		row['path'] = path = os.path.join(dirpath, filename)
		print path
		# TODO: Precheck files (locally or remotely?) before hashing, so we don't waste time rehashing
		info = os.lstat(path)
		if stat.S_ISLNK(info.st_mode):
			continue # don't include symlinks
			# TODO: is this the best option?
		row['size'] = size = info.st_size
		row['mtime'] = int(info.st_mtime)
		row['ctime'] = int(info.st_ctime)


		for algo, digest in get_file_hashes(path, size).items():
			row['hash_' + algo] = digest

		row['file_type'] = get_file_type(path)

		try:
			record_file(row)
		except:
			print row
			raise