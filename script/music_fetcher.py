import json
from pathlib import Path

import requests
import musicbrainzngs

from script.logger import AppLogger
from script.load_music import *

# MusicBrainz要求设置UA
musicbrainzngs.set_useragent("MusicClassifier", "1.0.2")

class MusicFetcher:

    def __init__(self, log=None):
        if log:
            self.logger=log
        else:
            self.logger=AppLogger()
    
    def set_logger(self, log):
        if log:
            self.logger=log     

    def search_song(self, title, artist):
        """
        MusicBrainz搜索歌曲
        """
        try:
            result = musicbrainzngs.search_recordings(
                recording=title,
                artist=artist,
                limit=1
            )

            if not result["recording-list"]:
                return None
        except Exception as e:
            self.logger.exception(e)
            return None

        return result["recording-list"][0]

    def get_release_id(self, recording):

        release_list = recording.get("release-list", [])

        if not release_list:
            return None

        return release_list[0]["id"]

    def get_cover_url(self, release_id):
        """
        Cover Art Archive
        """
        if not release_id:
            return None

        return (
            f"https://coverartarchive.org/release/"
            f"{release_id}/front"
        )

    def download_cover(self, url, save_path):

        try:
            r = requests.get(url, timeout=20)

            if r.status_code == 200:
                with open(save_path, "wb") as f:
                    f.write(r.content)
                return True

        except Exception as e:
            self.logger.exception(e)

        return False

    def get_lyrics(self, title, artist):
        
        try:
            search = requests.get(
                "https://lrclib.net/api/search",
                params={
                    "track_name": title,
                    "artist_name": artist
                },
                timeout=20
            )
            

            if search.status_code != 200:
                return None

            results = search.json()

            if not results:
                return None
        except Exception as e:
            self.logger.exception(e)
            return None

        best = results[0]

        return {
            "plainLyrics": best.get("plainLyrics"),
            "syncedLyrics": best.get("syncedLyrics"),
            "album": best.get("albumName"),
            "duration": best.get("duration")
        }

    def build_song(self, title, artist):

        print(f"Searching: {artist} - {title}")

        release_id = None
        lyrics_data = None
        cover_url = None

        recording = self.search_song(title, artist)

        if not recording:
            return None

        release_id = self.get_release_id(recording)
        cover_url = self.get_cover_url(release_id)
        lyrics_data = self.get_lyrics(title, artist)

        # print(recording.get("artist-credit-phrase"))
        song_data = {
            "title": to_simplified(recording.get("title")),
            "artist": to_simplified(recording.get("artist-credit-phrase")),
            "musicbrainz_id": recording.get("id"),
            "release_id": release_id,
            "album": "",
            "year": "",
            "cover_url": cover_url,
            "lyrics": "",
            "synced_lyrics": ""
        }

        release_list = recording.get(
            "release-list",
            []
        )

        if release_list:

            for release in release_list:
                if song_data["album"] == "" or song_data["year"] == "":
                    song_data["album"] = to_simplified(release.get("title",""))
                    song_data["year"] = release.get("date","")

        if lyrics_data:

            song_data["lyrics"] = (
                lyrics_data.get(
                    "plainLyrics",
                    ""
                )
            )

            song_data["synced_lyrics"] = (
                lyrics_data.get(
                    "syncedLyrics",
                    ""
                )
            )

        return song_data

    def save_song(self, song, save_dir="music_data"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        safe_name = (
            f"{song['artist']}"
            f" - "
            f"{song['title']}"
        ).replace("/", "_")

        song_dir = (
            self.save_dir /
            safe_name
        )

        song_dir.mkdir(exist_ok=True)

        json_file = song_dir / "song.json"

        with open(
                json_file,
                "w",
                encoding="utf-8"
        ) as f:
            json.dump(
                song,
                f,
                indent=4,
                ensure_ascii=False
            )

        if song["cover_url"]:

            self.download_cover(
                song["cover_url"],
                song_dir / "cover.jpg"
            )

        if song["lyrics"]:

            with open(
                    song_dir / "lyrics.txt",
                    "w",
                    encoding="utf-8"
            ) as f:
                f.write(song["lyrics"])

        if song["synced_lyrics"]:

            with open(
                    song_dir / "lyrics.lrc",
                    "w",
                    encoding="utf-8"
            ) as f:
                f.write(song["synced_lyrics"])

        print(
            f"Saved => {song_dir}"
        )


if __name__ == "__main__":

    fetcher = MusicFetcher()

    songs = [

        ("Shape of You", "Ed Sheeran"),

        ("Yellow", "Coldplay"),

        ("Someone Like You", "Adele")

    ]

    for title, artist in songs:

        try:

            data = fetcher.build_song(
                title,
                artist
            )

            if data:
                fetcher.save_song(
                    data
                )

        except Exception as e:

            print(
                title,
                artist,
                e
            )
