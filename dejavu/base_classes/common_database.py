import abc
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import numpy as np
from dejavu.config.settings import (DEFAULT_FS, DEFAULT_OVERLAP_RATIO,
                                    DEFAULT_WINDOW_SIZE)

from dejavu.base_classes.base_database import BaseDatabase


class CommonDatabase(BaseDatabase, metaclass=abc.ABCMeta):
    # Since several methods across different databases are actually just the same
    # I've built this class with the idea to reuse that logic instead of copy pasting
    # over and over the same code.

    def __init__(self):
        super().__init__()

    def before_fork(self) -> None:
        """
        Called before the database instance is given to the new process
        """
        pass

    def after_fork(self) -> None:
        """
        Called after the database instance has been given to the new process

        This will be called in the new process.
        """
        pass

    def setup(self) -> None:
        """
        Called on creation or shortly afterwards.
        """
        with self.cursor() as cur:
            cur.execute(self.CREATE_SONGS_TABLE)
            cur.execute(self.CREATE_FINGERPRINTS_TABLE)
            cur.execute(self.DELETE_UNFINGERPRINTED)

    def empty(self) -> None:
        """
        Called when the database should be cleared of all data.
        """
        with self.cursor() as cur:
            cur.execute(self.DROP_FINGERPRINTS)
            cur.execute(self.DROP_SONGS)

        self.setup()

    def delete_unfingerprinted_songs(self) -> None:
        """
        Called to remove any song entries that do not have any fingerprints
        associated with them.
        """
        with self.cursor() as cur:
            cur.execute(self.DELETE_UNFINGERPRINTED)

    def get_num_songs(self) -> int:
        """
        Returns the song's count stored.

        :return: the amount of songs in the database.
        """
        with self.cursor(buffered=True) as cur:
            cur.execute(self.SELECT_UNIQUE_SONG_IDS)
            count = cur.fetchone()[0] if cur.rowcount != 0 else 0

        return count

    def get_num_fingerprints(self) -> int:
        """
        Returns the fingerprints' count stored.

        :return: the number of fingerprints in the database.
        """
        with self.cursor(buffered=True) as cur:
            cur.execute(self.SELECT_NUM_FINGERPRINTS)
            count = cur.fetchone()[0] if cur.rowcount != 0 else 0

        return count

    def set_song_fingerprinted(self, song_id):
        """
        Sets a specific song as having all fingerprints in the database.

        :param song_id: song identifier.
        """
        with self.cursor() as cur:
            cur.execute(self.UPDATE_SONG_FINGERPRINTED, (song_id,))

    def get_songs(self) -> List[Dict[str, str]]:
        """
        Returns all fully fingerprinted songs in the database

        :return: a dictionary with the songs info.
        """
        with self.cursor(dictionary=True) as cur:
            cur.execute(self.SELECT_SONGS)
            return list(cur)

    def get_song_by_id(self, song_id: int) -> Dict[str, str]:
        """
        Brings the song info from the database.

        :param song_id: song identifier.
        :return: a song by its identifier. Result must be a Dictionary.
        """
        with self.cursor(dictionary=True) as cur:
            cur.execute(self.SELECT_SONG, (song_id,))
            return cur.fetchone()

    def insert(self, fingerprint: str, song_id: int, offset: int):
        """
        Inserts a single fingerprint into the database.

        :param fingerprint: Part of a sha1 hash, in hexadecimal format
        :param song_id: Song identifier this fingerprint is off
        :param offset: The offset this fingerprint is from.
        """
        with self.cursor() as cur:
            cur.execute(self.INSERT_FINGERPRINT, (fingerprint, song_id, offset))

    @abc.abstractmethod
    def insert_song(self, song_name: str, file_hash: str, total_hashes: int) -> int:
        """
        Inserts a song name into the database, returns the new
        identifier of the song.

        :param song_name: The name of the song.
        :param file_hash: Hash from the fingerprinted file.
        :param total_hashes: amount of hashes to be inserted on fingerprint table.
        :return: the inserted id.
        """
        pass

    def query(self, fingerprint: str = None) -> List[Tuple]:
        """
        Returns all matching fingerprint entries associated with
        the given hash as parameter, if None is passed it returns all entries.

        :param fingerprint: part of a sha1 hash, in hexadecimal format
        :return: a list of fingerprint records stored in the db.
        """
        with self.cursor() as cur:
            if fingerprint:
                cur.execute(self.SELECT, (fingerprint,))
            else:  # select all if no key
                cur.execute(self.SELECT_ALL)
            return list(cur)

    def get_iterable_kv_pairs(self) -> List[Tuple]:
        """
        Returns all fingerprints in the database.

        :return: a list containing all fingerprints stored in the db.
        """
        return self.query(None)

    def insert_hashes(self, song_id: int, hashes: List[Tuple[str, int]], batch_size: int = 1000) -> None:
        """
        Insert a multitude of fingerprints.

        :param song_id: Song identifier the fingerprints belong to
        :param hashes: A sequence of tuples in the format (hash, offset)
            - hash: Part of a sha1 hash, in hexadecimal format
            - offset: Offset this hash was created from/at.
        :param batch_size: insert batches.
        """
        values = [(song_id, hsh, int(offset)) for hsh, offset in hashes]

        with self.cursor() as cur:
            for index in range(0, len(hashes), batch_size):
                cur.executemany(self.INSERT_FINGERPRINT, values[index: index + batch_size])

    def group_points(self, data):
        MIN_GROUP_SIZE = 10
        MIN_DISTANCE = 100
        data = np.sort(data)
        groups = []
        current_group = [data[0]]

        # Iterate through the array to form groups
        for i in range(1, len(data)):
            if data[i] - data[i-1] <= MIN_DISTANCE:
                current_group.append(data[i])
            else:
                groups.append(current_group)
                current_group = [data[i]]

        # Append the last group
        if len(current_group) > 0:
            groups.append(current_group)
        return [np.array(group) for group in groups if len(group) > MIN_GROUP_SIZE]
    
    def convert_to_sec2(self, offset):
        return round(float(offset) / DEFAULT_FS * DEFAULT_WINDOW_SIZE * DEFAULT_OVERLAP_RATIO, 5)
    

    def get_bounds_in_sec(self, data):
        groups = self.group_points(data)
        if len(groups) > 0:
            g1 = groups[0]
            return (self.convert_to_sec2(g1.min()), self.convert_to_sec2(g1.max()))
        else:
            return (-1, -1)
        

    def return_matches(self, hashes: List[Tuple[str, int]],
                       batch_size: int = 1000) -> Tuple[List[Tuple[int, int]], Dict[int, int]]:
        """
        Searches the database for pairs of (hash, offset) values.

        :param hashes: A sequence of tuples in the format (hash, offset)
            - hash: Part of a sha1 hash, in hexadecimal format
            - offset: Offset this hash was created from/at.
        :param batch_size: number of query's batches.
        :return: a list of (sid, offset_difference) tuples and a
        dictionary with the amount of hashes matched (not considering
        duplicated hashes) in each song.
            - song id: Song identifier
            - offset_difference: (database_offset - sampled_offset)
        """
        # Create a dictionary of hash => offset pairs for later lookups
        mapper = {}
        for hsh, offset in hashes:
            if hsh.upper() in mapper.keys():
                mapper[hsh.upper()].append(offset)
            else:
                mapper[hsh.upper()] = [offset]

        values = list(mapper.keys())

        # in order to count each hash only once per db offset we use the dic below
        dedup_hashes = {}

        results = []
        # stored_offsets = []
        # sample_offsets = []
        map_db_offsets={}
        map_ch_offsets={}
        with self.cursor() as cur:
            for index in range(0, len(values), batch_size):
                # Create our IN part of the query
                query = self.SELECT_MULTIPLE % ', '.join([self.IN_MATCH] * len(values[index: index + batch_size]))

                cur.execute(query, values[index: index + batch_size])
                rows = cur.fetchall()

                for hsh, sid, offset in rows:
                    if sid not in dedup_hashes.keys():
                        dedup_hashes[sid] = 1
                        db_offsets = []
                        ch_offsets = []
                        map_db_offsets[sid] = db_offsets
                        map_db_offsets[sid] = ch_offsets
                    else:
                        dedup_hashes[sid] += 1
                        db_offsets = map_db_offsets[sid]
                        ch_offsets = map_ch_offsets[sid]
                    #  we now evaluate all offset for each  hash matched
                    for song_sampled_offset in mapper[hsh]:
                        results.append((sid, offset - song_sampled_offset))
                        db_offsets.append(offset)
                        ch_offsets.append(song_sampled_offset)
            found = False
            for sid in dedup_hashes.keys():
                stored_np = np.array(map_db_offsets[sid])
                sample_np = np.array(map_ch_offsets[sid])
                deltas = stored_np - sample_np
                bin_width = 5
                bins = np.arange(deltas.min(), deltas.max() + bin_width, bin_width)
                hist, bin_edges = np.histogram(deltas, bins = bins)
                
                max_bin_index = np.argmax(hist)
                lower_bound = bin_edges[max_bin_index]
                upper_bound = bin_edges[max_bin_index + 1]
                
                mask = (deltas >= lower_bound) & (deltas < upper_bound)
                stored_filtered = stored_np[mask]
                sample_filtered = sample_np[mask]
                if hist.max() > 100:
                    (xmin, xmax) = self.get_bounds_in_sec(stored_filtered)
                    (ymin, ymax) = self.get_bounds_in_sec(sample_filtered)
                    song = self.get_song_by_id(sid)
                    print (f"Song: {song}")
                    print (f"Original file segment: {xmin}, {xmax}")
                    print (f"Checked file segment: {ymin}, {ymax}")
                    found = True
            if not found:
                print("No reusage found.")

            # plt.scatter(stored_offsets, sample_offsets)
            # plt.grid(True)
            # print ('Saving results...')
            # plt.savefig('result.png')
            # plt.show()
            # plt.close()
            
            # print ('Saving histogram...')
            # plt.hist(deltas, bins=bins)
            # plt.grid(True)
            # plt.savefig('hist.png')
            # plt.show()
            # plt.close()

            return results, dedup_hashes


    def delete_songs_by_id(self, song_ids: List[int], batch_size: int = 1000) -> None:
        """
        Given a list of song ids it deletes all songs specified and their corresponding fingerprints.

        :param song_ids: song ids to be deleted from the database.
        :param batch_size: number of query's batches.
        """
        with self.cursor() as cur:
            for index in range(0, len(song_ids), batch_size):
                # Create our IN part of the query
                query = self.DELETE_SONGS % ', '.join(['%s'] * len(song_ids[index: index + batch_size]))

                cur.execute(query, song_ids[index: index + batch_size])
