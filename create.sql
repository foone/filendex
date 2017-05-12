create table files(fileid integer primary key, path, ext, inside, size, file_type, mtime, ctime, hash_md5, hash_sha1, hash_sha256);
create unique index path_index on files(path);