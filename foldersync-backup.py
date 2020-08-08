import configparser
import os
import time
import datetime
import shutil
from pathlib import Path
import sqlite3


class FoldersyncBackup(object):

    def __init__(self):
        self.config = configparser.ConfigParser()
        gen_root_dir = os.path.dirname(os.path.realpath(__file__))
        config_path = os.path.join(gen_root_dir, "config.cfg")
        self.config.read(config_path)

        self.interval = self.config["config"].getint("interval")
        self.config.remove_section("config")


    def main(self):
        print("main: \n")
        running = True

        while running:
            conn = sqlite3.connect('foldersync-backup.db')
            c = conn.cursor()
            for section in self.config:
                if section == "DEFAULT":
                    continue

                # Create table in SQLite Database, if not exist
                table_name = self.scrub(section)
                c.execute("CREATE TABLE IF NOT EXISTS " + table_name + " (rel_path text, modified_date timestamp, "
                          "PRIMARY KEY(\"rel_path\") );")
                conn.commit()


                overwrite = self.config[section].getboolean("overwrite_if_edited")
                src = self.config[section]["source"]
                # removes trailing slash
                src = os.path.abspath(src)
                dest = self.config[section]["destination"]
                # removes trailing slash
                dest = os.path.abspath(dest)

                # print(src, dest, overwrite)

                for subdir, dirs, files in os.walk(src):
                    for file in files:
                        path = os.path.join(subdir, file)
                        print()
                        print(path)
                        # print("subdir: ", subdir)
                        # print("file: ", file)
                        rel_path = "".join(path.split(src+"/", 1))
                        print("rel_path: ", rel_path)

                        # new path for file
                        new_path = os.path.join(dest, rel_path)
                        print("new_path: ", new_path)

                        # skip if file is a folder
                        if os.path.isdir(path):
                            continue

                        c.execute('SELECT modified_date as "[timestamp]" FROM ' + table_name + " WHERE rel_path='"+rel_path+"'")
                        saved_last_modified = c.fetchone()
                        print("saved_last_modified: ", saved_last_modified)
                        print(type(saved_last_modified))

                        # if there is no entry. Go ahead and copy and insert, that it was copied
                        if not saved_last_modified:

                            # create new directory if not exist
                            new_rel_path = os.path.dirname(rel_path)
                            new_dir = os.path.join(dest, new_rel_path)
                            Path(new_dir).mkdir(parents=True, exist_ok=True)

                            last_modified = self.modified_date(path)
                            c.execute("INSERT INTO " + table_name + " VALUES(?, ?)", (rel_path, last_modified))

                            shutil.copy2(path, new_path)
                            conn.commit()

                        elif overwrite:
                            last_modified = self.modified_date(path)
                            saved_last_modified = saved_last_modified[0]
                            try:
                                saved_last_modified = datetime.datetime.strptime(saved_last_modified,
                                                                                 "%Y-%m-%d %H:%M:%S.%f")
                            except ValueError as err:
                                saved_last_modified = datetime.datetime.strptime(saved_last_modified,
                                                                                 "%Y-%m-%d %H:%M:%S")
                            print(saved_last_modified)

                            if last_modified > saved_last_modified:

                                # create new directory if not exist
                                new_rel_path = os.path.dirname(rel_path)
                                new_dir = os.path.join(dest, new_rel_path)
                                Path(new_dir).mkdir(parents=True, exist_ok=True)

                                c.execute("UPDATE " + table_name + " SET modified_date = ? WHERE rel_path = ?",
                                          (last_modified, rel_path))

                                shutil.copy2(path, new_path)
                                conn.commit()

                        else:
                            print("skipped")


            # exit(1)
            time.sleep(self.interval)

    """
    returns a clean String, usable as a DB table name
    """
    def scrub(self, table_name):
        return ''.join(chr for chr in table_name if chr.isalnum())

    """
    returns the last modified date of given file
    """
    def modified_date(self, path):
        return datetime.datetime.fromtimestamp(os.path.getmtime(path))


if __name__ == "__main__":
    fsb = FoldersyncBackup()
    fsb.main()
