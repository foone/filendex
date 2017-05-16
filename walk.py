#!/usr/bin/python
import os, sys, stat, hashlib, subprocess, sqlite3

DATABASE_PATH = 'filendex.sqlite3'
BUFFER_SIZE = 1024*1024 # TODO: configure on command line?
HASHERS='md5 sha1 sha256'.split()
ARCHIVE_EXTS = """zip iso cab msi bin mdf rar 7z
tar tar.gz tar.bz2 tar.lzma arj arc pak zoo ace lzh sit
lha""".split()
IMAGE_EXTS = """bmp cur dcm gif ico jng jbig jbg jpeg jpg jpe
mng pbm pcx pgm pix pict png pnm ppm psd svg tga tiff tif wmf
xbm xpm""".split()
THUMBNAIL_SIZE = 200
MAXDEPTH = 100

EMPTYFILE={}
for algo in HASHERS:
	EMPTYFILE[algo] = hashlib.new(algo).hexdigest()

def thumbnailify(path, hash256):
	thumb_path = os.path.join('thumbs', '{}.jpeg'.format(hash256))

	subprocess.Popen([
		'convert', '-define',
		'jpeg:size={}x{}'.format(THUMBNAIL_SIZE*2, THUMBNAIL_SIZE*2),
		path + '[0]',
		'-thumbnail','{}x{}'.format(THUMBNAIL_SIZE, THUMBNAIL_SIZE),
		thumb_path,
	]).wait()

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
		cur = conn.cursor()
		with conn:
			cur.execute(sql, row.values())
			cur.close()
		return cur.lastrowid
	except sqlite3.IntegrityError:
		pass # Silently skip missing files
		# TODO: add an option to print these files or error?

def setup_database():
	conn = sqlite3.connect(DATABASE_PATH)
	conn.text_factory = str # linux filesystem encoding is a mess. we'll handle it later, in the GUI
	with conn as cur:
		try:
			cur.execute('select path from files limit 1')
		except sqlite3.OperationalError:
			with open('create.sql','rb') as f:
				cur.executescript(f.read())
	return conn

def is_archive(row):
	return row['ext'] in ARCHIVE_EXTS

def is_image(row):
	return row['ext'] in IMAGE_EXTS

def handle_archive(fileid, path, dirnum):
	target_dir = os.path.join('temp', '{:04}'.format(dirnum))
	os.mkdir(target_dir)
	try:
		subprocess.check_call(['unar', '-r', '-o', target_dir, '-D', '-q', path])
	except subprocess.CalledProcessError:
		# handle error (log somewhere? database?)
		# check that there are files (since the error might be a warning?)
		pass # Continue and process whatever we managed to extract

	try:
		scan_directory(target_dir, dirnum, fileid)
	finally:
		subprocess.check_call(['rm', '-rf', target_dir])


def scan_directory(top_path, dirnum=0, inside=None):
	for dirpath, dirnames, filenames in os.walk(top_path):
		if inside is not None:
			# This is messy, but we need to remove temp/0001
			#Normally and remove components?
			savepath = dirpath[len(top_path)+1:]
		else:
			savepath = dirpath

		for filename in filenames:
			row = {
				'inside': inside
			}
			path = os.path.join(dirpath, filename)
			row['path'] = os.path.join(savepath, filename)
			print row['path']
			row['ext'] = os.path.splitext(path)[1].lower().lstrip('.')
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
				fileid = record_file(row)
			except:
				print row
				raise

			if is_image(row):
				thumbnailify(path, row['hash_sha256'])

			if is_archive(row):
				if dirnum+1 == MAXDEPTH:
					print 'NOT RECURSING, REACHED MAX DEPTH'
				else:
					print 'IS ARCHIVE! RECURSING'
					handle_archive(fileid, path, dirnum+1)




if __name__ == '__main__':

	conn = setup_database()

	basepath = os.path.abspath(sys.argv[1])

	scan_directory(basepath)