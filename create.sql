create table files(path, inside, size, file_type, mtime, ctime, hash_md5, hash_sha1, hash_sha256);
create unique index path_index on files(path);